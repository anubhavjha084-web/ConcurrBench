"""
Concurrency Bug Detection Evaluation Harness
=============================================
Sends each task to configured AI models, collects responses, grades them,
and produces a results summary.

Usage:
    python run_eval.py                          # Run all tasks on all configured models
    python run_eval.py --validate-grader        # Validate grader only (no API calls)
    python run_eval.py --model gpt-4o           # Run on a specific model
    python run_eval.py --trials 3               # Number of trials per task
    python run_eval.py --dry-run                # Show prompts without calling APIs

Requires API keys in environment variables or .env file:
    OPENAI_API_KEY      — for GPT models
    ANTHROPIC_API_KEY   — for Claude models
    GOOGLE_API_KEY      — for Gemini models
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# Add graders to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "graders"))
# pyrefly: ignore[missing-import]
from grader import grade_task, validate_grader

# Load .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────
# Model configuration
# ──────────────────────────────────────────────────────────────────

MODEL_CONFIGS = {
    "gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "o3-mini": {
        "provider": "openai",
        "model_id": "o3-mini",
        "temperature": 1.0,  # o3-mini requires temperature=1
        "max_tokens": 16384,
    },
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-20250514",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "claude-3-5-haiku-20241022": {
        "provider": "anthropic",
        "model_id": "claude-3-5-haiku-20241022",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "gemini-2.5-flash": {
        "provider": "google",
        "model_id": "gemini-2.5-flash-preview-05-20",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "gemini-2.5-pro": {
        "provider": "google",
        "model_id": "gemini-2.5-pro-preview-06-05",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
    "mock-model": {
        "provider": "mock",
        "model_id": "mock-concurrency-agent",
        "temperature": 0.0,
        "max_tokens": 4096,
    },
}


# ──────────────────────────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert systems engineer specializing in concurrent and multithreaded programming. You have deep knowledge of threading primitives (locks, condition variables, semaphores), memory models, and common concurrency pitfalls.

Your task is to perform a thorough code review of concurrent code and identify ALL concurrency bugs. Be precise and specific — identify the exact function, the exact type of bug, explain the mechanism, and provide a concrete interleaving that triggers it.

You must return your answer as valid JSON. Do not include any text outside the JSON object."""


def build_prompt(task):
    """Build the user prompt from a task definition."""
    prompt = f"""## Task: {task['title']}

### Scenario
{task['scenario']}

### Code to Review
```python
{task['code']}
```

### Instructions
{task['instruction']}

### Output Format
Return ONLY a valid JSON object with the following structure:
```json
{{
  "bugs": [
    {{
      "function": "<function name where the bug occurs>",
      "bug_type": "<one of the bug types listed in the instructions>",
      "explanation": "<one sentence explaining the bug>",
      "interleaving": "<concrete sequence of thread actions that triggers the bug>"
    }}
  ]
}}
```

Important:
- Identify ALL concurrency bugs, not just the most obvious one.
- Each bug must be in a specific function.
- Return ONLY the JSON object, no additional text."""

    return prompt


# ──────────────────────────────────────────────────────────────────
# API callers
# ──────────────────────────────────────────────────────────────────


