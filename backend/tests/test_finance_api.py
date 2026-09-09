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
    return session


@pytest.fixture
def control(client):
    response = client.post(f"{BASE_URL}/api/controls", json={"name": f"TEST_{uuid.uuid4().hex[:8]}"}, timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["control_id"] and "_id" not in data
    return data


def test_auth_me_requires_session():
    response = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 401


def test_auth_me_returns_demo_without_mongo_id(client):
    response = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "demo@meucontrole.test"
    assert "_id" not in data


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
    listed = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20)
    assert listed.status_code == 200
    assert all("_id" not in item for item in listed.json())


def test_demo_data_add_and_remove(client, control):
    cid = control["control_id"]
    assert client.post(f"{BASE_URL}/api/controls/{cid}/demo-data", timeout=20).status_code == 200
    transactions = client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json()
    assert len(transactions) == 4
    assert client.delete(f"{BASE_URL}/api/controls/{cid}/demo-data", timeout=20).status_code == 200
    assert client.get(f"{BASE_URL}/api/controls/{cid}/transactions", timeout=20).json() == []


def test_delete_transaction_requires_owner(client, control):
    cid = control["control_id"]
    tag = client.post(f"{BASE_URL}/api/controls/{cid}/tags", json={"name": "TEST delete"}, timeout=20).json()
    tx = client.post(f"{BASE_URL}/api/controls/{cid}/transactions", json={
        "type": "expense", "amount": "1.00", "date": "03/06/2025", "description": "TEST delete", "tag_id": tag["tag_id"]
    }, timeout=20).json()
    response = client.delete(f"{BASE_URL}/api/controls/{cid}/transactions/{tx['transaction_id']}", timeout=20)
    assert response.status_code == 200


def test_viewer_permissions_and_control_isolation(client, control):
    """Verify control membership isolation and viewer read-only permissions."""
    cid = control["control_id"]
    assert client.get(f"{BASE_URL}/api/controls/control_missing/members", timeout=20).status_code == 403

    viewer_id = f"TEST_viewer_{uuid.uuid4().hex[:8]}"
    viewer_token = f"TEST_token_{uuid.uuid4().hex}"
    mongo = MongoClient(os.environ["MONGO_URL"])
    db = mongo[os.environ["DB_NAME"]]
    db.users.insert_one({"user_id": viewer_id, "email": f"{viewer_id}@example.test", "name": "TEST Viewer"})
    db.user_sessions.insert_one({"user_id": viewer_id, "session_token": viewer_token,
                                 "expires_at": "2099-01-01T00:00:00+00:00"})
    db.members.insert_one({"control_id": cid, "user_id": viewer_id,
                           "email": f"{viewer_id}@example.test", "role": "viewer"})
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