from fastapi import FastAPI, APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson.decimal128 import Decimal128
from pydantic import BaseModel, EmailStr, Field, field_validator
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal, Optional
from urllib.parse import urlsplit
import asyncio, csv, hashlib, io, json, os, re, uuid, requests
from emergentintegrations.llm.chat import LlmChat, TextDelta, StreamDone, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI()
api = APIRouter(prefix="/api")

def normalize_origin(origin: str):
    try:
        parsed = urlsplit(origin.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            return None
        port = parsed.port  # Validate that a provided port is numeric and in range.
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower()
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        default_port = 443 if scheme == "https" else 80
        netloc = hostname if port is None or port == default_port else f"{hostname}:{port}"
        return f"{scheme}://{netloc}"
    except ValueError:
        return None

configured_origins = os.environ.get("CORS_ORIGINS", "")
if "*" in configured_origins:
    raise RuntimeError("CORS_ORIGINS must list exact frontend origins; wildcard origins are not allowed")
origin_values = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
invalid_origins = [origin for origin in origin_values if normalize_origin(origin) is None]
if invalid_origins:
    raise RuntimeError("CORS_ORIGINS contains an invalid origin; use scheme://host[:port] values")
ALLOWED_ORIGINS = sorted({normalize_origin(origin) for origin in origin_values})

def uid(prefix): return f"{prefix}_{uuid.uuid4().hex[:12]}"
def now(): return datetime.now(timezone.utc).isoformat()
def clean(doc):
    if not doc: return None
    doc.pop("_id", None)
    return doc

class SessionRequest(BaseModel): session_id: str
class AccountDeleteIn(BaseModel):
    email: EmailStr
    ownership_transfers: dict[str, str] = Field(default_factory=dict)
class ControlIn(BaseModel): name: str = Field(min_length=2, max_length=120); description: str = Field(default="", max_length=500)
class MemberIn(BaseModel): email: EmailStr; role: Literal["viewer", "editor"] = "viewer"
class TagIn(BaseModel): name: str = Field(min_length=1, max_length=80); color: str = "#059669"; kind: Literal["income", "expense", "both"] = "both"
class TransactionIn(BaseModel):
    type: Literal["income", "expense"]
    amount: str = Field(min_length=1, max_length=32)
    date: str = Field(max_length=20)
    description: str = Field(min_length=1, max_length=120)
    tag_id: str = Field(min_length=1)
    note: str = Field(default="", max_length=500)

    @field_validator("date")
    @classmethod
    def normalize_date(cls, value):
        raw = value.strip()
        for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, date_format).date().isoformat()
            except ValueError:
                pass
        raise ValueError("Use uma data válida no formato AAAA-MM-DD")

MAX_TRANSACTION_AMOUNT = Decimal("999999999.99")

def normalize_amount(raw):
    try:
        amount = Decimal(str(raw).strip().replace(",", "."))
        if not amount.is_finite():
            raise InvalidOperation
        amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(422, "Valor inválido")
    if amount <= 0 or amount > MAX_TRANSACTION_AMOUNT:
        raise HTTPException(422, "O valor deve ser maior que zero e menor que R$ 1.000.000.000,00")
    return amount

def transaction_date_expression():
    raw_date = {"$toString": {"$ifNull": ["$date", ""]}}
    legacy_date = {"$regexMatch": {"input": raw_date, "regex": r"^\d{2}/\d{2}/\d{4}$"}}
    return {
        "$dateFromString": {
            "dateString": raw_date,
            "format": {"$cond": [legacy_date, "%d/%m/%Y", "%Y-%m-%d"]},
            "onError": None,
            "onNull": None,
        }
    }

def transaction_amount_expression():
    raw_amount = {"$toString": {"$ifNull": ["$amount", "0"]}}
    return {"$convert": {"input": raw_amount, "to": "decimal", "onError": 0, "onNull": 0}}

def normalized_date_stage():
    return {"$addFields": {
        "date": {
            "$cond": [
                {"$ne": ["$_parsed_date", None]},
                {"$dateToString": {"format": "%Y-%m-%d", "date": "$_parsed_date", "timezone": "UTC"}},
                "",
            ]
        }
    }}

