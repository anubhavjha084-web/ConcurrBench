"""
Tests specifically designed to boost test coverage across:
- api/main.py
- graders/grader.py
- run_eval.py
to meet the >=90% project requirement.
"""

import os
import sys
import json
import asyncio
import runpy
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import api.main as api_main
from api.main import (
    app,
    _call_model,
    _available_models,
    _run_evaluation,
    lifespan,
    MODEL_CONFIGS,
    RUNS,
    RunStatus,
    RunSummary,
)
import graders.grader as grader
import run_eval


# =====================================================================
# 1. api/main.py Coverage Tests
# =====================================================================

def test_api_available_models_with_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key",
    }):
        avail = _available_models()
        assert "gpt-4o" in avail
        assert "claude-sonnet-4-20250514" in avail
        assert "gemini-2.5-flash" in avail
        assert "mock-model" in avail


def test_api_call_model_openai():
    mock_choice = MagicMock()
    mock_choice.message.content = '{"bugs": []}'
    mock_usage = MagicMock()
    mock_usage.total_tokens = 50
    mock_usage.prompt_tokens = 30
    mock_usage.completion_tokens = 20
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=mock_client):
        content, elapsed, usage = _call_model(
            "test prompt",
            {"provider": "openai", "model_id": "gpt-4o", "temperature": 0.0, "max_tokens": 100}
        )
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 50


def test_api_call_model_openai_o_series():
    mock_choice = MagicMock()
    mock_choice.message.content = '{"bugs": []}'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = None

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=mock_client):
        content, elapsed, usage = _call_model(
            "test prompt",
            {"provider": "openai", "model_id": "o3-mini", "temperature": 1.0, "max_tokens": 100}
        )
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 0


def test_api_call_model_anthropic():
    mock_content = MagicMock()
    mock_content.text = '{"bugs": []}'
    mock_usage = MagicMock()
    mock_usage.input_tokens = 25
    mock_usage.output_tokens = 25
    mock_resp = MagicMock()
    mock_resp.content = [mock_content]
    mock_resp.usage = mock_usage

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_resp

    with patch("anthropic.Anthropic", return_value=mock_client):
        content, elapsed, usage = _call_model(
            "test prompt",
            {"provider": "anthropic", "model_id": "claude-sonnet-4-20250514", "temperature": 0.0, "max_tokens": 100}
        )
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 50


def test_api_call_model_google():
    mock_resp = MagicMock()
    mock_resp.text = '{"bugs": []}'
    mock_meta = MagicMock()
    mock_meta.prompt_token_count = 10
    mock_meta.candidates_token_count = 15
    mock_meta.total_token_count = 25
    mock_resp.usage_metadata = mock_meta

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("google.genai.Client", return_value=mock_client):
        content, elapsed, usage = _call_model(
            "test prompt",
            {"provider": "google", "model_id": "gemini-2.5-flash-preview-05-20", "temperature": 0.0, "max_tokens": 100}
        )
        assert content == '{"bugs": []}'
        assert usage["total_tokens"] == 25


def test_api_call_model_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        _call_model("prompt", {"provider": "unsupported-provider"})


def test_api_lifespan():
    async def _run():
        async with lifespan(app):
            assert len(api_main.TASKS) > 0
    asyncio.run(_run())


def test_api_run_evaluation_error_handling():
    async def _run():
        run_id = "test-error-run"
        run = RunSummary(
            run_id=run_id,
            model="mock-model",
            provider="mock",
            status=RunStatus.pending,
            trials_per_task=1,
            created_at=api_main.datetime.now(api_main.timezone.utc),
        )
        RUNS[run_id] = run

        with patch("api.main._call_model", side_effect=RuntimeError("Model crashed")):
            await _run_evaluation(run_id, "mock-model", 1, ["task_01_bank_transfer"])
            assert run.status == RunStatus.completed
            assert len(run.tasks) > 0
            assert run.tasks[0].trials[0].error == "Model crashed"
    asyncio.run(_run())


