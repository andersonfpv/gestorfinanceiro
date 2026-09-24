import os
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/demo", timeout=20)
    assert response.status_code == 200
    token = session.cookies.get("session_token")
    assert token
    session.headers.update({"Authorization": f"Bearer {token}"})
    yield session
    session.post(f"{BASE_URL}/api/auth/logout", timeout=20)


@pytest.fixture
def control(client):
    response = client.post(f"{BASE_URL}/api/controls", json={"name": f"TEST_{uuid.uuid4().hex[:8]}"}, timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["control_id"] and "_id" not in data
    return data


@pytest.fixture
def registered_account():
    user_id = f"TEST_owner_{uuid.uuid4().hex[:8]}"
    token = f"TEST_token_{uuid.uuid4().hex}"
    email = f"{user_id}@example.com"
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    db.users.insert_one({"user_id": user_id, "email": email, "name": "TEST Owner"})
    db.user_sessions.insert_one({"user_id": user_id, "session_token": token,
                                 "expires_at": "2099-01-01T00:00:00+00:00"})
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    yield {"user_id": user_id, "email": email, "session": session, "db": db}
    owned_ids = [item["control_id"] for item in db.controls.find({"owner_id": user_id}, {"control_id": 1})]
    if owned_ids:
        db.transactions.delete_many({"control_id": {"$in": owned_ids}})
        db.tags.delete_many({"control_id": {"$in": owned_ids}})
        db.ai_insights.delete_many({"control_id": {"$in": owned_ids}})
        db.members.delete_many({"control_id": {"$in": owned_ids}})
        db.controls.delete_many({"control_id": {"$in": owned_ids}})
    db.members.delete_many({"user_id": user_id})
    db.user_sessions.delete_many({"user_id": user_id})
    db.users.delete_many({"user_id": user_id})
    mongo.close()


def test_auth_me_requires_session():
    response = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 401


def test_auth_me_returns_demo_without_mongo_id(client):
    response = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["email"].startswith("demo+")
    assert data["is_demo"] is True
    assert "_id" not in data


def test_demo_sessions_have_independent_users_and_controls():
    first = requests.Session()
    second = requests.Session()
    try:
        first_login = first.post(f"{BASE_URL}/api/auth/demo", timeout=20)
        second_login = second.post(f"{BASE_URL}/api/auth/demo", timeout=20)
        assert first_login.status_code == second_login.status_code == 200
        first_token = first.cookies.get("session_token")
        second_token = second.cookies.get("session_token")
        assert first_token and second_token
        first.headers.update({"Authorization": f"Bearer {first_token}"})
        second.headers.update({"Authorization": f"Bearer {second_token}"})
        first_user = first_login.json()
        second_user = second_login.json()
        assert first_user["user_id"] != second_user["user_id"]
        assert first_user["email"] != second_user["email"]

        created = first.post(
            f"{BASE_URL}/api/controls", json={"name": "TEST isolated demo"}, timeout=20
        )
        assert created.status_code == 200
        second_controls = second.get(f"{BASE_URL}/api/controls", timeout=20)
        assert second_controls.status_code == 200
        assert all(item["control_id"] != created.json()["control_id"] for item in second_controls.json())
    finally:
        first.post(f"{BASE_URL}/api/auth/logout", timeout=20)
        second.post(f"{BASE_URL}/api/auth/logout", timeout=20)


def test_legacy_shared_demo_session_is_revoked():
    token = f"TEST_legacy_demo_{uuid.uuid4().hex}"
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    db.user_sessions.insert_one({
        "user_id": "user_demo",
        "session_token": token,
        "expires_at": "2099-01-01T00:00:00+00:00",
    })
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    try:
        response = session.get(f"{BASE_URL}/api/auth/me", timeout=20)
        assert response.status_code == 401
        assert db.user_sessions.find_one({"session_token": token}) is None
    finally:
        db.user_sessions.delete_many({"session_token": token})
        mongo.close()


def test_demo_user_cannot_invite_people(client, control, registered_account):
    response = client.post(
        f"{BASE_URL}/api/controls/{control['control_id']}/members",
        json={"email": registered_account["email"], "role": "viewer"},
        timeout=20,
    )
    assert response.status_code == 403


def test_demo_logout_removes_demo_control_data(client):
    user = client.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    created = client.post(f"{BASE_URL}/api/controls", json={"name": "TEST ephemeral demo"}, timeout=20)
    assert created.status_code == 200
    control_id = created.json()["control_id"]
    assert client.post(f"{BASE_URL}/api/controls/{control_id}/demo-data", timeout=20).status_code == 200
    assert client.post(f"{BASE_URL}/api/auth/logout", timeout=20).status_code == 200
    assert client.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 401

    mongo = MongoClient(os.environ["MONGO_URL"])
    try:
        db = mongo[os.environ["DB_NAME"]]
        assert db.users.find_one({"user_id": user["user_id"]}) is None
        assert db.controls.find_one({"control_id": control_id}) is None
        assert db.transactions.count_documents({"control_id": control_id}) == 0
    finally:
        mongo.close()


def test_untrusted_origin_cannot_use_authenticated_api(client):
    response = client.post(
        f"{BASE_URL}/api/controls",
        json={"name": "TEST blocked origin"},
        headers={"Origin": "https://attacker.example"},
        timeout=20,
    )
    assert response.status_code == 403


def test_member_roles_are_limited_and_owner_can_revoke_access(registered_account):
    owner = registered_account["session"]
    created_control = owner.post(f"{BASE_URL}/api/controls", json={"name": "TEST member roles"}, timeout=20).json()
    cid = created_control["control_id"]
    invited_user_id = f"TEST_viewer_{uuid.uuid4().hex[:8]}"
    invited_email = f"{invited_user_id}@example.com"
    token = f"TEST_token_{uuid.uuid4().hex}"
    db = registered_account["db"]
    db.users.insert_one({"user_id": invited_user_id, "email": invited_email, "name": "TEST Viewer"})
    db.user_sessions.insert_one({"user_id": invited_user_id, "session_token": token,
                                 "expires_at": "2099-01-01T00:00:00+00:00"})
    viewer = requests.Session()
    viewer.headers.update({"Authorization": f"Bearer {token}"})

    invalid_role = owner.post(
        f"{BASE_URL}/api/controls/{cid}/members",
        json={"email": invited_email, "role": "owner"}, timeout=20,
    )
    assert invalid_role.status_code == 422

    added = owner.post(
        f"{BASE_URL}/api/controls/{cid}/members",
        json={"email": invited_email, "role": "viewer"}, timeout=20,
    )
    assert added.status_code == 200
    assert viewer.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).status_code == 200
    assert owner.delete(
        f"{BASE_URL}/api/controls/{cid}/members/{invited_user_id}", timeout=20
    ).status_code == 200
    assert viewer.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).status_code == 403
    assert owner.delete(f"{BASE_URL}/api/controls/{cid}", timeout=20).status_code == 200
    db.members.delete_many({"user_id": invited_user_id})
    db.user_sessions.delete_many({"user_id": invited_user_id})
    db.users.delete_many({"user_id": invited_user_id})