def safe_csv_text(value):
    text = str(value or "")
    return f"'{text}" if text.lstrip().startswith(("=", "+", "-", "@")) else text

def formatted_amount(value):
    amount = value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value or "0"))
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

async def current_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(401, "Sessão necessária")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session: raise HTTPException(401, "Sessão expirada")
    if session.get("user_id") == "user_demo":
        await db.user_sessions.delete_many({"session_token": token})
        raise HTTPException(401, "Sessão de demonstração antiga expirada")
    expiry = session.get("expires_at", "")
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry < datetime.now(timezone.utc): raise HTTPException(401, "Sessão expirada")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user: raise HTTPException(401, "Usuário não encontrado")
    return user

async def access(user_id, control_id, roles=None):
    member = await db.members.find_one({"control_id": control_id, "user_id": user_id}, {"_id": 0})
    if not member or (roles and member["role"] not in roles): raise HTTPException(403, "Você não tem permissão para esta ação")
    control = await db.controls.find_one({"control_id": control_id}, {"_id": 0, "deleting": 1})
    if not control or control.get("deleting"):
        raise HTTPException(404, "Controle não encontrado")
    return member

async def cleanup_demo_user(user_id):
    controls = await db.controls.find({"owner_id": user_id}, {"_id": 0, "control_id": 1}).to_list(None)
    for control in controls:
        control_id = control["control_id"]
        await db.transactions.delete_many({"control_id": control_id})
        await db.tags.delete_many({"control_id": control_id})
        await db.ai_insights.delete_many({"control_id": control_id})
        await db.members.delete_many({"control_id": control_id})
        await db.controls.delete_one({"control_id": control_id, "owner_id": user_id})
    await db.members.delete_many({"user_id": user_id})
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.users.delete_one({"user_id": user_id, "is_demo": True})

@api.get("/auth/me")
async def me(request: Request): return await current_user(request)

@api.post("/auth/session")
async def auth_session(body: SessionRequest, response: Response):
    try:
        r = await asyncio.to_thread(requests.get, "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": body.session_id}, timeout=15)
    except requests.RequestException as exc:
        raise HTTPException(502, "O serviço de autenticação está temporariamente indisponível") from exc
    if r.status_code != 200: raise HTTPException(401, "Não foi possível validar o acesso")
    data = r.json(); user = {"user_id": f"user_{data['id']}", "email": data["email"], "name": data.get("name") or data["email"], "picture": data.get("picture", ""), "created_at": now()}
    await db.users.update_one({"email": user["email"]}, {"$set": user}, upsert=True)
    existing = await db.users.find_one({"email": user["email"]}, {"_id": 0}); user = existing
    token = data["session_token"]
    await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token, "expires_at": (datetime.now(timezone.utc)+timedelta(days=7)).isoformat(), "created_at": now()})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/")
    return user

@api.post("/auth/demo")
async def demo_auth(response: Response):
    await db.user_sessions.delete_many({"user_id": "user_demo"})
    expired_sessions = await db.user_sessions.find(
        {"user_id": {"$regex": r"^user_demo_"}, "expires_at": {"$lt": now()}},
        {"_id": 0, "user_id": 1},
    ).to_list(500)
    for expired_user_id in {session["user_id"] for session in expired_sessions}:
        await cleanup_demo_user(expired_user_id)
    demo_id = uuid.uuid4().hex
    user = {"user_id": f"user_demo_{demo_id}", "email": f"demo+{demo_id}@example.com", "name": "Conta demonstração", "is_demo": True, "created_at": now()}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": user}, upsert=True)
    token = f"demo_{uuid.uuid4().hex}"; await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token, "expires_at": (datetime.now(timezone.utc)+timedelta(days=1)).isoformat(), "created_at": now()})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/"); return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0, "user_id": 1})
        if session:
            user = await db.users.find_one({"user_id": session["user_id"], "is_demo": True}, {"_id": 0, "user_id": 1})
            if user:
                await cleanup_demo_user(user["user_id"])
            else:
                await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/"); return {"ok": True}