def call_openai(prompt, config):
    """Call OpenAI API."""
    from openai import OpenAI

    client = OpenAI()

    kwargs = {
        "model": config["model_id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": config["max_tokens"],
    }

    # o3-mini doesn't support temperature=0
    if not config["model_id"].startswith("o"):
        kwargs["temperature"] = config["temperature"]

    start = time.time()
    response = client.chat.completions.create(**kwargs)
    elapsed = time.time() - start

    content = response.choices[0].message.content
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    return content, elapsed, usage


def call_anthropic(prompt, config):
    """Call Anthropic API."""
    from anthropic import Anthropic

    client = Anthropic()

    start = time.time()
    response = client.messages.create(
        model=config["model_id"],
        max_tokens=config["max_tokens"],
        temperature=config["temperature"],
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start

    content = response.content[0].text
    usage = {
        "prompt_tokens": response.usage.input_tokens,
        "completion_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
    }

    return content, elapsed, usage


def call_google(prompt, config):
    """Call Google Gemini API."""
    from google import genai
    from google.genai import types

    client = genai.Client()

    start = time.time()
    response = client.models.generate_content(
        model=config["model_id"],
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=config["temperature"],
            max_output_tokens=config["max_tokens"],
        ),
    )
    elapsed = time.time() - start

    content = response.text
    usage = {
        "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
        "completion_tokens": getattr(
            response.usage_metadata, "candidates_token_count", 0
        ),
        "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
    }

    return content, elapsed, usage


def call_mock(prompt, config):
    """Deterministic mock model for CI testing, verification, and offline evaluation."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ref_dir = os.path.join(base_dir, "reference")
    tasks_dir = os.path.join(base_dir, "tasks")

    matched_bugs = []
    # Identify task from prompt
    for tf in os.listdir(tasks_dir):
        if tf.endswith(".json"):
            with open(os.path.join(tasks_dir, tf), "r") as f:
                tdata = json.load(f)
            if tdata.get("title", "") in prompt or tdata.get("task_id", "") in prompt:
                ref_path = os.path.join(ref_dir, f"{tdata['task_id']}_reference.json")
                if os.path.exists(ref_path):
                    with open(ref_path, "r") as rf:
                        matched_bugs = json.load(rf).get("bugs", [])
                break

    content = json.dumps({"bugs": matched_bugs}, indent=2)
    elapsed = 0.05
    usage = {
        "prompt_tokens": len(prompt) // 4,
        "completion_tokens": len(content) // 4,
        "total_tokens": (len(prompt) + len(content)) // 4,
    }
    return content, elapsed, usage


PROVIDERS = {
    "openai": call_openai,
    "anthropic": call_anthropic,
    "google": call_google,
    "mock": call_mock,
}


def call_model(prompt, config):
    """Call the appropriate API based on provider."""
    provider = config["provider"]
    caller = PROVIDERS.get(provider)
    if caller is None:
        raise ValueError(f"Unknown provider: {provider}")
    return caller(prompt, config)


# ──────────────────────────────────────────────────────────────────
# Task loading
# ──────────────────────────────────────────────────────────────────


def load_tasks(tasks_dir):
    """Load all task definitions."""
    tasks = []
    for fname in sorted(os.listdir(tasks_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(tasks_dir, fname), "r") as f:
                tasks.append(json.load(f))
    return tasks


# ──────────────────────────────────────────────────────────────────
# Main evaluation loop
# ──────────────────────────────────────────────────────────────────


def run_evaluation(args):
    """Run the full evaluation."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(base_dir, "tasks")
    reference_dir = os.path.join(base_dir, "reference")
    results_dir = os.path.join(base_dir, "results")
    transcripts_dir = os.path.join(base_dir, "transcripts")

    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(transcripts_dir, exist_ok=True)

    # Step 1: Validate grader
    if args.validate_grader or not args.skip_validation:
        print("\n" + "=" * 70)
        print("STEP 1: VALIDATING GRADER")
        print("=" * 70)
        passed = validate_grader(reference_dir)
        if not passed:
            print(
                "\nWARNING: Grader validation failed. Fix issues before running eval."
            )
            if not args.force:
                sys.exit(1)
        if args.validate_grader:
            return

    # Step 2: Load tasks
    tasks = load_tasks(tasks_dir)
    print(f"\nLoaded {len(tasks)} tasks")

    # Step 3: Determine models to test
    models_to_test = []
    if args.model:
        if args.model in MODEL_CONFIGS:
            models_to_test = [args.model]
        else:
            print(f"Unknown model: {args.model}")
            print(f"Available: {', '.join(MODEL_CONFIGS.keys())}")
            sys.exit(1)
    else:
        # Test all models with available API keys
        for name, config in MODEL_CONFIGS.items():
            provider = config["provider"]
            key_name = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
            }.get(provider)
            if key_name and os.environ.get(key_name):
                models_to_test.append(name)

    if not models_to_test:
        print(
            "\nWARNING: No API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY."
        )
        print("  The evaluation harness is ready — set keys and re-run.")
        print("  You can also run: python run_eval.py --dry-run  to see prompts.")

        if args.dry_run:
            print("\n" + "=" * 70)
            print("DRY RUN — Showing prompts for each task")
            print("=" * 70)
            for task in tasks:
                prompt = build_prompt(task)
                print(f"\n--- {task['task_id']}: {task['title']} ---")
                print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        return

    print(f"Models to test: {', '.join(models_to_test)}")
    print(f"Trials per task: {args.trials}")

    # Step 4: Run evaluation
    all_results = {}
    run_timestamp = datetime.now(timezone.utc).isoformat()

    for model_name in models_to_test:
        config = MODEL_CONFIGS[model_name]
        model_results = {
            "model": model_name,
            "model_id": config["model_id"],
            "provider": config["provider"],
            "temperature": (
                None if config["model_id"].startswith("o") else config["temperature"]
            ),
            "max_tokens": config["max_tokens"],
            "timestamp": run_timestamp,
            "trials": args.trials,
            "tasks": {},
        }

        print(f"\n{'=' * 70}")
        print(f"EVALUATING: {model_name}")
        print(f"{'=' * 70}")

        total_cost_tokens = 0

        for task in tasks:
            task_id = task["task_id"]
            ref_path = os.path.join(reference_dir, f"{task_id}_reference.json")

            if not os.path.exists(ref_path):
                print(f"  WARNING: No reference for {task_id}, skipping")
                continue

            print(f"\n  TASK {task_id}: {task['title']}")

            trial_results = []
            prompt = build_prompt(task)

            for trial in range(args.trials):
                trial_label = f"Trial {trial + 1}/{args.trials}"

                if args.dry_run:
                    print(
                        f"    {trial_label}: [DRY RUN] Would send prompt ({len(prompt)} chars)"
                    )
                    continue

                try:
                    print(
                        f"    {trial_label}: Calling {model_name}...",
                        end=" ",
                        flush=True,
                    )
                    response, elapsed, usage = call_model(prompt, config)
                    total_cost_tokens += usage.get("total_tokens", 0)

                    # Grade the response
                    grade_result = grade_task(response, ref_path)

                    print(
                        f"Score: {grade_result['score']:.2f} "
                        f"({len(grade_result.get('matched_bugs', []))}/{grade_result['total_reference_bugs']} bugs) "
                        f"[{elapsed:.1f}s, {usage.get('total_tokens', '?')} tokens]"
                    )

                    trial_data = {
                        "trial": trial + 1,
                        "score": grade_result["score"],
                        "precision": grade_result["precision"],
                        "recall": grade_result["recall"],
                        "matched_bugs": grade_result["matched_bugs"],
                        "missed_bugs": grade_result["missed_bugs"],
                        "false_positives": grade_result.get("false_positives", []),
                        "total_reference_bugs": grade_result["total_reference_bugs"],
                        "model_bugs_reported": grade_result.get(
                            "model_bugs_reported", 0
                        ),
                        "elapsed_seconds": elapsed,
                        "tokens": usage,
                        "details": grade_result["details"],
                    }
                    trial_results.append(trial_data)

                    # Save transcript
                    transcript_file = os.path.join(
                        transcripts_dir, f"{model_name}_{task_id}_trial{trial+1}.json"
                    )
                    transcript = {
                        "model": model_name,
                        "task_id": task_id,
                        "trial": trial + 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "prompt": prompt,
                        "response": response,
                        "grade": trial_data,
                    }
                    with open(transcript_file, "w") as f:
                        json.dump(transcript, f, indent=2)

                except Exception as e:
                    print(f"ERROR: {e}")
                    trial_results.append(
                        {
                            "trial": trial + 1,
                            "score": 0.0,
                            "error": str(e),
                        }
                    )

            if trial_results and not args.dry_run:
                scores = [t["score"] for t in trial_results if "error" not in t]

                # pass@k: probability of at least one correct in k trials
                # pass^k: probability of all correct in k trials
                if scores:
                    pass_rate = (
                        sum(1 for s in scores if s >= 0.8) / len(scores)
                        if scores
                        else 0
                    )
                    mean_score = sum(scores) / len(scores)
                    max_score = max(scores)
                    min_score = min(scores)
                    pass_at_k = max_score >= 0.8
                    pass_all_k = len(scores) == args.trials and min_score >= 0.8
                else:
                    pass_rate = mean_score = max_score = min_score = 0
                    pass_at_k = pass_all_k = False

                model_results["tasks"][task_id] = {
                    "trials": trial_results,
                    "mean_score": mean_score,
                    "max_score": max_score,
                    "min_score": min_score,
                    "pass_rate_80pct": pass_rate,
                    "pass_at_k": pass_at_k,
                    "pass_all_k": pass_all_k,
                    "num_trials": len(scores),
                }

        model_results["total_tokens"] = total_cost_tokens
        all_results[model_name] = model_results

        # Save per-model results
        model_results_file = os.path.join(results_dir, f"{model_name}_results.json")
        with open(model_results_file, "w") as f:
            json.dump(model_results, f, indent=2)
        print(f"\n  Results saved to {model_results_file}")

    # Step 5: Generate summary
    if all_results and not args.dry_run:
        generate_summary(all_results, results_dir, args.trials)


