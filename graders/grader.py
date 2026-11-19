"""
Concurrency Bug Detection Grader
================================
Deterministic, code-based grading for the concurrency eval benchmark.
Each model response is compared against the reference bugs using semantic matching.

Scoring:
- Each reference bug is worth 1 point.
- A model-reported bug matches a reference bug if:
  1. It identifies the correct function (exact match or reasonable alias).
  2. It identifies the correct bug type (from the allowed set, with synonyms mapped).
  3. Its explanation demonstrates understanding of the core issue (keyword matching).
- Partial credit: per correctly identified bug.
- False positives and duplicate reports reduce precision.
- Score per task is the F1 score of precision and recall.
"""

import json
import os
import re
import sys

# Canonical bug type synonyms — models may use slightly different terminology
BUG_TYPE_SYNONYMS = {
    "deadlock": {"deadlock", "circular_wait", "lock_ordering", "deadly_embrace"},
    "race_condition": {
        "race_condition",
        "data_race",
        "race",
        "racy_read",
        "racy_write",
        "unsynchronized_access",
        "thread_unsafe",
    },
    "atomicity_violation": {
        "atomicity_violation",
        "atomicity",
        "toctou",
        "time_of_check_time_of_use",
        "check_then_act",
        "compound_action",
        "non_atomic",
    },
    "ordering_bug": {
        "ordering_bug",
        "ordering",
        "memory_ordering",
        "instruction_reordering",
        "happens_before",
    },
    "memory_visibility": {
        "memory_visibility",
        "visibility",
        "stale_read",
        "cache_coherence",
        "memory_barrier",
        "volatile",
    },
    "starvation": {
        "starvation",
        "livelock",
        "unfairness",
        "writer_starvation",
        "reader_starvation",
        "priority_inversion",
    },
    "lost_wakeup": {
        "lost_wakeup",
        "lost_signal",
        "missed_notification",
        "lost_notification",
    },
    "spurious_wakeup_vulnerability": {
        "spurious_wakeup_vulnerability",
        "spurious_wakeup",
        "if_instead_of_while",
        "missing_while_loop",
    },
    "spin_wait": {"spin_wait", "busy_wait", "busy_waiting", "spinlock", "polling"},
    "lost_task": {
        "lost_task",
        "task_loss",
        "dropped_task",
        "silently_dropped",
        "lost_work",
    },
    "iterator_invalidation": {
        "iterator_invalidation",
        "concurrent_modification",
        "modification_during_iteration",
    },
}

# Keywords that indicate understanding of each specific bug
# (task_id, bug_index) -> set of keyword groups (at least one keyword from each group must appear)
BUG_KEYWORDS: dict[tuple[str, int], set[str]] = {}  # populated per-task below


def normalize_bug_type(bug_type_str):
    """Normalize a bug type string to its canonical form."""
    cleaned = bug_type_str.strip().lower().replace(" ", "_").replace("-", "_")
    for canonical, synonyms in BUG_TYPE_SYNONYMS.items():
        if cleaned in synonyms:
            return canonical
    return cleaned


def normalize_function_name(func_name):
    """Normalize function name for comparison."""
    cleaned = func_name.strip().lower().replace("()", "").replace("self.", "")
    # Handle class.method notation
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    return cleaned