def test_bearer_logout_invalidates_same_token():
    """Verify Bearer-only sessions are accepted, then invalidated by logout."""
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/demo", timeout=20)
    assert login.status_code == 200
    token = session.cookies.get("session_token")
    session.cookies.clear()
    session.headers.update({"Authorization": f"Bearer {token}"})
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 200
    assert session.post(f"{BASE_URL}/api/auth/logout", timeout=20).status_code == 200
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 401


def test_cookie_logout_clears_session():
    """Verify cookie sessions are invalidated and the cookie is cleared on logout."""
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/demo", timeout=20)
    assert login.status_code == 200
    assert "secure" in login.headers.get("set-cookie", "").lower()
    token = session.cookies.get("session_token")
    session.cookies.clear()
    # Simulate the browser sending its Secure cookie over the local HTTP test URL.
    session.cookies.set("session_token", token, secure=False)
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 200
    assert session.post(f"{BASE_URL}/api/auth/logout", timeout=20).status_code == 200
    assert session.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 401


def test_oauth_invalid_session_returns_auth_error():
    """Verify an invalid managed OAuth session fails cleanly rather than crashing."""
    response = requests.post(f"{BASE_URL}/api/auth/session", json={"session_id": "TEST_invalid_oauth_session"}, timeout=30)
    assert response.status_code == 401
    assert response.json().get("detail")


def test_control_and_membership_persist(client, control):
    response = client.get(f"{BASE_URL}/api/controls", timeout=20)
    assert response.status_code == 200
    assert any(item["control_id"] == control["control_id"] for item in response.json())
    members = client.get(f"{BASE_URL}/api/controls/{control['control_id']}/members", timeout=20)
    assert members.status_code == 200
    assert members.json()[0]["role"] == "owner"


