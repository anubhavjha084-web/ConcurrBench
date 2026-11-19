import os
import json
from fastapi.testclient import TestClient

# Ensure the API key environment variable is set for tests
os.environ.setdefault("BENCH_API_KEY", "test-key")

from api.main import app, API_KEY_NAME, API_KEY, _available_models

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # health response contains list of available models under 'models_available'
    assert "models_available" in data
    # The mock model should always be listed
    assert "mock-model" in data["models_available"]


def test_tasks_list():
    response = client.get("/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    if tasks:
        task = tasks[0]
        for key in ["task_id", "title", "domain", "difficulty", "expected_bug_count"]:
            assert key in task


def test_task_detail_valid():
    list_resp = client.get("/tasks")
    tasks = list_resp.json()
    if not tasks:
        return  # skip if no tasks
    task_id = tasks[0]["task_id"]
    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    task = resp.json()
    for key in ["task_id", "title", "domain", "difficulty", "expected_bug_count"]:
        assert key in task


def test_task_detail_invalid():
    resp = client.get("/tasks/nonexistent-id")
    assert resp.status_code == 404


def test_evaluate_success():
    list_resp = client.get("/tasks")
    tasks = list_resp.json()
    if not tasks:
        return
    task_id = tasks[0]["task_id"]
    payload = {"model": "mock-model", "task_ids": [task_id], "trials": 1}
    headers = {API_KEY_NAME: API_KEY}
    resp = client.post("/evaluate", json=payload, headers=headers)
    # FastAPI returns 200 by default; accept either 200 or 202
    assert resp.status_code in (200, 202)
    data = resp.json()
    assert "run_id" in data
    run_id = data["run_id"]
    run_resp = client.get(f"/results/{run_id}")
    assert run_resp.status_code == 200
    run_info = run_resp.json()
    assert run_info["run_id"] == run_id


def test_evaluate_unknown_model():
    payload = {"model": "nonexistent-model", "task_ids": [], "trials": 1}
    headers = {API_KEY_NAME: API_KEY}
    resp = client.post("/evaluate", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "unknown model" in resp.text.lower()


def test_evaluate_missing_api_key():
    payload = {"model": "mock-model", "task_ids": [], "trials": 1}
    resp = client.post("/evaluate", json=payload)
    assert resp.status_code == 403