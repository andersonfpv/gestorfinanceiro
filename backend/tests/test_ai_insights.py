import json
import os
import uuid

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def session_and_control():
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/demo", timeout=20)
    assert login.status_code == 200
    session.headers.update({"Authorization": f"Bearer {session.cookies.get('session_token')}"})
    control = session.post(
        f"{BASE_URL}/api/controls",
        json={"name": f"TEST_AI_{uuid.uuid4().hex[:8]}"},
        timeout=20,
    ).json()
    tag = session.post(
        f"{BASE_URL}/api/controls/{control['control_id']}/tags",
        json={"name": f"TEST_AI_TAG_{uuid.uuid4().hex[:6]}"},
        timeout=20,
    ).json()
    session.post(
        f"{BASE_URL}/api/controls/{control['control_id']}/transactions",
        json={
            "type": "income", "amount": "1000.00", "date": "01/06/2026",
            "description": "TEST_PRIVATE_DESCRIPTION", "note": "TEST_PRIVATE_NOTE",
            "tag_id": tag["tag_id"],
        },
        timeout=20,
    ).raise_for_status()
    yield session, control["control_id"]
    session.post(f"{BASE_URL}/api/auth/logout", timeout=20)


def test_ai_insights_requires_authentication():
    response = requests.post(
        f"{BASE_URL}/api/controls/control_missing/ai/insights", timeout=20
    )
    assert response.status_code == 401


def test_ai_insights_requires_control_membership():
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/demo", timeout=20)
    assert login.status_code == 200
    session.headers.update({"Authorization": f"Bearer {session.cookies.get('session_token')}"})
    try:
        response = session.post(
            f"{BASE_URL}/api/controls/control_not_owned/ai/insights", timeout=20
        )
        assert response.status_code == 403
    finally:
        session.post(f"{BASE_URL}/api/auth/logout", timeout=20)


def test_ai_insights_streams_done_and_persists_aggregates(session_and_control):
    session, control_id = session_and_control
    response = session.post(
        f"{BASE_URL}/api/controls/{control_id}/ai/insights", stream=True, timeout=90
    )
    assert response.status_code == 200
    events = []
    for line in response.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    assert any(event.get("text") for event in events)
    generated_text = "".join(event.get("text", "") for event in events)
    assert {event.get("done") for event in events} >= {True}
    assert not any("error" in event for event in events)

    mongo = MongoClient(os.environ["MONGO_URL"])
    try:
        insight = mongo[os.environ["DB_NAME"]].ai_insights.find_one(
            {"control_id": control_id}, {"_id": 0}
        )
        assert insight["summary"] == {
            "entries_total": "1000.00",
            "expenses_total": "0.00",
            "transaction_count": 1,
            "expenses_by_tag": {},
        }
        assert insight["summary_hash"]
        assert "TEST_PRIVATE_DESCRIPTION" not in insight["content"]
        assert "TEST_PRIVATE_NOTE" not in insight["content"]
        assert insight["content"] == generated_text
    finally:
        mongo.close()

    cached = session.post(
        f"{BASE_URL}/api/controls/{control_id}/ai/insights", stream=True, timeout=20
    )
    assert cached.status_code == 200
    cached_events = [json.loads(line[6:]) for line in cached.iter_lines(decode_unicode=True) if line.startswith("data: ")]
    assert "".join(event.get("text", "") for event in cached_events) == generated_text
    assert any(event.get("done") for event in cached_events)

    tags = session.get(f"{BASE_URL}/api/controls/{control_id}/tags", timeout=20).json()
    changed = session.post(
        f"{BASE_URL}/api/controls/{control_id}/transactions",
        json={"type": "expense", "amount": "25.00", "date": "2026-09-02",
              "description": "TEST changed aggregate", "tag_id": tags[0]["tag_id"]}, timeout=20,
    )
    assert changed.status_code == 200
    limited = session.post(
        f"{BASE_URL}/api/controls/{control_id}/ai/insights", timeout=20
    )
    assert limited.status_code == 429
    assert "10 minutos" in limited.json()["detail"]