def test_tag_required_and_transaction_precision(client, control):
    cid = control["control_id"]
    tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST alimentação"}, timeout=20)
    assert tag.status_code == 200
    tag_id = tag.json()["tag_id"]
    invalid = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "10.00", "date": "01/06/2025", "description": "TEST invalid", "tag_id": "missing"
    }, timeout=20)
    assert invalid.status_code == 422
    created = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "income", "amount": "1234.567", "date": "02/06/2025", "description": "TEST precision", "tag_id": tag_id
    }, timeout=20)
    assert created.status_code == 200
    assert created.json()["amount"] == "1234.57"
    assert created.json()["date"] == "2025-06-02"

    rounded_half_up = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "1.005", "date": "2025-06-03", "description": "TEST rounding", "tag_id": tag_id
    }, timeout=20)
    assert rounded_half_up.status_code == 200
    assert rounded_half_up.json()["amount"] == "1.01"

    invalid_amount = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "NaN", "date": "2025-06-03", "description": "TEST invalid amount", "tag_id": tag_id
    }, timeout=20)
    assert invalid_amount.status_code == 422

    invalid_date = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "1.00", "date": "31/02/2025", "description": "TEST invalid date", "tag_id": tag_id
    }, timeout=20)
    assert invalid_date.status_code == 422
    listed = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20)
    assert listed.status_code == 200
    assert all("_id" not in item for item in listed.json())


def test_demo_data_add_and_remove(client, control):
    cid = control["control_id"]
    assert client.post(f"{BASE_URL}/api/controls/{cid}/demo-data", timeout=20).status_code == 200
    assert client.post(f"{BASE_URL}/api/controls/{cid}/demo-data", timeout=20).status_code == 200
    transactions = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json()
    assert len(transactions) == 4

    salary_tag = next(tag for tag in client.get(f"{BASE_URL}/api/controls/{cid}/tags", timeout=20).json() if tag["name"] == "Salário")
    real_transaction = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "income", "amount": "10.00", "date": "2025-06-04",
        "description": "TEST same note as demo", "tag_id": salary_tag["tag_id"],
        "note": "Dado de demonstração",
    }, timeout=20).json()

    assert client.delete(f"{BASE_URL}/api/controls/{cid}/demo-data", timeout=20).status_code == 200
    remaining = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json()
    assert [item["transaction_id"] for item in remaining] == [real_transaction["transaction_id"]]


def test_transaction_pagination_and_csv_export(client, control):
    cid = control["control_id"]
    tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST export"}, timeout=20).json()
    for amount, description in [("5.00", "TEST five"), ("20.00", "=HYPERLINK(\"https://example.com\")"), ("10.00", "TEST ten")]:
        response = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
            "type": "expense", "amount": amount, "date": "2025-07-01",
            "description": description, "tag_id": tag["tag_id"],
        }, timeout=20)
        assert response.status_code == 200

    first_page = client.get(f"{BASE_URL}/api/controls/{cid}/transactions?page=1&page_size=2&sort=amount", timeout=20)
    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert [item["amount"] for item in first_page.json()["items"]] == ["20.00", "10.00"]
    second_page = client.get(f"{BASE_URL}/api/controls/{cid}/transactions?page=2&page_size=2", timeout=20).json()
    assert len(second_page["items"]) == 1

    export = client.get(f"{BASE_URL}/api/controls/{cid}/transactions/export", timeout=20)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "'=HYPERLINK" in export.text


def test_financial_summary_aggregates_all_matching_transactions(client, control):
    cid = control["control_id"]
    income_tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST summary income"}, timeout=20).json()
    expense_tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST summary expense"}, timeout=20).json()
    records = [
        {"type": "income", "amount": "100.10", "date": "2025-07-02", "description": "TEST summary salary", "tag_id": income_tag["tag_id"]},
        {"type": "expense", "amount": "33.33", "date": "2025-07-03", "description": "TEST summary food", "tag_id": expense_tag["tag_id"]},
        {"type": "expense", "amount": "10.00", "date": "2025-08-01", "description": "TEST summary next month", "tag_id": expense_tag["tag_id"]},
    ]
    for record in records:
        assert client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json=record, timeout=20).status_code == 200

    all_summary = client.get(f"{BASE_URL}/api/controls/{cid}/summary", timeout=20).json()
    assert all_summary["entries_total"] == "100.10"
    assert all_summary["expenses_total"] == "43.33"
    assert all_summary["transaction_count"] == 3
    assert len(all_summary["trend"]) == 3

    month_summary = client.get(
        f"{BASE_URL}/api/controls/{cid}/summary?date_from=2025-07-01&date_to=2025-08-01",
        timeout=20,
    ).json()
    assert month_summary["entries_total"] == "100.10"
    assert month_summary["expenses_total"] == "33.33"
    assert month_summary["transaction_count"] == 2