def test_api_run_evaluation_fatal_error():
    async def _run():
        run_id = "test-fatal-run"
        run = RunSummary(
            run_id=run_id,
            model="mock-model",
            provider="mock",
            status=RunStatus.pending,
            trials_per_task=1,
            created_at=api_main.datetime.now(api_main.timezone.utc),
        )
        RUNS[run_id] = run

        # Throw exception inside the try block of _run_evaluation
        with patch("api.main._build_prompt", side_effect=RuntimeError("Fatal prompt error")):
            await _run_evaluation(run_id, "mock-model", 1, ["task_01_bank_transfer"])
            assert run.status == RunStatus.failed
    asyncio.run(_run())


def test_api_evaluate_missing_api_key_400():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    with patch.dict(os.environ, {}, clear=True):
        resp = client.post(
            "/evaluate",
            json={"model": "gpt-4o", "trials": 1},
            headers={"X-API-Key": "dev-key-change-me"},
        )
        assert resp.status_code == 400
        assert "No API key configured" in resp.json()["detail"]


# =====================================================================
# 2. graders/grader.py Coverage Tests
# =====================================================================

def test_grader_normalize_bug_type():
    assert grader.normalize_bug_type("race_condition") == "race_condition"
    assert grader.normalize_bug_type("unknown_nonexistent_type") == "unknown_nonexistent_type"
    assert grader.normalize_bug_type("Data Race") == "race_condition"


def test_grader_normalize_function_name():
    assert grader.normalize_function_name("self.do_action()") == "do_action"
    assert grader.normalize_function_name("MyClass.method_name") == "method_name"
    assert grader.normalize_function_name("simple_function") == "simple_function"


def test_grader_extract_json():
    assert grader.extract_json_from_response(None) is None
    assert grader.extract_json_from_response("Not json at all") is None
    assert grader.extract_json_from_response("```json\n{broken json\n```") is None
    assert grader.extract_json_from_response('```json\n{"bugs": []}\n```') == {"bugs": []}
    assert grader.extract_json_from_response('```\n{"bugs": []}\n```') == {"bugs": []}


def test_grader_match_bug_branches():
    ref_bug = {
        "function": "transfer",
        "bug_type": "deadlock",
        "explanation": "Lock ordering violation causes circular wait",
        "interleaving": "Thread 1 acquires lock A, Thread 2 acquires lock B",
    }

    assert grader.match_bug("invalid", ref_bug, "t1")[0] is False
    assert grader.match_bug({"function": 123}, ref_bug, "t1")[0] is False
    assert grader.match_bug(
        {"function": "other", "bug_type": "deadlock", "explanation": "Locks"},
        ref_bug, "t1"
    )[0] is False
    assert grader.match_bug(
        {"function": "transfer", "bug_type": "atomicity_violation", "explanation": "Locks"},
        ref_bug, "t1"
    )[0] is False

    syn_ref = dict(ref_bug, bug_type="lock_ordering")
    m_bug = {
        "function": "transfer",
        "bug_type": "circular_wait",
        "explanation": "Lock ordering causes circular wait deadlock",
        "interleaving": "Thread 1 lock A, Thread 2 lock B",
    }
    assert grader.match_bug(m_bug, syn_ref, "t1")[0] is True

    assert grader.match_bug(
        dict(m_bug, bug_type="deadlock"),
        syn_ref, "t1"
    )[0] is True

    assert grader.match_bug(
        m_bug,
        dict(ref_bug, bug_type="deadlock"), "t1"
    )[0] is True

    m_bug_non_str_interleaving = dict(m_bug, interleaving=123)
    assert grader.match_bug(m_bug_non_str_interleaving, syn_ref, "t1")[0] is True

    poor_explanation = {
        "function": "transfer",
        "bug_type": "deadlock",
        "explanation": "It breaks when called quickly",
        "interleaving": "none",
    }
    matched, detail = grader.match_bug(poor_explanation, ref_bug, "t1")
    assert matched is False
    assert "Explanation lacks key concepts" in detail


