from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
import os, uuid, requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI()
api = APIRouter(prefix="/api")

def uid(prefix): return f"{prefix}_{uuid.uuid4().hex[:12]}"
def now(): return datetime.now(timezone.utc).isoformat()
def clean(doc):
    if not doc: return None
    doc.pop("_id", None)
    return doc

class SessionRequest(BaseModel): session_id: str
class ControlIn(BaseModel): name: str = Field(min_length=2); description: str = ""
class MemberIn(BaseModel): email: str; role: str = "viewer"
class TagIn(BaseModel): name: str; color: str = "#059669"; kind: str = "both"
class TransactionIn(BaseModel):
    type: str; amount: str; date: str; description: str; tag_id: str; note: str = ""

async def current_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(401, "Sessão necessária")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session: raise HTTPException(401, "Sessão expirada")
    expiry = session.get("expires_at", "")
    if isinstance(expiry, str) and datetime.fromisoformat(expiry) < datetime.now(timezone.utc): raise HTTPException(401, "Sessão expirada")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user: raise HTTPException(401, "Usuário não encontrado")
    return user

async def access(user_id, control_id, roles=None):
    member = await db.members.find_one({"control_id": control_id, "user_id": user_id}, {"_id": 0})
    if not member or (roles and member["role"] not in roles): raise HTTPException(403, "Você não tem permissão para esta ação")
    return member

@api.get("/auth/me")
async def me(request: Request): return await current_user(request)

@api.post("/auth/session")
async def auth_session(body: SessionRequest, response: Response):
    r = requests.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": body.session_id}, timeout=15)
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
    user = {"user_id": "user_demo", "email": "demo@meucontrole.test", "name": "Conta demonstração", "created_at": now()}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": user}, upsert=True)
    token = f"demo_{uuid.uuid4().hex}"; await db.user_sessions.insert_one({"user_id": user["user_id"], "session_token": token, "expires_at": (datetime.now(timezone.utc)+timedelta(days=1)).isoformat(), "created_at": now()})
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/"); return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token: await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/"); return {"ok": True}

@api.get("/controls")
async def controls(request: Request):
    user = await current_user(request); ids = [m["control_id"] async for m in db.members.find({"user_id": user["user_id"]}, {"_id": 0})]
    return await db.controls.find({"control_id": {"$in": ids}}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api.post("/controls")
async def create_control(body: ControlIn, request: Request):
    user = await current_user(request); cid = uid("control"); control = {"control_id": cid, "name": body.name, "description": body.description, "owner_id": user["user_id"], "created_at": now()}
    await db.controls.insert_one(control); await db.members.insert_one({"control_id": cid, "user_id": user["user_id"], "email": user["email"], "role": "owner"}); return clean(control)

@api.post("/controls/{cid}/members")
async def add_member(cid: str, body: MemberIn, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); invited = await db.users.find_one({"email": body.email}, {"_id": 0})
    if not invited: raise HTTPException(404, "Usuário não encontrado. Ele precisa acessar o app primeiro.")
    doc = {"control_id": cid, "user_id": invited["user_id"], "email": body.email, "role": body.role}; await db.members.update_one({"control_id": cid, "email": body.email}, {"$set": doc}, upsert=True); return doc

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
async def transactions(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid); return await db.transactions.find({"control_id": cid}, {"_id": 0}).sort("date", -1).to_list(1000)

@api.post("/controls/{cid}/transactions")
async def create_transaction(cid: str, body: TransactionIn, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner", "editor"])
    try: amount = Decimal(body.amount.replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation: raise HTTPException(422, "Valor inválido")
    if amount <= 0 or body.type not in ["income", "expense"]: raise HTTPException(422, "Confira tipo e valor")
    if not await db.tags.find_one({"tag_id": body.tag_id, "control_id": cid}, {"_id": 0}): raise HTTPException(422, "Tag inválida")
    doc = {"transaction_id": uid("tx"), "control_id": cid, "type": body.type, "amount": str(amount), "date": body.date, "description": body.description, "tag_id": body.tag_id, "note": body.note, "user_id": user["user_id"], "user_name": user["name"], "created_at": now()}; await db.transactions.insert_one(doc); return clean(doc)

@api.delete("/controls/{cid}/transactions/{tid}")
async def delete_transaction(cid: str, tid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); await db.transactions.delete_one({"transaction_id": tid, "control_id": cid}); return {"ok": True}

@api.post("/controls/{cid}/demo-data")
async def demo_data(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); defaults = [("Salário", "#10b981", "income"), ("Alimentação", "#f97316", "expense"), ("Moradia", "#ef4444", "expense"), ("Lazer", "#8b5cf6", "expense")]
    for name, color, kind in defaults: await db.tags.update_one({"control_id": cid, "name": name}, {"$setOnInsert": {"tag_id": uid("tag"), "control_id": cid, "name": name, "color": color, "kind": kind}}, upsert=True)
    tags = await db.tags.find({"control_id": cid}, {"_id": 0}).to_list(20); tag = {t["name"]: t["tag_id"] for t in tags}; base_date = datetime.now(timezone.utc); dates = [(base_date - timedelta(days=offset)).strftime("%d/%m/%Y") for offset in [3, 2, 1, 0]]; samples = [("income", "5200.00", dates[0], "Salário mensal", "Salário"), ("expense", "1320.50", dates[1], "Aluguel e condomínio", "Moradia"), ("expense", "248.90", dates[2], "Compras da semana", "Alimentação"), ("expense", "89.90", dates[3], "Cinema e jantar", "Lazer")]
    for typ, amount, date, desc, tg in samples: await db.transactions.insert_one({"transaction_id": uid("tx"), "control_id": cid, "type": typ, "amount": amount, "date": date, "description": desc, "tag_id": tag[tg], "note": "Dado de demonstração", "user_id": user["user_id"], "user_name": user["name"], "created_at": now()})
    return {"ok": True}

@api.delete("/controls/{cid}/demo-data")
async def delete_demo(cid: str, request: Request):
    user = await current_user(request); await access(user["user_id"], cid, ["owner"]); await db.transactions.delete_many({"control_id": cid, "note": "Dado de demonstração"}); return {"ok": True}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])
@app.on_event("shutdown")
async def shutdown(): client.close()