def test_financial_summary_counts_transactions_past_legacy_list_limit(client, control):
    cid = control["control_id"]
    user = client.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    records = [{
        "transaction_id": f"TEST_bulk_{uuid.uuid4().hex}",
        "control_id": cid,
        "type": "income",
        "amount": "0.01",
        "date": "2026-09-01",
        "description": "TEST aggregate beyond list limit",
        "tag_id": "TEST_no_tag_needed_for_income",
        "user_id": user["user_id"],
        "user_name": user["name"],
        "created_at": "2026-09-01T00:00:00+00:00",
    } for _ in range(1001)]
    try:
        db.transactions.insert_many(records)
        summary = client.get(f"{BASE_URL}/api/controls/{cid}/summary", timeout=30)
        assert summary.status_code == 200
        assert summary.json()["transaction_count"] == 1001
        assert summary.json()["entries_total"] == "10.01"
        page = client.get(
            f"{BASE_URL}/api/controls/{cid}/transactions?page=1&page_size=25", timeout=30
        ).json()
        assert page["total"] == 1001
        assert len(page["items"]) == 25
    finally:
        db.transactions.delete_many({"control_id": cid})
        mongo.close()


def test_delete_control_requires_removing_other_members_first(registered_account):
    owner = registered_account["session"]
    cid = owner.post(f"{BASE_URL}/api/controls", json={"name": "TEST shared control"}, timeout=20).json()["control_id"]
    invited_user_id = f"TEST_member_{uuid.uuid4().hex[:8]}"
    invited_email = f"{invited_user_id}@example.com"
    registered_account["db"].users.insert_one({"user_id": invited_user_id, "email": invited_email, "name": "TEST Member"})
    assert owner.post(
        f"{BASE_URL}/api/controls/{cid}/members",
        json={"email": invited_email, "role": "viewer"}, timeout=20,
    ).status_code == 200
    assert owner.delete(f"{BASE_URL}/api/controls/{cid}", timeout=20).status_code == 409
    assert owner.delete(
        f"{BASE_URL}/api/controls/{cid}/members/{invited_user_id}", timeout=20
    ).status_code == 200
    assert owner.delete(f"{BASE_URL}/api/controls/{cid}", timeout=20).status_code == 200
    assert owner.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).status_code == 403
    registered_account["db"].users.delete_many({"user_id": invited_user_id})