@api.delete("/auth/account")
async def delete_account(body: AccountDeleteIn, request: Request, response: Response):
    user = await current_user(request)
    if user.get("is_demo"):
        raise HTTPException(403, "Contas de demonstração são removidas ao sair")
    if body.email.strip().casefold() != user.get("email", "").strip().casefold():
        raise HTTPException(422, "O e-mail de confirmação não corresponde à conta")

    user_id = user["user_id"]
    owned = await db.controls.find(
        {"owner_id": user_id}, {"_id": 0, "control_id": 1}
    ).to_list(None)
    owned_ids = [control["control_id"] for control in owned]
    transferred_ids = []
    if owned_ids:
        await db.controls.update_many(
            {"control_id": {"$in": owned_ids}, "owner_id": user_id},
            {"$set": {"deleting": True}},
        )
        other_members = await db.members.find({
            "control_id": {"$in": owned_ids}, "user_id": {"$ne": user_id},
        }, {"_id": 0, "control_id": 1, "user_id": 1, "role": 1}).to_list(None)
        shared_member_ids = {member["control_id"] for member in other_members}
        transfers = body.ownership_transfers
        missing_transfers = shared_member_ids - set(transfers)
        invalid_transfer_controls = set(transfers) - shared_member_ids
        if missing_transfers or invalid_transfer_controls:
            await db.controls.update_many(
                {"control_id": {"$in": owned_ids}, "owner_id": user_id},
                {"$unset": {"deleting": ""}},
            )
            raise HTTPException(
                409,
                "Escolha um novo proprietário para cada controle compartilhado que você possui",
            )

        member_ids_by_control = {}
        for member in other_members:
            member_ids_by_control.setdefault(member["control_id"], set()).add(member["user_id"])
        transfer_users = {}
        for control_id, new_owner_id in transfers.items():
            new_owner = await db.users.find_one({"user_id": new_owner_id}, {"_id": 0, "user_id": 1})
            if new_owner_id == user_id or new_owner_id not in member_ids_by_control[control_id] or not new_owner:
                await db.controls.update_many(
                    {"control_id": {"$in": owned_ids}, "owner_id": user_id},
                    {"$unset": {"deleting": ""}},
                )
                raise HTTPException(422, "O novo proprietário precisa ser outro membro ativo do controle")
            transfer_users[control_id] = new_owner_id

        for control_id, new_owner_id in transfer_users.items():
            previous_role = next(
                member["role"]
                for member in other_members
                if member["control_id"] == control_id and member["user_id"] == new_owner_id
            )
            member_update = await db.members.update_one(
                {"control_id": control_id, "user_id": new_owner_id},
                {"$set": {"role": "owner"}},
            )
            if not member_update.matched_count:
                await db.controls.update_many(
                    {"control_id": {"$in": owned_ids}, "owner_id": user_id},
                    {"$unset": {"deleting": ""}},
                )
                raise HTTPException(409, "O membro escolhido não está mais no controle; atualize a página")
            control_update = await db.controls.update_one(
                {"control_id": control_id, "owner_id": user_id, "deleting": True},
                {"$set": {"owner_id": new_owner_id}, "$unset": {"deleting": ""}},
            )
            if not control_update.matched_count:
                await db.members.update_one(
                    {"control_id": control_id, "user_id": new_owner_id},
                    {"$set": {"role": previous_role}},
                )
                await db.controls.update_many(
                    {"control_id": {"$in": owned_ids}, "owner_id": user_id},
                    {"$unset": {"deleting": ""}},
                )
                raise HTTPException(409, "Não foi possível transferir a propriedade; tente novamente")
            transferred_ids.append(control_id)

    delete_ids = [control_id for control_id in owned_ids if control_id not in transferred_ids]

    # Preserve financial records in controls that survive, while removing this
    # user's identity from transaction authorship and revoking their memberships.
    retained_controls = {"$nin": delete_ids}
    await db.transactions.update_many(
        {"user_id": user_id, "control_id": retained_controls},
        {"$unset": {"user_id": ""}, "$set": {"user_name": "Usuário removido"}},
    )
    await db.ai_insights.delete_many({"user_id": user_id, "control_id": retained_controls})
    await db.members.delete_many({"user_id": user_id, "control_id": retained_controls})

    if delete_ids:
        await db.transactions.delete_many({"control_id": {"$in": delete_ids}})
        await db.tags.delete_many({"control_id": {"$in": delete_ids}})
        await db.ai_insights.delete_many({"control_id": {"$in": delete_ids}})
        await db.members.delete_many({"control_id": {"$in": delete_ids}})
        await db.controls.delete_many({"control_id": {"$in": delete_ids}, "owner_id": user_id})

    await db.user_sessions.delete_many({"user_id": user_id})
    await db.users.delete_one({"user_id": user_id})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

