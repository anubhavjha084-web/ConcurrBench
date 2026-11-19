# ConcurrBench: Evaluating AI Models on Concurrency Bug Detection
[![CI](https://github.com/anubhavjha084-web/ConcurrBench/actions/workflows/ci.yml/badge.svg)](https://github.com/anubhavjha084-web/ConcurrBench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Coverage: 92%](https://img.shields.io/badge/coverage-92%25-brightgreen.svg)](https://github.com/anubhavjha084-web/ConcurrBench)
[![Tests: 75 Passed](https://img.shields.io/badge/tests-75%20passed-success.svg)](https://github.com/anubhavjha084-web/ConcurrBench)

> **Domain**: Systems Engineering / Concurrent Programming  
> **Evaluation objective**: Measure how reliably AI models identify concrete concurrency bugs in Python programs. Evaluated via a deterministic code-based grading harness.

## Short Description

**ConcurrBench** is a 7-task evaluation benchmark and developer platform for concurrency code review. Each task presents a Python program with one or more documented concurrency defects (race conditions, deadlocks, TOCTOU, condition predicate misuse, atomicity violations). Models identify bugs, classify their types, explain the mechanism, and give a triggering interleaving. The deterministic grader matches function, bug type, and explanation concepts; it reports precision and recall and uses their harmonic mean (F1) as the task score.

## Why This Matters

Concurrency bugs are among the most expensive defects in production software:
- They are **intermittent** — they may not manifest during testing but crash production systems under load.
- They are **costly** — a single race condition caused the 2003 Northeast blackout (affected 55M people), the Therac-25 radiation overdoses, and countless data corruption incidents.
- They require **deep reasoning about interleavings** — you must mentally simulate how multiple threads interact with shared state.
- **AI code review** is increasingly used in industry. If models miss concurrency bugs, engineers who trust AI reviews may ship dangerous code.

A model that can reliably detect concurrency bugs would save companies millions in debugging time. Our benchmark measures exactly this capability.

## Task Overview

| # | Task | Scenario | Bugs | Key Challenge |
|---|------|----------|------|---------------|
| 1 | Bank Transfer | Lock-ordering deadlock, non-atomic conditional transfer, unprotected audit sum | 3 | Opposite lock order, a check performed before locking, and an unlocked multi-account snapshot |
| 2 | Producer-Consumer | Condition predicates not rechecked after wake | 2 | Waiters must re-check the predicate after waking |
| 3 | Singleton | Reset race and connection-pool races | 4 | Python assignment publishes the singleton only after initialization; the actual issues are reset and pool synchronization |
| 4 | Read-Write Lock | Writer starvation, stale-read TOCTOU in read-modify-write, unsynchronized counters | 4 | Fairness, check/update separation, and unprotected counters |
| 5 | Thread Pool | Non-atomic task ID, shutdown-submit race, task loss on shutdown, spin-wait, dict mutation during iteration | 5 | Task identity, submission/shutdown ordering, queue draining, and result access |
| 6 | Event Bus | Subscriber list mutation during dispatch | 1 | Mutating a live Python list during iteration can skip callbacks; it does not raise `RuntimeError` in this example |
| 7 | Rate Limiter | Double-refill race, token check/decrement race, periodic polling | 3 | Separate shared-state operations are not protected by the declared lock |

**Total**: 7 tasks, 22 reference findings across all tasks.

## Grading Methodology

### Approach
The grader is **fully deterministic and code-based** — no LLM judge is used. Each model response is parsed as JSON and compared against the reference solution using a three-step matching algorithm:

1. **Function match**: The model must identify the correct function where the bug occurs (normalized for `self.` prefixes, class names, and parentheses).
2. **Bug type match**: The model must classify the bug correctly. A synonym table maps common variations (e.g., `data_race` → `race_condition`, `toctou` → `atomicity_violation`, `busy_wait` → `spin_wait`).
3. **Explanation quality**: The model's explanation must contain key concurrency concepts from the reference (checked via regex matching against a curated concept list).

### Scoring
- Precision = matched findings / reported findings; recall = matched findings / reference findings.
- Task score = F1, the harmonic mean of precision and recall. Extra or duplicate findings therefore reduce the score.
- Overall score = mean across all tasks
- **Pass rate (≥80%)**: percentage of trials where the model scores ≥ 0.8 on a task
- **pass@k**: percentage of tasks with at least one successful trial in the run
- **pass^k**: percentage of tasks where all requested trials completed and scored ≥ 0.8

### Grader Validation
The built-in validation checks task/reference file-set consistency plus 8 checks per task (56 per-task checks):
- ✅ Every task's declared finding count matches its reference
- ✅ Every reference solution scores 1.00
- ✅ Empty responses score 0.00
- ✅ Entirely wrong reports score 0.00
- ✅ An extra false positive lowers an otherwise perfect score
- ✅ Duplicate reports cannot earn duplicate credit
- ✅ Wrong function but right explanation: rejected
- ✅ Malformed finding entries are rejected without crashing

## How to Run

### Prerequisites
- Python 3.10+
- API keys for at least one provider

### Setup
```bash
# From the extracted submission directory
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your API keys
```

### Environment Variables
```
OPENAI_API_KEY=sk-...        # For GPT-4o, GPT-4o-mini, o3-mini
ANTHROPIC_API_KEY=sk-ant-... # For Claude Sonnet 4, Claude 3.5 Haiku
GOOGLE_API_KEY=AI...         # For Gemini 2.5 Flash, Gemini 2.5 Pro
```

### Run Commands

#### 1. CLI Evaluation
```bash
# Validate the grader first (56 built-in checks, no API keys needed)
python run_eval.py --validate-grader

# Run evaluation on all models with available API keys (3 trials each)
python run_eval.py --trials 3

# Run on a specific model
python run_eval.py --model gpt-4o --trials 3

# Dry run (show prompts without calling APIs)
python run_eval.py --dry-run
```

#### 2. REST API & Interactive Docs (FastAPI)
```bash
# Start API locally with uvicorn
uvicorn api.main:app --reload --port 8000

# Open Swagger UI in browser
# http://localhost:8000/docs
# Metrics endpoint: http://localhost:8000/metrics
```

#### 3. Web Dashboard (React + Vite)
```bash
cd frontend
npm install
npm run dev
# Dashboard available at http://localhost:5173
```

#### 4. One-Click Full-Stack Docker Deployment
```bash
# Start CLI benchmark, FastAPI backend, and React Dashboard together:
docker compose up --build

# Or use one-click scripts:
./run.ps1   # Windows PowerShell
./run.sh    # macOS / Linux
```

## System Architecture & Documentation

- 📐 **[System Architecture](docs/architecture.md)**: End-to-end Mermaid architecture diagrams, data flows, and tech stack details.
- 💼 **[Interview Talking Points](docs/interview_talking_points.md)**: Design trade-offs, concurrency reasoning, security measures, and scaling strategies for SDE interviews.
- 🚀 **[Cloud Run Deployment Guide](deploy/README.md)**: Production deployment instructions using Google Cloud Run and GitHub Container Registry.
- 🤝 **[Contributing Guidelines](CONTRIBUTING.md)**: Code style, linting, testing, and pull request checklist.

### Configured Model IDs

These are the identifiers in the current harness configuration. Provider model availability changes; verify each identifier with the provider before running.

| Model ID | Provider | Notes |
|----------|----------|-------|
| `gpt-4o` | OpenAI | Frontier |
| `gpt-4o-mini` | OpenAI | Smaller |
| `o3-mini` | OpenAI | Reasoning model |
| `claude-sonnet-4-20250514` | Anthropic | Frontier |
| `claude-3-5-haiku-20241022` | Anthropic | Smaller |
| `gemini-2.5-flash` | Google | Fast |
| `gemini-2.5-pro` | Google | Frontier |

## Results

### Summary Table

| Model (version, settings) | Trials per task | Mean F1 | Pass Rate (≥80%) | pass@k | pass^k | Tokens / runtime |
|---------------------------|-----------------|---------|-------------------|--------|--------|------------------|
| *No run recorded* | — | — | — | — | — | — |

> **No evaluation run has been recorded.** The files in `results/` are explicit placeholders, not evidence. Run `python run_eval.py --trials 3` with your own provider API key to generate actual outputs, scores, model IDs, and timestamps. Do not report expected or fabricated scores as results.

### Per-Task Analysis

After running the eval, check `results/summary.txt` and `results/summary.json` for:
- Per-task scores with min/max/mean across trials
- Most commonly missed bugs per task per model
- Precision, recall, F1 score, and detailed match/miss breakdowns

### Expected Failure Patterns

These are hypotheses from task design, not observed results:

1. **Condition predicate rechecking** (Task 2): Waiters must verify the condition again after returning from `wait()`.
2. **Writer starvation** (Task 4): Requires reasoning about continuous reader arrivals and lock fairness.
3. **Shutdown task loss** (Task 5): Workers can exit before draining queued tasks.
4. **Non-atomic counters** (Tasks 4, 5): Statistics and task IDs are updated outside a synchronization primitive.

## Cost and Runtime

- **Estimated tokens per task**: ~1500 prompt + ~800 completion = ~2300 tokens
- **Total tokens per full run** (7 tasks × 3 trials): ~48,000 tokens
- **Cost and runtime** vary by provider, model, input/output token rates, and API latency. Check current provider pricing; the harness records token counts and elapsed time but does not estimate monetary cost.
- **Before submission**, record the observed runtime and estimate cost from the provider's current input/output token prices and the recorded token usage; identify the pricing date and assumptions in the results description.

## Provenance

### What existed before the hackathon
- None. This benchmark was built entirely during the hackathon.

### Data sources
- All code snippets are **synthetic** — written specifically for this benchmark.
- No external datasets, copyrighted code, or confidential data is used.
- All task code is original, inspired by common concurrency patterns found in textbooks (Herlihy & Shavit, *The Art of Multiprocessor Programming*; Goetz et al., *Java Concurrency in Practice*).

### Prior work
- This benchmark is not adapted from any existing benchmark.
- The concurrency bug patterns are well-known in the systems engineering literature, but the specific task code and grading approach are original.

## AI Use Disclosure

AI assistance was used to review and correct the task references, scoring behavior, and documentation in this package. The package has not been evaluated against external models yet. The submitting author should review the task/reference pairs, run validation and model trials, and report only verified results.

## File Structure

```
./
├── README.md                          # Project documentation
├── pyproject.toml                     # Python package metadata (pip install .)
├── Dockerfile                         # Benchmark CLI container
├── Dockerfile.api                     # FastAPI production container
├── docker-compose.yml                 # Multi-service stack (CLI, API, Frontend)
├── run.ps1 / run.sh                   # One-click startup scripts
├── api/                               # FastAPI Backend
│   ├── main.py                        # REST routes, background jobs, rate limiter
│   └── models.py                      # Pydantic schemas (Task, Run, Trial)
├── frontend/                          # React + Vite Web Dashboard
│   ├── src/                           # Components, dashboard charts, API client
│   ├── Dockerfile & nginx.conf        # Production SPA container
│   └── package.json                   # Web dependencies
├── tasks/                             # 7 Benchmark task specifications
├── reference/                         # 7 Reference ground-truth solutions
├── graders/                           # Deterministic grading engine
│   └── grader.py
├── tests/                             # Automated test suite (Pytest, 75 tests, 92% coverage)
│   ├── test_api.py                    # REST API unit tests
│   ├── test_api_routes.py             # Additional route & health tests
│   ├── test_coverage_boost.py         # Mock provider & edge case coverage tests
│   ├── test_grader.py                 # Grader unit & integration tests
│   ├── test_integration_harness.py   # End-to-end integration test
│   └── test_run_eval.py               # Evaluation CLI tests
├── docs/                              # System documentation
│   ├── architecture.md                # System design & Mermaid diagrams
│   └── interview_talking_points.md    # SDE interview guide & trade-offs
├── deploy/                            # Deployment specifications
│   ├── cloudrun.yaml                  # Google Cloud Run service definition
│   └── README.md                      # Cloud Run step-by-step setup
├── .github/                           # CI/CD and open-source templates
│   ├── workflows/ci.yml               # Automated test, Trivy scan, GHCR publish
│   ├── ISSUE_TEMPLATE/                # Bug report & feature request templates
│   └── PULL_REQUEST_TEMPLATE.md       # PR guidelines & checklist
├── results/                           # Evaluation outputs (summary.json/txt)
└── transcripts/                       # Full model raw transcripts
```

## Main Failure Mode and Hot Take

**What the benchmark can show**: On a fixed set of synthetic tasks, it measures whether a model's reported findings match a reviewed reference. It does not by itself establish production safety, broad model capability, or generalization to other code. Report conclusions only after running the benchmark and reviewing the transcripts and scoring limitations.