def test_account_deletion_transfers_owned_shared_controls_and_preserves_shared_data(registered_account):
    owner = registered_account["session"]
    db = registered_account["db"]
    user_id = registered_account["user_id"]
    email = registered_account["email"]
    user_control = owner.post(
        f"{BASE_URL}/api/controls", json={"name": "TEST account deletion"}, timeout=20
    ).json()
    owned_id = user_control["control_id"]
    tag = owner.post(
        f"{BASE_URL}/api/controls/{owned_id}/tags", json={"name": "TEST account tag"}, timeout=20
    ).json()
    owned_tx = owner.post(
        f"{BASE_URL}/api/controls/{owned_id}/transactions",
        json={"type": "expense", "amount": "12.34", "date": "2026-09-01",
              "description": "TEST owned data", "tag_id": tag["tag_id"]}, timeout=20,
    ).json()
    solo_control = owner.post(
        f"{BASE_URL}/api/controls", json={"name": "TEST solo account data"}, timeout=20
    ).json()
    solo_id = solo_control["control_id"]
    solo_tag = owner.post(
        f"{BASE_URL}/api/controls/{solo_id}/tags", json={"name": "TEST solo account tag"}, timeout=20
    ).json()
    solo_tx = owner.post(
        f"{BASE_URL}/api/controls/{solo_id}/transactions",
        json={"type": "expense", "amount": "7.89", "date": "2026-09-02",
              "description": "TEST solo record", "tag_id": solo_tag["tag_id"]}, timeout=20,
    ).json()

    external_owner = f"TEST_external_owner_{uuid.uuid4().hex[:8]}"
    external_control = f"TEST_external_control_{uuid.uuid4().hex[:8]}"
    external_tag = f"TEST_external_tag_{uuid.uuid4().hex[:8]}"
    external_tx = f"TEST_external_tx_{uuid.uuid4().hex[:8]}"
    blocking_member = None
    try:
        db.users.insert_one({"user_id": external_owner, "email": f"{external_owner}@example.com", "name": "TEST External Owner"})
        db.controls.insert_one({"control_id": external_control, "owner_id": external_owner, "name": "TEST retained shared control"})
        db.members.insert_many([
            {"control_id": external_control, "user_id": external_owner, "email": f"{external_owner}@example.com", "role": "owner"},
            {"control_id": external_control, "user_id": user_id, "email": email, "role": "viewer"},
        ])
        db.tags.insert_one({"tag_id": external_tag, "control_id": external_control, "name": "TEST shared tag"})
        db.transactions.insert_one({
            "transaction_id": external_tx, "control_id": external_control, "tag_id": external_tag,
            "type": "expense", "amount": "45.00", "date": "2026-09-01", "description": "TEST shared record",
            "user_id": user_id, "user_name": "TEST Owner",
        })

        # An incorrect confirmation is rejected without changing ownership or sessions.
        mismatch = owner.delete(f"{BASE_URL}/api/auth/account", json={"email": "wrong@example.com"}, timeout=20)
        assert mismatch.status_code == 422
        assert db.users.find_one({"user_id": user_id})

        # Shared ownership must be transferred explicitly before closing the account.
        blocking_member = f"TEST_blocking_member_{uuid.uuid4().hex[:8]}"
        db.users.insert_one({"user_id": blocking_member, "email": f"{blocking_member}@example.com", "name": "TEST New Owner"})
        db.members.insert_one({"control_id": owned_id, "user_id": blocking_member, "role": "viewer"})
        blocked = owner.delete(f"{BASE_URL}/api/auth/account", json={"email": email}, timeout=20)
        assert blocked.status_code == 409
        assert db.controls.find_one({"control_id": owned_id, "deleting": {"$exists": False}})
        assert db.users.find_one({"user_id": user_id})

        deleted = owner.delete(
            f"{BASE_URL}/api/auth/account",
            json={"email": email, "ownership_transfers": {owned_id: blocking_member}}, timeout=20,
        )
        assert deleted.status_code == 200
        assert db.users.find_one({"user_id": user_id}) is None
        assert db.user_sessions.find_one({"user_id": user_id}) is None
        assert db.controls.find_one({"control_id": owned_id, "owner_id": blocking_member, "deleting": {"$ne": True}})
        assert db.members.find_one({"control_id": owned_id, "user_id": blocking_member, "role": "owner"})
        assert db.members.find_one({"control_id": owned_id, "user_id": user_id}) is None
        transferred_tx = db.transactions.find_one({"transaction_id": owned_tx["transaction_id"]})
        assert transferred_tx and "user_id" not in transferred_tx
        assert transferred_tx["user_name"] == "Usuário removido"
        assert db.tags.find_one({"tag_id": tag["tag_id"]})
        assert db.controls.find_one({"control_id": solo_id}) is None
        assert db.transactions.find_one({"transaction_id": solo_tx["transaction_id"]}) is None
        assert db.tags.find_one({"tag_id": solo_tag["tag_id"]}) is None
        assert db.controls.find_one({"control_id": external_control, "owner_id": external_owner})
        assert db.members.find_one({"control_id": external_control, "user_id": user_id}) is None
        retained = db.transactions.find_one({"transaction_id": external_tx})
        assert retained
        assert "user_id" not in retained
        assert retained["user_name"] == "Usuário removido"

    finally:
        for control_id in (external_control, owned_id, solo_id):
            db.transactions.delete_many({"control_id": control_id})
            db.tags.delete_many({"control_id": control_id})
            db.ai_insights.delete_many({"control_id": control_id})
            db.members.delete_many({"control_id": control_id})
            db.controls.delete_one({"control_id": control_id})
        user_ids = [external_owner]
        if blocking_member:
            user_ids.append(blocking_member)
        db.users.delete_many({"user_id": {"$in": user_ids}})