@api.get("/controls")
async def controls(request: Request):
    user = await current_user(request); ids = [m["control_id"] async for m in db.members.find({"user_id": user["user_id"]}, {"_id": 0})]
    return await db.controls.find(
        {"control_id": {"$in": ids}, "deleting": {"$ne": True}}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)

@api.post("/controls")
async def create_control(body: ControlIn, request: Request):
    user = await current_user(request); cid = uid("control"); control = {"control_id": cid, "name": body.name, "description": body.description, "owner_id": user["user_id"], "created_at": now()}
    await db.controls.insert_one(control); await db.members.insert_one({"control_id": cid, "user_id": user["user_id"], "email": user["email"], "role": "owner"}); return clean(control)

@api.post("/controls/{cid}/members")
async def add_member(cid: str, body: MemberIn, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); invited = await db.users.find_one({"email": body.email}, {"_id": 0})
    if not invited: raise HTTPException(404, "Usuário não encontrado. Ele precisa acessar o app primeiro.")
    if invited.get("is_demo") or user.get("is_demo"):
        raise HTTPException(403, "O compartilhamento não está disponível na demonstração")
    doc = {"control_id": cid, "user_id": invited["user_id"], "email": body.email, "role": body.role}; await db.members.update_one({"control_id": cid, "email": body.email}, {"$set": doc}, upsert=True); return doc

@api.delete("/controls/{cid}/members/{member_user_id}")
async def remove_member(cid: str, member_user_id: str, request: Request):
    user = await current_user(request)
    await access(user["user_id"], cid, ["owner"])
    if member_user_id == user["user_id"]:
        raise HTTPException(422, "Transfira a propriedade antes de remover o proprietário")
    result = await db.members.delete_one({"control_id": cid, "user_id": member_user_id})
    if not result.deleted_count:
        raise HTTPException(404, "Membro não encontrado")
    return {"ok": True}

@api.get("/controls/{cid}/members")
async def members(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid); return await db.members.find({"control_id": cid}, {"_id": 0}).to_list(100)

@api.get("/controls/{cid}/tags")
async def tags(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid); return await db.tags.find({"control_id": cid}, {"_id": 0}).to_list(100)

