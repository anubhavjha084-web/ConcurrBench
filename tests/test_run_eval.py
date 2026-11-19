"""
Unit tests for run_eval.py functions and task loaders.
"""

import json
import os
import sys
import argparse
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_eval import (
    load_tasks,
    build_prompt,
    call_model,
    call_mock,
    call_openai,
    call_anthropic,
    call_google,
    generate_summary,
    MODEL_CONFIGS,
    PROVIDERS,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_DIR = os.path.join(BASE_DIR, "tasks")
RESULTS_DIR = os.path.join(BASE_DIR, "results")


class TestTaskLoading:
    def test_load_tasks_count(self):
        tasks = load_tasks(TASKS_DIR)
        assert len(tasks) == 7

    def test_tasks_have_required_fields(self):
        tasks = load_tasks(TASKS_DIR)
        required = {"task_id", "title", "domain", "difficulty", "scenario", "code", "instruction"}
        for t in tasks:
            assert required.issubset(t.keys()), f"Task {t.get('task_id')} missing fields"

    def test_tasks_sorted_order(self):
        tasks = load_tasks(TASKS_DIR)
        task_ids = [t["task_id"] for t in tasks]
        assert task_ids == sorted(task_ids)


class TestPromptBuilding:
    def test_build_prompt_contains_scenario_and_code(self):
        task = {
            "title": "Sample Task",
            "scenario": "A multithreaded test scenario",
            "code": "print('concurrency')",
            "instruction": "Find the race condition",
        }
        prompt = build_prompt(task)
        assert "## Task: Sample Task" in prompt
        assert "A multithreaded test scenario" in prompt
        assert "print('concurrency')" in prompt
        assert "Find the race condition" in prompt
        assert "Return ONLY a valid JSON object" in prompt


class TestModelDispatcher:
    def test_call_mock_returns_valid_json(self):
        task_prompt = "## Task: Bank Account Transfer System — Deadlock and Atomicity"
        config = MODEL_CONFIGS["mock-model"]
        content, elapsed, usage = call_mock(task_prompt, config)
        assert elapsed >= 0.0
        assert usage["total_tokens"] > 0
        parsed = json.loads(content)
        assert "bugs" in parsed
        assert isinstance(parsed["bugs"], list)

    def test_call_model_dispatches_mock(self):
        config = MODEL_CONFIGS["mock-model"]
        content, elapsed, usage = call_model("## Task: Bank Account Transfer System", config)
        assert "bugs" in json.loads(content)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            call_model("test", {"provider": "invalid_provider"})

    def test_call_openai_mocked(self, monkeypatch):
        from unittest.mock import MagicMock
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content='{"bugs": []}'))]
        fake_response.usage.prompt_tokens = 10
        fake_response.usage.completion_tokens = 5
        fake_response.usage.total_tokens = 15

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response

        monkeypatch.setattr("openai.OpenAI", lambda: mock_client)
        content, elapsed, usage = call_openai("test prompt", MODEL_CONFIGS["gpt-4o"])
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 15

    def test_call_anthropic_mocked(self, monkeypatch):
        from unittest.mock import MagicMock
        fake_response = MagicMock()
        fake_response.content = [MagicMock(text='{"bugs": []}')]
        fake_response.usage.input_tokens = 12
        fake_response.usage.output_tokens = 6

        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_response

        monkeypatch.setattr("anthropic.Anthropic", lambda: mock_client)
        content, elapsed, usage = call_anthropic("test prompt", MODEL_CONFIGS["claude-sonnet-4-20250514"])
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 18

    def test_call_google_mocked(self, monkeypatch):
        from unittest.mock import MagicMock
        fake_response = MagicMock()
        fake_response.text = '{"bugs": []}'
        fake_response.usage_metadata.prompt_token_count = 14
        fake_response.usage_metadata.candidates_token_count = 7
        fake_response.usage_metadata.total_token_count = 21

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = fake_response

        monkeypatch.setattr("google.genai.Client", lambda: mock_client)
        content, elapsed, usage = call_google("test prompt", MODEL_CONFIGS["gemini-2.5-flash"])
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 21


class TestSummaryGeneration:
    def test_generate_summary_output(self, tmp_path):
        sample_results = {
            "mock-model": {
                "model": "mock-model",
                "trials": 2,
                "total_tokens": 5000,
                "tasks": {
                    "task_01_bank_transfer": {
                        "mean_score": 1.0,
                        "min_score": 1.0,
                        "max_score": 1.0,
                        "pass_rate_80pct": 1.0,
                        "pass_at_k": True,
                        "pass_all_k": True,
                        "num_trials": 2,
                        "trials": [
                            {"score": 1.0, "missed_bugs": []},
                            {"score": 1.0, "missed_bugs": []},
                        ],
                    }
                },
            }
        }
        generate_summary(sample_results, str(tmp_path), trials=2)

        summary_txt = tmp_path / "summary.txt"
        summary_json = tmp_path / "summary.json"
        assert summary_txt.exists()
        assert summary_json.exists()

        content = summary_txt.read_text(encoding="utf-8")
        assert "mock-model" in content
        assert "100.0%" in content

        with open(summary_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "models" in data
        assert "mock-model" in data["models"]
        assert data["models"]["mock-model"]["overall_mean_score"] == 1.0