def generate_summary(all_results, results_dir, trials):
    """Generate a summary table and analysis."""
    summary_lines = []
    summary_lines.append("=" * 80)
    summary_lines.append("EVALUATION RESULTS SUMMARY")
    summary_lines.append("=" * 80)
    summary_lines.append(f"Date: {datetime.now(timezone.utc).isoformat()}")
    summary_lines.append(f"Trials per task: {trials}")
    summary_lines.append("")

    # Results table
    header = f"{'Model':<30} {'Mean Score':>10} {'Pass Rate':>10} {'pass@k':>8} {'pass^k':>8} {'Tokens':>10}"
    summary_lines.append(header)
    summary_lines.append("-" * len(header))

    for model_name, results in all_results.items():
        task_scores = [t["mean_score"] for t in results["tasks"].values()]
        overall_mean = sum(task_scores) / len(task_scores) if task_scores else 0
        pass_rates = [t["pass_rate_80pct"] for t in results["tasks"].values()]
        overall_pass = sum(pass_rates) / len(pass_rates) if pass_rates else 0
        pass_at_k_rate = (
            sum(t["pass_at_k"] for t in results["tasks"].values())
            / len(results["tasks"])
            if results["tasks"]
            else 0
        )
        pass_all_k_rate = (
            sum(t["pass_all_k"] for t in results["tasks"].values())
            / len(results["tasks"])
            if results["tasks"]
            else 0
        )

        summary_lines.append(
            f"{model_name:<30} {overall_mean:>9.1%} {overall_pass:>9.1%} "
            f"{pass_at_k_rate:>7.1%} {pass_all_k_rate:>7.1%} {results.get('total_tokens', 0):>10}"
        )

    summary_lines.append("")

    # Per-task breakdown
    summary_lines.append("PER-TASK BREAKDOWN")
    summary_lines.append("-" * 80)

    # Get all task IDs
    all_task_ids = set()
    for results in all_results.values():
        all_task_ids.update(results["tasks"].keys())

    for task_id in sorted(all_task_ids):
        summary_lines.append(f"\n  {task_id}:")
        for model_name, results in all_results.items():
            task_data = results["tasks"].get(task_id)
            if task_data:
                summary_lines.append(
                    f"    {model_name:<28} Mean: {task_data['mean_score']:.2f}  "
                    f"Range: [{task_data['min_score']:.2f}, {task_data['max_score']:.2f}]  "
                    f"Trials: {task_data['num_trials']}"
                )
                # Show commonly missed bugs
                if task_data["trials"]:
                    all_missed = []
                    for trial in task_data["trials"]:
                        if "missed_bugs" in trial:
                            all_missed.extend(trial["missed_bugs"])
                    if all_missed:
                        from collections import Counter

                        missed_counts = Counter(all_missed)
                        most_missed = missed_counts.most_common(2)
                        for bug, count in most_missed:
                            summary_lines.append(
                                f"      ↳ Missed {count}/{task_data['num_trials']} times: {bug[:70]}..."
                                if len(bug) > 70
                                else f"      ↳ Missed {count}/{task_data['num_trials']} times: {bug}"
                            )

    summary_text = "\n".join(summary_lines)
    print("\n" + summary_text)

    # Save summary
    summary_file = os.path.join(results_dir, "summary.txt")
    with open(summary_file, "w") as f:
        f.write(summary_text)

    # Save structured summary as JSON
    summary_json = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trials_per_task": trials,
        "models": {},
    }

    for model_name, results in all_results.items():
        task_scores = [t["mean_score"] for t in results["tasks"].values()]
        overall_mean = sum(task_scores) / len(task_scores) if task_scores else 0
        pass_rates = [t["pass_rate_80pct"] for t in results["tasks"].values()]
        overall_pass = sum(pass_rates) / len(pass_rates) if pass_rates else 0
        pass_at_k_rate = (
            sum(t["pass_at_k"] for t in results["tasks"].values())
            / len(results["tasks"])
            if results["tasks"]
            else 0
        )
        pass_all_k_rate = (
            sum(t["pass_all_k"] for t in results["tasks"].values())
            / len(results["tasks"])
            if results["tasks"]
            else 0
        )

        summary_json["models"][model_name] = {
            "model_id": results.get("model_id", model_name),
            "provider": results.get("provider", "unknown"),
            "temperature": results.get("temperature", 0),
            "max_tokens": results.get("max_tokens"),
            "trials_per_task": results.get("trials"),
            "timestamp": results.get("timestamp"),
            "overall_mean_score": overall_mean,
            "overall_pass_rate": overall_pass,
            "pass_at_k": pass_at_k_rate,
            "pass_all_k": pass_all_k_rate,
            "total_tokens": results.get("total_tokens", 0),
            "per_task": {
                tid: {
                    "mean_score": td["mean_score"],
                    "max_score": td["max_score"],
                    "min_score": td["min_score"],
                    "pass_rate": td["pass_rate_80pct"],
                    "pass_at_k": td["pass_at_k"],
                    "pass_all_k": td["pass_all_k"],
                }
                for tid, td in results["tasks"].items()
            },
        }

    json_file = os.path.join(results_dir, "summary.json")
    with open(json_file, "w") as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nSummary saved to {summary_file}")
    print(f"JSON summary saved to {json_file}")


# ──────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────


def main():
    def positive_int(value):
        parsed = int(value)
        if parsed < 1:
            raise argparse.ArgumentTypeError("must be a positive integer")
        return parsed

    parser = argparse.ArgumentParser(
        description="Concurrency Bug Detection Evaluation Harness"
    )
    parser.add_argument("--model", type=str, help="Specific model to test")
    parser.add_argument(
        "--trials", type=positive_int, default=3, help="Trials per task (default: 3)"
    )
    parser.add_argument(
        "--validate-grader", action="store_true", help="Only validate grader"
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip grader validation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show prompts without API calls"
    )
    parser.add_argument(
        "--force", action="store_true", help="Continue even if validation fails"
    )

    args = parser.parse_args()
    run_evaluation(args)


if __name__ == "__main__":
    main()
