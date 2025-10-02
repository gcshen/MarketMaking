import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_start_session():
    resp = client.post("/v1/fermi/sessions", json={"question": "How many breaths per day?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["question"] == "How many breaths per day?"
