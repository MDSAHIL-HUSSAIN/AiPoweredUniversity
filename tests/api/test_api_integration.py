import json
import os
from pathlib import Path

os.environ["MOCK_LLM"] = "true"
os.environ["CHROMA_DISABLED"] = "true"
os.environ["SQLITE_PATH"] = str(Path(".tmp/api-integration.db"))

from fastapi.testclient import TestClient

from main import app


def test_health_and_policy_question():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["api"] is True

        answer = client.post(
            "/ask",
            json={
                "question": "What is the minimum attendance requirement?",
                "as_of_date": "2026-10-06",
            },
        )
        assert answer.status_code == 200
        body = answer.json()
        assert body["answer_type"] == "retrieved_fact"
        assert body["citations"]

        audit = client.get(f"/audit/{body['trace_id']}")
        assert audit.status_code == 200
        assert audit.json()["question"] == "What is the minimum attendance requirement?"


def test_personal_question_uses_header_and_real_tool():
    with TestClient(app) as client:
        answer = client.post(
            "/ask",
            headers={"X-Student-Id": "S1001"},
            json={
                "question": "Am I eligible for the end-semester exam in CS201?",
                "as_of_date": "2026-10-06",
            },
        )
        assert answer.status_code == 200
        body = answer.json()
        assert body["answer_type"] == "calculated"
        assert body["tools_invoked"][0]["tool"] == "check_exam_eligibility"


def test_ingest_text_and_list_source():
    metadata = {
        "doc_id": "TEST-NOTICE-1",
        "title": "Test Notice",
        "issuer": "Registrar",
        "authority_level": 2,
        "doc_type": "notice",
        "version": "1.0",
        "effective_from": "2026-10-01",
        "provenance": "API integration test",
        "synthetic": True,
    }
    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            files={"file": ("notice.txt", b"Section 1\nTest policy text.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )
        assert response.status_code == 200
        assert response.json()["chunks_indexed"] >= 1
        listed = client.get("/sources")
        assert listed.status_code == 200
        assert any(item["doc_id"] == "TEST-NOTICE-1" for item in listed.json())
