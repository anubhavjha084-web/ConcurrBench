"""
End-to-end integration test for the ConcurrencyBugBench evaluation harness.
Runs the evaluation loop against a mock model and verifies full pipeline execution.
"""

import json
import os
import sys
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_eval import run_evaluation


class ArgsStub:
    """Mock argparse namespace for run_evaluation."""
    def __init__(self, model="mock-model", trials=1, validate_grader=False, skip_validation=True, dry_run=False, force=True):
        self.model = model
        self.trials = trials
        self.validate_grader = validate_grader
        self.skip_validation = skip_validation
        self.dry_run = dry_run
        self.force = force


class TestHarnessIntegration:
    def test_full_harness_execution_with_mock_model(self):
        """Run full evaluation with mock model and verify output files."""
        args = ArgsStub(model="mock-model", trials=1)
        run_evaluation(args)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        results_dir = os.path.join(base_dir, "results")
        transcripts_dir = os.path.join(base_dir, "transcripts")

        # Verify summary files were updated
        summary_json = os.path.join(results_dir, "summary.json")
        summary_txt = os.path.join(results_dir, "summary.txt")
        model_results = os.path.join(results_dir, "mock-model_results.json")

        assert os.path.exists(summary_json), "summary.json was not created"
        assert os.path.exists(summary_txt), "summary.txt was not created"
        assert os.path.exists(model_results), "model results json was not created"

        with open(summary_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "models" in data
        assert "mock-model" in data["models"]
        assert data["models"]["mock-model"]["overall_mean_score"] > 0.0

        # Verify transcripts were generated
        transcripts = [f for f in os.listdir(transcripts_dir) if f.startswith("mock-model_")]
        assert len(transcripts) >= 7, f"Expected at least 7 transcripts, got {len(transcripts)}"

        # Verify transcript content structure
        sample_transcript = os.path.join(transcripts_dir, transcripts[0])
        with open(sample_transcript, "r", encoding="utf-8") as f:
            t_data = json.load(f)
        assert "model" in t_data
        assert "task_id" in t_data
        assert "prompt" in t_data
        assert "response" in t_data
        assert "grade" in t_data
        assert "score" in t_data["grade"]