def test_grader_validate_all_references():
    ref_dir = BASE_DIR / "reference"
    passed = grader.validate_grader(str(ref_dir))
    assert passed is True


def test_grader_grade_task_edge_cases(tmp_path):
    with pytest.raises(FileNotFoundError):
        grader.grade_task('{"bugs": []}', str(tmp_path / "nonexistent.json"))

    empty_ref = tmp_path / "empty_ref.json"
    with open(empty_ref, "w") as f:
        json.dump({"task_id": "test_id", "bugs": []}, f)
    res2 = grader.grade_task('{"bugs": []}', str(empty_ref))
    assert res2["score"] == 0.0

    valid_ref = BASE_DIR / "reference" / "task_01_bank_transfer_reference.json"
    res3 = grader.grade_task("invalid not json", str(valid_ref))
    assert res3["score"] == 0.0
    assert "Invalid JSON" in res3["details"] or len(res3["matched_bugs"]) == 0


def test_grader_cli_branches(tmp_path, capsys):
    ref_dir = BASE_DIR / "reference"
    sample_ref = ref_dir / "task_01_bank_transfer_reference.json"
    with open(sample_ref, "r") as f:
        ref_data = json.load(f)

    resp_file = tmp_path / "task_01_bank_transfer_response.txt"
    with open(resp_file, "w") as f:
        json.dump({"bugs": ref_data["bugs"]}, f)

    # Test grader __main__ with --validate
    with patch("sys.argv", ["grader.py", "--validate"]):
        runpy.run_path(str(BASE_DIR / "graders" / "grader.py"), run_name="__main__")

    # Test grader __main__ with single file
    with patch("sys.argv", ["grader.py", str(resp_file)]):
        runpy.run_path(str(BASE_DIR / "graders" / "grader.py"), run_name="__main__")

    # Test grader __main__ with no arguments (usage message)
    with patch("sys.argv", ["grader.py"]):
        runpy.run_path(str(BASE_DIR / "graders" / "grader.py"), run_name="__main__")

    # Test grader __main__ with missing reference
    bad_resp_file = tmp_path / "nonexistent_task_response.txt"
    with open(bad_resp_file, "w") as f:
        f.write("{}")
    with patch("sys.argv", ["grader.py", str(bad_resp_file)]):
        with pytest.raises(SystemExit):
            runpy.run_path(str(BASE_DIR / "graders" / "grader.py"), run_name="__main__")


# =====================================================================
# 3. run_eval.py Coverage Tests
# =====================================================================

def test_run_eval_cli_positive_int():
    with patch("sys.argv", ["run_eval.py", "--validate-grader"]):
        run_eval.main()


def test_run_eval_dry_run_no_keys(capsys):
    args = MagicMock()
    args.model = None
    args.trials = 1
    args.dry_run = True
    args.validate_grader = False
    args.skip_validation = True
    args.force = False

    with patch.dict(os.environ, {}, clear=True):
        run_eval.run_evaluation(args)
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out


def test_run_eval_unknown_model():
    args = MagicMock()
    args.model = "completely-unknown-model"
    args.trials = 1
    args.dry_run = False
    args.validate_grader = False
    args.skip_validation = True
    args.force = False

    with pytest.raises(SystemExit):
        run_eval.run_evaluation(args)


def test_run_eval_validation_failure_exit():
    args = MagicMock()
    args.model = "mock-model"
    args.trials = 1
    args.dry_run = False
    args.validate_grader = False
    args.skip_validation = False
    args.force = False

    with patch("run_eval.validate_grader", return_value=False):
        with pytest.raises(SystemExit):
            run_eval.run_evaluation(args)


def test_run_eval_mock_providers_error_handling():
    args = MagicMock()
    args.model = "mock-model"
    args.trials = 1
    args.dry_run = False
    args.validate_grader = False
    args.skip_validation = True
    args.force = False

    with patch("run_eval.PROVIDERS", {"mock": MagicMock(side_effect=RuntimeError("Provider failed"))}):
        run_eval.run_evaluation(args)
