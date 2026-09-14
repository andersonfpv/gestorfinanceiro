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
    assert session.post(f"{BASE_URL}/api/auth/demo", timeout=20).status_code == 200
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


def test_ai_insights_requires_authentication():
    response = requests.get(
        f"{BASE_URL}/api/controls/control_missing/ai/insights", timeout=20
    )
    assert response.status_code == 401


def test_ai_insights_requires_control_membership():
    session = requests.Session()
    assert session.post(f"{BASE_URL}/api/auth/demo", timeout=20).status_code == 200
    response = session.get(
        f"{BASE_URL}/api/controls/control_not_owned/ai/insights", timeout=20
    )
    assert response.status_code == 403


def test_ai_insights_streams_done_and_persists_aggregates(session_and_control):
    session, control_id = session_and_control
    response = session.get(
        f"{BASE_URL}/api/controls/{control_id}/ai/insights", stream=True, timeout=90
    )
    assert response.status_code == 200
    events = []
    for line in response.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    assert any(event.get("text") for event in events)
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
        assert "TEST_PRIVATE_DESCRIPTION" not in insight["content"]
        assert "TEST_PRIVATE_NOTE" not in insight["content"]
    finally:
        mongo.close()