@api.post("/controls/{cid}/tags")
async def create_tag(cid: str, body: TagIn, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner", "editor"]); doc = {"tag_id": uid("tag"), "control_id": cid, **body.model_dump()}; await db.tags.insert_one(doc); return clean(doc)

@api.get("/controls/{cid}/transactions")
async def transactions(
    cid: str,
    request: Request,
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    sort: Literal["date", "amount"] = "date",
):
    user = await current_user(request)
    await access(user["user_id"], cid)
    match = {"control_id": cid}
    if q.strip():
        match["description"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    pipeline = [
        {"$match": match},
        {"$addFields": {
            "_parsed_date": transaction_date_expression(),
            "_amount_numeric": transaction_amount_expression(),
        }},
    ]
    sort_order = {"_amount_numeric": -1, "_parsed_date": -1, "created_at": -1} if sort == "amount" else {"_parsed_date": -1, "created_at": -1}
    paginated = page is not None or page_size is not None or bool(q.strip())
    if paginated:
        current_page = page or 1
        current_page_size = page_size or 25
        items_pipeline = [
            {"$skip": (current_page - 1) * current_page_size},
            {"$limit": current_page_size},
            normalized_date_stage(),
            {"$project": {"_id": 0, "_parsed_date": 0, "_amount_numeric": 0}},
        ]
        result = await db.transactions.aggregate(
            pipeline + [
                {"$sort": sort_order},
                {"$facet": {
                    "items": items_pipeline,
                    "metadata": [{"$count": "total"}],
                }},
            ],
            allowDiskUse=True,
        ).to_list(1)
        payload = result[0] if result else {"items": [], "metadata": []}
        total = payload["metadata"][0]["total"] if payload["metadata"] else 0
        return {"items": payload["items"], "total": total, "page": current_page, "page_size": current_page_size}

    pipeline.extend([
        {"$sort": sort_order},
        {"$limit": 1000},
        normalized_date_stage(),
        {"$project": {"_id": 0, "_parsed_date": 0, "_amount_numeric": 0}},
    ])
    return await db.transactions.aggregate(pipeline).to_list(1000)

@api.get("/controls/{cid}/transactions/export")
async def export_transactions(cid: str, request: Request):
    user = await current_user(request)
    await access(user["user_id"], cid)
    tags = await db.tags.find({"control_id": cid}, {"_id": 0, "tag_id": 1, "name": 1}).to_list(1000)
    tag_names = {tag["tag_id"]: tag["name"] for tag in tags}
    cursor = db.transactions.aggregate(
        [
            {"$match": {"control_id": cid}},
            {"$addFields": {"_parsed_date": transaction_date_expression()}},
            {"$sort": {"_parsed_date": -1, "created_at": -1}},
            normalized_date_stage(),
            {"$project": {"_id": 0, "_parsed_date": 0}},
        ],
        allowDiskUse=True,
    )

    async def csv_rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Data", "Tipo", "Valor (R$)", "Descrição", "Tag", "Observação", "Lançado por"])
        yield "\ufeff" + buffer.getvalue()
        async for transaction in cursor:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow([
                safe_csv_text(transaction.get("date", "")),
                safe_csv_text("Entrada" if transaction.get("type") == "income" else "Saída"),
                safe_csv_text(transaction.get("amount", "0.00")),
                safe_csv_text(transaction.get("description")),
                safe_csv_text(tag_names.get(transaction.get("tag_id"), "")),
                safe_csv_text(transaction.get("note")),
                safe_csv_text(transaction.get("user_name")),
            ])
            yield buffer.getvalue()

    return StreamingResponse(
        csv_rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="controle-{cid}-lancamentos.csv"'},
    )

@api.get("/controls/{cid}/summary")
async def financial_summary(
    cid: str,
    request: Request,
    transaction_type: Optional[Literal["income", "expense"]] = Query(default=None, alias="type"),
    tag_id: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    user = await current_user(request)
    await access(user["user_id"], cid)
    match = {"control_id": cid}
    if transaction_type:
        match["type"] = transaction_type
    if tag_id:
        match["tag_id"] = tag_id
    if user_id:
        match["user_id"] = user_id
    pipeline = [
        {"$match": match},
        {"$addFields": {
            "_parsed_date": transaction_date_expression(),
            "_amount_numeric": transaction_amount_expression(),
        }},
    ]
    date_range = {}
    try:
        if date_from:
            start = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if start.strftime("%Y-%m-%d") != date_from:
                raise ValueError("Data inválida")
            date_range["$gte"] = start
        if date_to:
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if end.strftime("%Y-%m-%d") != date_to:
                raise ValueError("Data inválida")
            date_range["$lt"] = end
    except ValueError as exc:
        raise HTTPException(422, "Período inválido") from exc
    if date_range:
        pipeline.append({"$match": {"_parsed_date": date_range}})

    zero = Decimal128("0.00")
    income_expression = {"$cond": [{"$eq": ["$type", "income"]}, "$_amount_numeric", zero]}
    expense_expression = {"$cond": [{"$eq": ["$type", "expense"]}, "$_amount_numeric", zero]}
    total_rows, tag_rows, trend_rows = await asyncio.gather(
        db.transactions.aggregate(pipeline + [{"$group": {
            "_id": None,
            "entries_total": {"$sum": income_expression},
            "expenses_total": {"$sum": expense_expression},
            "transaction_count": {"$sum": 1},
        }}], allowDiskUse=True).to_list(1),
        db.transactions.aggregate(pipeline + [
            {"$match": {"type": "expense"}},
            {"$group": {"_id": "$tag_id", "amount": {"$sum": "$_amount_numeric"}}},
        ], allowDiskUse=True).to_list(None),
        db.transactions.aggregate(pipeline + [
            {"$match": {"_parsed_date": {"$ne": None}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$_parsed_date", "timezone": "UTC"}},
                "entries_total": {"$sum": income_expression},
                "expenses_total": {"$sum": expense_expression},
            }},
            {"$sort": {"_id": -1}},
            {"$limit": 6},
            {"$sort": {"_id": 1}},
        ], allowDiskUse=True).to_list(6),
    )
    totals = total_rows[0] if total_rows else {}
    tag_docs = await db.tags.find({"control_id": cid}, {"_id": 0, "tag_id": 1, "name": 1, "color": 1}).to_list(1000)
    tags_by_id = {tag["tag_id"]: tag for tag in tag_docs}
    expenses_by_tag = [
        {
            "tag_id": row["_id"],
            "name": tags_by_id.get(row["_id"], {}).get("name", "Outros"),
            "color": tags_by_id.get(row["_id"], {}).get("color", "#6c7f80"),
            "amount": formatted_amount(row["amount"]),
        }
        for row in tag_rows
    ]
    return {
        "entries_total": formatted_amount(totals.get("entries_total", "0.00")),
        "expenses_total": formatted_amount(totals.get("expenses_total", "0.00")),
        "transaction_count": totals.get("transaction_count", 0),
        "expenses_by_tag": expenses_by_tag,
        "trend": [
            {
                "date": row["_id"],
                "entries_total": formatted_amount(row["entries_total"]),
                "expenses_total": formatted_amount(row["expenses_total"]),
            }
            for row in trend_rows
        ],
    }

@api.delete("/controls/{cid}")
async def delete_control(cid: str, request: Request):
    user = await current_user(request)
    control = await db.controls.find_one({"control_id": cid, "owner_id": user["user_id"]}, {"_id": 0})
    if not control:
        raise HTTPException(404, "Controle não encontrado")
    # Lock the control before checking membership so new requests cannot add members
    # or mutate data while the deletion decision is being made.
    await db.controls.update_one(
        {"control_id": cid, "owner_id": user["user_id"]},
        {"$set": {"deleting": True}},
    )
    members = await db.members.find({"control_id": cid}, {"_id": 0, "user_id": 1}).to_list(101)
    if any(member["user_id"] != user["user_id"] for member in members):
        await db.controls.update_one(
            {"control_id": cid, "owner_id": user["user_id"]},
            {"$unset": {"deleting": ""}},
        )
        raise HTTPException(409, "Remova os outros membros antes de excluir este controle compartilhado")
    await db.transactions.delete_many({"control_id": cid})
    await db.tags.delete_many({"control_id": cid})
    await db.ai_insights.delete_many({"control_id": cid})
    await db.members.delete_many({"control_id": cid})
    result = await db.controls.delete_one({"control_id": cid, "owner_id": user["user_id"]})
    if not result.deleted_count:
        raise HTTPException(404, "Controle não encontrado")
    return {"ok": True}

@api.post("/controls/{cid}/transactions")
async def create_transaction(cid: str, body: TransactionIn, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner", "editor"])
    amount = normalize_amount(body.amount)
    if not await db.tags.find_one({"tag_id": body.tag_id, "control_id": cid}, {"_id": 0}): raise HTTPException(422, "Tag inválida")
    doc = {"transaction_id": uid("tx"), "control_id": cid, "type": body.type, "amount": str(amount), "date": body.date, "description": body.description, "tag_id": body.tag_id, "note": body.note, "user_id": user["user_id"], "user_name": user["name"], "created_at": now()}; await db.transactions.insert_one(doc); return clean(doc)

@api.put("/controls/{cid}/transactions/{tid}")
async def update_transaction(cid: str, tid: str, body: TransactionIn, request: Request):
    user = await current_user(request)
    await access(user["user_id"], cid, ["owner", "editor"])
    amount = normalize_amount(body.amount)
    if not await db.tags.find_one({"tag_id": body.tag_id, "control_id": cid}, {"_id": 0}):
        raise HTTPException(422, "Tag inválida")
    changes = {**body.model_dump(), "amount": str(amount)}
    result = await db.transactions.update_one({"transaction_id": tid, "control_id": cid}, {"$set": changes})
    if not result.matched_count:
        raise HTTPException(404, "Lançamento não encontrado")
    updated = await db.transactions.find_one({"transaction_id": tid, "control_id": cid}, {"_id": 0})
    return updated

@api.delete("/controls/{cid}/transactions/{tid}")
async def delete_transaction(cid: str, tid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); await db.transactions.delete_one({"transaction_id": tid, "control_id": cid}); return {"ok": True}

@api.post("/controls/{cid}/demo-data")
async def demo_data(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); defaults = [("Salário", "#10b981", "income"), ("Alimentação", "#f97316", "expense"), ("Moradia", "#ef4444", "expense"), ("Lazer", "#8b5cf6", "expense")]
    for name, color, kind in defaults: await db.tags.update_one({"control_id": cid, "name": name}, {"$setOnInsert": {"tag_id": uid("tag"), "control_id": cid, "name": name, "color": color, "kind": kind}}, upsert=True)
    tags = await db.tags.find({"control_id": cid}, {"_id": 0}).to_list(20); tag = {t["name"]: t["tag_id"] for t in tags}; base_date = datetime.now(timezone.utc); dates = [(base_date - timedelta(days=offset)).date().isoformat() for offset in [3, 2, 1, 0]]; samples = [("income", "5200.00", dates[0], "Salário mensal", "Salário"), ("expense", "1320.50", dates[1], "Aluguel e condomínio", "Moradia"), ("expense", "248.90", dates[2], "Compras da semana", "Alimentação"), ("expense", "89.90", dates[3], "Cinema e jantar", "Lazer")]
    for index, (typ, amount, date, desc, tg) in enumerate(samples):
        await db.transactions.update_one(
            {"control_id": cid, "demo_key": f"sample-{index + 1}"},
            {"$setOnInsert": {"transaction_id": uid("tx"), "control_id": cid, "type": typ, "amount": amount, "date": date, "description": desc, "tag_id": tag[tg], "note": "Dado de demonstração", "is_demo": True, "demo_key": f"sample-{index + 1}", "user_id": user["user_id"], "user_name": user["name"], "created_at": now()}},
            upsert=True,
        )
    return {"ok": True}

@api.delete("/controls/{cid}/demo-data")
async def delete_demo(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); await db.transactions.delete_many({"control_id": cid, "is_demo": True}); return {"ok": True}

@api.post("/controls/{cid}/ai/insights")
async def ai_insights(cid: str, request: Request):
    user = await current_user(request)
    await access(user["user_id"], cid)
    aggregate_pipeline = [
        {"$match": {"control_id": cid}},
        {"$addFields": {"_amount_numeric": transaction_amount_expression()}},
    ]
    zero = Decimal128("0.00")
    income_expression = {"$cond": [{"$eq": ["$type", "income"]}, "$_amount_numeric", zero]}
    expense_expression = {"$cond": [{"$eq": ["$type", "expense"]}, "$_amount_numeric", zero]}
    total_rows, expense_tag_rows = await asyncio.gather(
        db.transactions.aggregate(aggregate_pipeline + [{"$group": {
            "_id": None,
            "entries_total": {"$sum": income_expression},
            "expenses_total": {"$sum": expense_expression},
            "transaction_count": {"$sum": 1},
        }}], allowDiskUse=True).to_list(1),
        db.transactions.aggregate(aggregate_pipeline + [
            {"$match": {"type": "expense"}},
            {"$group": {"_id": "$tag_id", "amount": {"$sum": "$_amount_numeric"}}},
        ], allowDiskUse=True).to_list(None),
    )
    tags = await db.tags.find({"control_id": cid}, {"_id": 0, "tag_id": 1, "name": 1}).to_list(200)
    tag_names = {tag["tag_id"]: tag["name"] for tag in tags}
    totals = total_rows[0] if total_rows else {}
    by_tag = {}
    for row in expense_tag_rows:
        name = tag_names.get(row["_id"], "Outros")
        amount = row["amount"].to_decimal() if isinstance(row["amount"], Decimal128) else Decimal(str(row["amount"]))
        by_tag[name] = by_tag.get(name, Decimal("0")) + amount
    summary = {
        "entries_total": formatted_amount(totals.get("entries_total", "0.00")),
        "expenses_total": formatted_amount(totals.get("expenses_total", "0.00")),
        "transaction_count": totals.get("transaction_count", 0),
        "expenses_by_tag": {name: formatted_amount(amount) for name, amount in by_tag.items()},
    }
    prompt = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    summary_hash = hashlib.sha256(f"gemini-3.8-flash:v1:{prompt}".encode("utf-8")).hexdigest()
    cached = await db.ai_insights.find_one(
        {"control_id": cid, "summary_hash": summary_hash, "content": {"$type": "string", "$ne": ""}},
        {"_id": 0, "content": 1},
        sort=[("created_at", -1)],
    )
    if cached:
        async def cached_stream():
            yield f"data: {json.dumps({'text': cached['content']}, ensure_ascii=False)}\n\n"
            yield "data: {\"done\":true}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    requested_at = datetime.now(timezone.utc)
    cooldown_cutoff = requested_at - timedelta(minutes=10)
    reservation = await db.users.update_one(
        {
            "user_id": user["user_id"],
            "$or": [
                {"ai_last_requested_at": {"$lt": cooldown_cutoff}},
                {"ai_last_requested_at": {"$exists": False}},
            ],
        },
        {"$set": {"ai_last_requested_at": requested_at}},
    )
    if not reservation.matched_count:
        raise HTTPException(429, "Você já gerou um insight recentemente. Tente novamente em até 10 minutos.")

    async def stream():
        chunks = []
        try:
            chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"finance-insight-{cid}-{uuid.uuid4().hex}", system_message="Você é um orientador financeiro claro e responsável. Analise somente os totais agregados fornecidos. Não invente dados, não dê recomendações de investimento e responda em português do Brasil com três observações práticas e curtas.").with_model("gemini", "gemini-3.8-flash")
            async for event in chat.stream_message(UserMessage(text=f"Gere insights sobre este resumo financeiro agregado, sem mencionar dados pessoais: {prompt}")):
                if isinstance(event, TextDelta):
                    chunks.append(event.content)
                    yield f"data: {json.dumps({'text': event.content}, ensure_ascii=False)}\n\n"
                elif isinstance(event, StreamDone):
                    break
            content = "".join(chunks)
            if content:
                await db.ai_insights.insert_one({"insight_id": uid("insight"), "control_id": cid, "user_id": user["user_id"], "summary": summary, "summary_hash": summary_hash, "content": content, "created_at": now()})
            yield "data: {\"done\":true}\n\n"
        except Exception:
            try:
                await db.users.update_one(
                    {"user_id": user["user_id"], "ai_last_requested_at": requested_at},
                    {"$unset": {"ai_last_requested_at": ""}},
                )
            except Exception:
                pass
            yield f"data: {json.dumps({'error': 'Não foi possível gerar os insights agora.'}, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

app.include_router(api)

@app.middleware("http")
async def reject_untrusted_origins(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        normalized = normalize_origin(origin)
        request_origin = normalize_origin(f"{request.url.scheme}://{request.url.netloc}")
        if normalized is None or (normalized not in ALLOWED_ORIGINS and normalized != request_origin):
            return JSONResponse({"detail": "Origem não autorizada"}, status_code=403)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)
@app.on_event("shutdown")
async def shutdown(): client.close()
