"""
Unit tests for the ConcurrencyBugBench FastAPI endpoints.
"""

import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["tasks_loaded"] == 7

    def test_health_has_version(self):
        body = client.get("/health").json()
        assert "version" in body


# ── Tasks ─────────────────────────────────────────────────────────


class TestTasks:
    def test_list_tasks(self):
        resp = client.get("/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 7

    def test_get_task_by_id(self):
        resp = client.get("/tasks/task_01_bank_transfer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "task_01_bank_transfer"

    def test_get_task_not_found(self):
        resp = client.get("/tasks/nonexistent")
        assert resp.status_code == 404


# ── Results ───────────────────────────────────────────────────────


class TestResults:
    def test_list_results_empty(self):
        resp = client.get("/results")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_result_not_found(self):
        resp = client.get("/results/nonexistent-id")
        assert resp.status_code == 404


# ── Evaluate (auth) ──────────────────────────────────────────────


class TestEvaluateAuth:
    def test_evaluate_no_key_rejected(self):
        resp = client.post("/evaluate", json={"model": "gpt-4o", "trials": 1})
        assert resp.status_code == 403

    def test_evaluate_wrong_key_rejected(self):
        resp = client.post(
            "/evaluate",
            json={"model": "gpt-4o", "trials": 1},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_evaluate_unknown_model(self):
        resp = client.post(
            "/evaluate",
            json={"model": "nonexistent-model", "trials": 1},
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 400

    def test_evaluate_mock_model_execution(self):
        resp = client.post(
            "/evaluate",
            json={"model": "mock-model", "trials": 1, "tasks": ["task_01_bank_transfer"]},
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 200
        run_data = resp.json()
        assert run_data["status"] in ("pending", "completed")
        run_id = run_data["run_id"]

        # Retrieve result
        get_resp = client.get(f"/results/{run_id}")
        assert get_resp.status_code == 200
        completed_data = get_resp.json()
        assert completed_data["status"] == "completed"
        assert len(completed_data["tasks"]) == 1
        assert completed_data["tasks"][0]["task_id"] == "task_01_bank_transfer"
        assert completed_data["overall_mean_score"] == 1.0


# ── Metrics & Observability ──────────────────────────────────────


class TestMetrics:
    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "http_requests" in resp.text or "process_cpu_seconds" in resp.text