def extract_json_from_response(response_text):
    """Extract JSON from a model response, handling markdown code blocks."""
    if response_text is None:
        return None

    # Try direct JSON parse first
    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON in markdown code blocks
    patterns = [
        r"```json\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```",
        r"\{.*\}",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and "bugs" in parsed:
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue

    return None


def match_bug(model_bug, ref_bug, task_id):
    """
    Check if a model-reported bug matches a reference bug.
    Returns (matched: bool, details: str)
    """
    if not isinstance(model_bug, dict):
        return False, "Bug entry is not an object"
    if not all(
        isinstance(model_bug.get(key), str)
        for key in ("function", "bug_type", "explanation")
    ):
        return False, "Bug entry is missing required string fields"

    # 1. Check function name match
    model_func = normalize_function_name(model_bug["function"])
    ref_func = normalize_function_name(ref_bug.get("function", ""))

    if model_func != ref_func:
        return False, f"Function mismatch: model='{model_func}' vs ref='{ref_func}'"

    # 2. Check bug type match (with synonyms)
    model_type = normalize_bug_type(model_bug["bug_type"])
    ref_type = normalize_bug_type(ref_bug.get("bug_type", ""))

    type_match = False
    if model_type == ref_type:
        type_match = True
    else:
        # Check if they map to the same canonical type
        for canonical, synonyms in BUG_TYPE_SYNONYMS.items():
            if model_type in synonyms and ref_type in synonyms:
                type_match = True
                break
            if model_type == canonical and ref_type in synonyms:
                type_match = True
                break
            if ref_type == canonical and model_type in synonyms:
                type_match = True
                break

    if not type_match:
        return False, f"Bug type mismatch: model='{model_type}' vs ref='{ref_type}'"

    # 3. Check explanation quality — the model must demonstrate understanding
    interleaving = model_bug.get("interleaving", "")
    if not isinstance(interleaving, str):
        interleaving = ""
    model_explanation = (model_bug["explanation"] + " " + interleaving).lower()

    ref_explanation = (
        ref_bug.get("explanation", "") + " " + ref_bug.get("interleaving", "")
    ).lower()

    # The explanation must contain at least some relevant keywords from the reference
    # We check for key concepts rather than exact wording
    ref_keywords = extract_key_concepts(ref_explanation)
    match_count = sum(1 for kw in ref_keywords if re.search(kw, model_explanation))

    if len(ref_keywords) > 0 and match_count < max(1, (len(ref_keywords) + 2) // 3):
        return (
            False,
            f"Explanation lacks key concepts (matched {match_count}/{len(ref_keywords)})",
        )

    return True, "Matched"


def extract_key_concepts(explanation):
    """Extract key concept keywords from a reference explanation."""
    # Important concurrency concepts to look for
    concept_patterns = [
        "deadlock",
        "circular wait",
        "lock order",
        "race",
        "atomic",
        "toctou",
        "check.*then.*act",
        "spurious wakeup",
        "while",
        "if instead",
        "starvation",
        "fairness",
        "starve",
        "lost.*wake",
        "notify_all",
        "notify.*one",
        "spin",
        "busy.*wait",
        "poll",
        "memory.*vis",
        "partial.*construct",
        "reorder",
        "without.*lock",
        "no.*lock",
        "outside.*lock",
        "concurrent.*modif",
        "iteration",
        "iterator",
        "lost.*task",
        "queue.*drain",
        "shutdown",
        "counter",
        "increment",
        "double.*count",
        "negative",
        "underflow",
        "partially",
        "stale",
        "inconsistent",
        "two.*thread",
        "both.*see",
        "interleav",
    ]

    found = []
    for pattern in concept_patterns:
        if re.search(pattern, explanation):
            found.append(pattern)
    return found


def grade_task(model_response_text, reference_path):
    """
    Grade a single task response.

    Returns:
        dict with keys:
            - score: float (0.0 to 1.0)
            - matched_bugs: list of matched reference bugs
            - missed_bugs: list of unmatched reference bugs
            - false_positives: list of model bugs that didn't match anything
            - total_reference_bugs: int
            - details: str
    """
    # Load reference
    with open(reference_path, "r") as f:
        reference = json.load(f)

    ref_bugs = reference["bugs"]
    task_id = reference["task_id"]

    # Parse model response
    parsed = extract_json_from_response(model_response_text)

    if not isinstance(parsed, dict):
        return {
            "score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "matched_bugs": [],
            "missed_bugs": [b["explanation"] for b in ref_bugs],
            "false_positives": [],
            "total_reference_bugs": len(ref_bugs),
            "parse_error": True,
            "details": "Could not parse JSON from model response",
        }

    model_bugs = parsed.get("bugs", [])

    if not isinstance(model_bugs, list):
        return {
            "score": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "matched_bugs": [],
            "missed_bugs": [b["explanation"] for b in ref_bugs],
            "false_positives": [],
            "total_reference_bugs": len(ref_bugs),
            "parse_error": True,
            "details": "'bugs' field is not a list",
        }

    # Match model bugs to reference bugs (greedy matching)
    matched_ref_indices = set()
    matched_model_indices = set()
    match_details = []

    for mi, model_bug in enumerate(model_bugs):
        for ri, ref_bug in enumerate(ref_bugs):
            if ri in matched_ref_indices:
                continue
            matched, detail = match_bug(model_bug, ref_bug, task_id)
            if matched:
                matched_ref_indices.add(ri)
                matched_model_indices.add(mi)
                match_details.append(
                    {
                        "model_bug": (
                            model_bug.get("explanation", "")
                            if isinstance(model_bug, dict)
                            else ""
                        ),
                        "ref_bug": ref_bug.get("explanation", ""),
                        "detail": detail,
                    }
                )
                break

    # Compute results
    matched_bugs = [ref_bugs[i]["explanation"] for i in sorted(matched_ref_indices)]
    missed_bugs = [
        ref_bugs[i]["explanation"]
        for i in range(len(ref_bugs))
        if i not in matched_ref_indices
    ]
    false_positives = [
        (
            model_bugs[i].get("explanation", str(model_bugs[i]))
            if isinstance(model_bugs[i], dict)
            else str(model_bugs[i])
        )
        for i in range(len(model_bugs))
        if i not in matched_model_indices
    ]

    true_positives = len(matched_ref_indices)
    false_positive_count = len(model_bugs) - len(matched_model_indices)
    precision = (
        true_positives / (true_positives + false_positive_count)
        if true_positives + false_positive_count
        else 0.0
    )
    recall = true_positives / len(ref_bugs) if ref_bugs else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "score": score,
        "precision": precision,
        "recall": recall,
        "matched_bugs": matched_bugs,
        "missed_bugs": missed_bugs,
        "false_positives": false_positives,
        "total_reference_bugs": len(ref_bugs),
        "model_bugs_reported": len(model_bugs),
        "match_details": match_details,
        "parse_error": False,
        "details": f"Matched {len(matched_ref_indices)}/{len(ref_bugs)} bugs. {len(false_positives)} false positive(s).",
    }


def grade_all_tasks(results_dir, reference_dir):
    """
    Grade all tasks and return aggregate results.
    """
    task_scores = {}

    for ref_file in sorted(os.listdir(reference_dir)):
        if not ref_file.endswith("_reference.json"):
            continue

        task_id = ref_file.replace("_reference.json", "")
        ref_path = os.path.join(reference_dir, ref_file)

        # Find corresponding model output
        response_file = os.path.join(results_dir, f"{task_id}_response.txt")
        if not os.path.exists(response_file):
            task_scores[task_id] = {
                "score": 0.0,
                "details": "No response file found",
                "skipped": True,
            }
            continue

        with open(response_file, "r") as f:
            model_response = f.read()

        task_scores[task_id] = grade_task(model_response, ref_path)

    # Aggregate
    valid_scores = [s["score"] for s in task_scores.values() if not s.get("skipped")]
    aggregate = {
        "tasks": task_scores,
        "aggregate": {
            "mean_score": (
                sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
            ),
            "tasks_graded": len(valid_scores),
            "tasks_skipped": len(task_scores) - len(valid_scores),
            "total_tasks": len(task_scores),
        },
    }

    return aggregate


def validate_grader(reference_dir):
    """
    Validate the grader by checking that:
    1. Reference solutions pass every grader (score = 1.0)
    2. Deliberately wrong answers fail every grader (score < 1.0)
    3. Empty responses get score 0.0
    4. False positives and duplicate reports reduce precision
    """
    print("=" * 60)
    print("GRADER VALIDATION")
    print("=" * 60)

    all_passed = True
    tasks_dir = os.path.join(os.path.dirname(reference_dir), "tasks")
    task_ids = {
        filename[:-5]
        for filename in os.listdir(tasks_dir)
        if filename.endswith(".json")
    }
    reference_ids = {
        filename[:-15]
        for filename in os.listdir(reference_dir)
        if filename.endswith("_reference.json")
    }
    if task_ids != reference_ids:
        print("FAIL: Task and reference file sets do not match")
        print(f"  Tasks without references: {sorted(task_ids - reference_ids)}")
        print(f"  References without tasks: {sorted(reference_ids - task_ids)}")
        all_passed = False

    for ref_file in sorted(os.listdir(reference_dir)):
        if not ref_file.endswith("_reference.json"):
            continue

        task_id = ref_file.replace("_reference.json", "")
        ref_path = os.path.join(reference_dir, ref_file)

        with open(ref_path, "r") as f:
            reference = json.load(f)

        print(f"\n--- {task_id} ---")

        task_path = os.path.join(tasks_dir, f"{task_id}.json")
        if not os.path.exists(task_path):
            print(f"  FAIL: Task definition missing: {task_path}")
            all_passed = False
        else:
            with open(task_path, "r") as f:
                task = json.load(f)
            if (
                task.get("task_id") != task_id
                or reference.get("task_id") != task_id
                or task.get("expected_bug_count") != len(reference["bugs"])
            ):
                print(
                    "  FAIL: Task metadata does not match the reference bug count or task ID"
                )
                all_passed = False
            else:
                print(
                    f"  PASS: Task metadata matches ({len(reference['bugs'])} reference bugs)"
                )

        # Test 1: Reference solution should score 1.0
        ref_response = json.dumps({"bugs": reference["bugs"]})
        result = grade_task(ref_response, ref_path)

        if abs(result["score"] - 1.0) < 1e-9:
            print(f"  PASS: Reference solution (score={result['score']:.2f})")
        else:
            print(f"  FAIL: Reference solution (score={result['score']:.2f})")
            print(f"    Missed: {result['missed_bugs']}")
            all_passed = False

        # Test 2: Empty response should score 0.0
        empty_result = grade_task("", ref_path)
        if abs(empty_result["score"]) < 1e-9:
            print(f"  PASS: Empty response (score={empty_result['score']:.2f})")
        else:
            print(f"  FAIL: Empty response (score={empty_result['score']:.2f})")
            all_passed = False

        # Test 3: Wrong bugs should not match
        wrong_response = json.dumps(
            {
                "bugs": [
                    {
                        "function": "nonexistent_function",
                        "bug_type": "deadlock",
                        "explanation": "This function has a deadlock because reasons.",
                        "interleaving": "Thread 1 does X, Thread 2 does Y.",
                    }
                ]
            }
        )
        wrong_result = grade_task(wrong_response, ref_path)
        if wrong_result["score"] == 0.0 and wrong_result["false_positives"]:
            print(f"  PASS: Wrong answer rejected (score={wrong_result['score']:.2f})")
        else:
            print(
                f"  FAIL: Wrong answer false-positive handling (score={wrong_result['score']:.2f})"
            )
            all_passed = False

        # Test 4: A false positive must lower an otherwise perfect score
        extra_bug_response = json.dumps(
            {
                "bugs": reference["bugs"]
                + [
                    {
                        "function": "nonexistent_function",
                        "bug_type": "race_condition",
                        "explanation": "A made-up race condition.",
                        "interleaving": "Two threads execute at once.",
                    }
                ]
            }
        )
        extra_bug_result = grade_task(extra_bug_response, ref_path)
        if (
            extra_bug_result["score"] < 1.0
            and len(extra_bug_result["false_positives"]) == 1
        ):
            print(
                f"  PASS: Extra false positive penalized (score={extra_bug_result['score']:.2f})"
            )
        else:
            print(
                f"  FAIL: Extra false positive not penalized (score={extra_bug_result['score']:.2f})"
            )
            all_passed = False

        # Test 5: A duplicate cannot earn credit for the same reference more than once
        duplicate_response = json.dumps(
            {"bugs": [reference["bugs"][0], reference["bugs"][0]]}
        )
        duplicate_result = grade_task(duplicate_response, ref_path)
        if (
            len(duplicate_result["matched_bugs"]) == 1
            and len(duplicate_result["false_positives"]) == 1
        ):
            print("  PASS: Duplicate report cannot earn duplicate credit")
        else:
            print("  FAIL: Duplicate report handling")
            all_passed = False

        # Test 6: Right bug type but wrong function should fail
        partially_wrong = json.dumps(
            {
                "bugs": [
                    {
                        "function": "wrong_func",
                        "bug_type": reference["bugs"][0]["bug_type"],
                        "explanation": reference["bugs"][0]["explanation"],
                        "interleaving": reference["bugs"][0]["interleaving"],
                    }
                ]
            }
        )
        partial_result = grade_task(partially_wrong, ref_path)
        if partial_result["matched_bugs"] == [] and partial_result["false_positives"]:
            print("  PASS: Wrong function rejected")
        else:
            print("  FAIL: Wrong function accepted")
            all_passed = False

        # Test 7: Malformed bug entries are rejected without crashing
        malformed_result = grade_task(json.dumps({"bugs": [None]}), ref_path)
        if (
            malformed_result["score"] == 0.0
            and len(malformed_result["false_positives"]) == 1
        ):
            print("  PASS: Malformed bug entry rejected")
        else:
            print("  FAIL: Malformed bug entry handling")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL GRADER VALIDATION CHECKS PASSED")
    else:
        print("SOME GRADER VALIDATION CHECKS FAILED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    reference_dir = os.path.join(os.path.dirname(__file__), "..", "reference")

    if len(sys.argv) > 1 and sys.argv[1] == "--validate":
        validate_grader(reference_dir)
    elif len(sys.argv) > 1:
        # Grade a specific response file against its reference
        response_file = sys.argv[1]
        task_id = os.path.basename(response_file).replace("_response.txt", "")
        ref_path = os.path.join(reference_dir, f"{task_id}_reference.json")

        if not os.path.exists(ref_path):
            print(f"No reference found for {task_id}")
            sys.exit(1)

        with open(response_file, "r") as f:
            response = f.read()

        result = grade_task(response, ref_path)
        print(json.dumps(result, indent=2))
    else:
        print("Usage:")
        print(
            "  python grader.py --validate          # Validate grader against reference solutions"
        )
        print("  python grader.py <response_file>     # Grade a single response")