def test_delete_transaction_requires_owner(client, control):
    cid = control["control_id"]
    tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST delete"}, timeout=20).json()
    tx = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "1.00", "date": "03/06/2025", "description": "TEST delete", "tag_id": tag["tag_id"]
    }, timeout=20).json()
    viewer_id = f"TEST_viewer_{uuid.uuid4().hex[:8]}"
    viewer_token = f"TEST_token_{uuid.uuid4().hex}"
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    db.users.insert_one({"user_id": viewer_id, "email": f"{viewer_id}@example.com", "name": "TEST Viewer"})
    db.user_sessions.insert_one({"user_id": viewer_id, "session_token": viewer_token,
                                 "expires_at": "2099-01-01T00:00:00+00:00"})
    db.members.insert_one({"control_id": cid, "user_id": viewer_id,
                           "email": f"{viewer_id}@example.com", "role": "viewer"})
    viewer = requests.Session()
    viewer.headers.update({"Authorization": f"Bearer {viewer_token}"})
    try:
        response = viewer.delete(
            f"{BASE_URL}/api/controls/{cid}/transactions/{tx['transaction_id']}", timeout=20
        )
        assert response.status_code == 403
        persisted = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json()
        assert any(item["transaction_id"] == tx["transaction_id"] for item in persisted)
        assert client.delete(
            f"/api/controls/{cid}/transactions/{tx['transaction_id']}", timeout=20
        ).status_code == 200
    finally:
        db.members.delete_many({"user_id": viewer_id})
        db.user_sessions.delete_many({"user_id": viewer_id})
        db.users.delete_many({"user_id": viewer_id})
        mongo.close()


def test_update_transaction_preserves_session_and_precision(client, control):
    """Verify PUT updates the record, keeps the authenticated session, and quantizes cents."""
    cid = control["control_id"]
    tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST update"}, timeout=20).json()
    tx = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "10.00", "date": "03/06/2025",
        "description": "TEST before update", "tag_id": tag["tag_id"]
    }, timeout=20).json()
    updated = client.put(f"{BASE_URL}/api/controls/{cid}/transactions/{tx['transaction_id']}", json={
        "type": "income", "amount": "123.456", "date": "04/06/2025",
        "description": "TEST after update", "tag_id": tag["tag_id"], "note": "updated"
    }, timeout=20)
    assert updated.status_code == 200
    assert updated.json()["amount"] == "123.46"
    assert updated.json()["description"] == "TEST after update"
    assert client.get(f"{BASE_URL}/api/auth/me", timeout=20).status_code == 200
    persisted = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json()
    assert next(item for item in persisted if item["transaction_id"] == tx["transaction_id"])["amount"] == "123.46"


def test_viewer_permissions_and_control_isolation(client, control):
    """Verify control membership isolation and viewer read-only permissions."""
    cid = control["control_id"]
    assert client.get(f"{BASE_URL}/api/controls/control_missing/members", timeout=20).status_code == 403

    viewer_id = f"TEST_viewer_{uuid.uuid4().hex[:8]}"
    viewer_token = f"TEST_token_{uuid.uuid4().hex}"
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    db.users.insert_one({"user_id": viewer_id, "email": f"{viewer_id}@example.com", "name": "TEST Viewer"})
    db.user_sessions.insert_one({"user_id": viewer_id, "session_token": viewer_token,
                                 "expires_at": "2099-01-01T00:00:00+00:00"})
    db.members.insert_one({"control_id": cid, "user_id": viewer_id,
                           "email": f"{viewer_id}@example.com", "role": "viewer"})
    viewer = requests.Session()
    viewer.headers.update({"Authorization": f"Bearer {viewer_token}", "Content-Type": "application/json"})
    try:
        assert viewer.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).status_code == 200
        tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST viewer tag"}, timeout=20).json()
        denied_tag = viewer.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST denied"}, timeout=20)
        assert denied_tag.status_code == 403
        denied_tx = viewer.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
            "type": "expense", "amount": "1.00", "date": "01/01/2026",
            "description": "TEST denied", "tag_id": tag["tag_id"]}, timeout=20)
        assert denied_tx.status_code == 403
    finally:
        db.members.delete_many({"user_id": viewer_id})
        db.user_sessions.delete_many({"user_id": viewer_id})
        db.users.delete_many({"user_id": viewer_id})
        mongo.close()
