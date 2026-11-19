"""
Unit tests for the ConcurrencyBugBench grader.
"""

import json
import os
import sys

import pytest

# Ensure the graders package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "graders"))

from grader import (
    extract_json_from_response,
    grade_all_tasks,
    grade_task,
    normalize_bug_type,
    normalize_function_name,
    validate_grader,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE_DIR = os.path.join(BASE_DIR, "reference")


# ── Normalization helpers ─────────────────────────────────────────


class TestNormalizeBugType:
    def test_canonical_unchanged(self):
        assert normalize_bug_type("deadlock") == "deadlock"

    def test_synonym_maps(self):
        assert normalize_bug_type("data_race") == "race_condition"
        assert normalize_bug_type("toctou") == "atomicity_violation"
        assert normalize_bug_type("busy_wait") == "spin_wait"

    def test_whitespace_and_hyphens(self):
        assert normalize_bug_type("  data-race ") == "race_condition"


class TestNormalizeFunctionName:
    def test_basic(self):
        assert normalize_function_name("transfer") == "transfer"

    def test_strips_parens_and_self(self):
        assert normalize_function_name("self.transfer()") == "transfer"

    def test_class_method(self):
        assert normalize_function_name("BankAccount.transfer") == "transfer"


# ── JSON extraction ───────────────────────────────────────────────


class TestExtractJson:
    def test_plain_json(self):
        raw = json.dumps({"bugs": []})
        assert extract_json_from_response(raw) == {"bugs": []}

    def test_markdown_json_block(self):
        raw = '```json\n{"bugs": []}\n```'
        assert extract_json_from_response(raw) == {"bugs": []}

    def test_garbage_returns_none(self):
        assert extract_json_from_response("not json at all") is None

    def test_empty_string(self):
        assert extract_json_from_response("") is None

    def test_none_input(self):
        assert extract_json_from_response(None) is None


# ── grade_task ────────────────────────────────────────────────────


class TestGradeTask:
    @pytest.fixture(autouse=True)
    def _pick_first_ref(self):
        refs = sorted(
            f for f in os.listdir(REFERENCE_DIR) if f.endswith("_reference.json")
        )
        assert refs, "No reference files found"
        self.ref_path = os.path.join(REFERENCE_DIR, refs[0])
        with open(self.ref_path) as f:
            self.ref = json.load(f)

    def test_perfect_score(self):
        response = json.dumps({"bugs": self.ref["bugs"]})
        result = grade_task(response, self.ref_path)
        assert abs(result["score"] - 1.0) < 1e-9

    def test_empty_response_zero(self):
        result = grade_task("", self.ref_path)
        assert result["score"] == 0.0

    def test_wrong_function_zero(self):
        wrong = [
            {
                "function": "nonexistent_function",
                "bug_type": self.ref["bugs"][0]["bug_type"],
                "explanation": self.ref["bugs"][0]["explanation"],
                "interleaving": self.ref["bugs"][0].get("interleaving", ""),
            }
        ]
        result = grade_task(json.dumps({"bugs": wrong}), self.ref_path)
        assert result["score"] == 0.0

    def test_extra_fp_lowers_score(self):
        bugs = self.ref["bugs"] + [
            {
                "function": "nonexistent_function",
                "bug_type": "race_condition",
                "explanation": "A made-up race condition.",
                "interleaving": "Two threads execute at once.",
            }
        ]
        result = grade_task(json.dumps({"bugs": bugs}), self.ref_path)
        assert result["score"] < 1.0

    def test_duplicate_no_double_credit(self):
        bugs = [self.ref["bugs"][0], self.ref["bugs"][0]]
        result = grade_task(json.dumps({"bugs": bugs}), self.ref_path)
        assert len(result["matched_bugs"]) == 1

    def test_malformed_entry(self):
        result = grade_task(json.dumps({"bugs": [None]}), self.ref_path)
        assert result["score"] == 0.0


# ── validate_grader (integration) ────────────────────────────────


class TestValidateGrader:
    def test_validate_passes(self):
        assert validate_grader(REFERENCE_DIR) is True


class TestGradeAllTasks:
    def test_grade_all_tasks_empty_dir(self, tmp_path):
        agg = grade_all_tasks(str(tmp_path), REFERENCE_DIR)
        assert agg["aggregate"]["total_tasks"] == 7
        assert agg["aggregate"]["tasks_skipped"] == 7
        assert agg["aggregate"]["mean_score"] == 0.0

    def test_grade_all_tasks_with_response(self, tmp_path):
        # Create a matching response file for task_01_bank_transfer
        ref_file = os.path.join(REFERENCE_DIR, "task_01_bank_transfer_reference.json")
        with open(ref_file) as f:
            ref = json.load(f)
        resp_file = tmp_path / "task_01_bank_transfer_response.txt"
        resp_file.write_text(json.dumps({"bugs": ref["bugs"]}))

        agg = grade_all_tasks(str(tmp_path), REFERENCE_DIR)
        assert agg["aggregate"]["tasks_graded"] == 1
        assert agg["aggregate"]["mean_score"] == 1.0


class TestGraderEdgeCases:
    def test_invalid_bugs_field_type(self):
        ref_file = os.path.join(REFERENCE_DIR, "task_01_bank_transfer_reference.json")
        result = grade_task(json.dumps({"bugs": "not-a-list"}), ref_file)
        assert result["score"] == 0.0
        assert result["parse_error"] is True

    def test_non_dict_bug_entry(self):
        ref_file = os.path.join(REFERENCE_DIR, "task_01_bank_transfer_reference.json")
        result = grade_task(json.dumps({"bugs": ["string_instead_of_dict"]}), ref_file)
        assert result["score"] == 0.0
        assert len(result["false_positives"]) == 1
