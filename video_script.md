# ConcurrencyBugBench — Demo Walkthrough Script

> **Target length**: 2–3 minutes  
> **Audience**: Hackathon judges, engineers interested in AI-assisted code review

---

## 0:00 – 0:20 | Introduction & Motivation

> *[Screen: Title slide or README header]*

"Hi, this is ConcurrencyBugBench — a benchmark that measures how well AI models detect concurrency bugs in Python code.

Concurrency bugs are some of the most dangerous defects in production software. They're intermittent, hard to reproduce, and have caused real-world disasters — from the 2003 Northeast blackout to the Therac-25 radiation incidents.

As AI-powered code review becomes mainstream, we need to know: can these models actually catch race conditions, deadlocks, and atomicity violations? That's exactly what this benchmark measures."

---

## 0:20 – 0:50 | The Benchmark Tasks

> *[Screen: `tasks/` folder or task table from README]*

"The benchmark includes 7 hand-crafted tasks with 22 total concurrency bugs — covering patterns like lock-ordering deadlocks, producer-consumer races, writer starvation, and shutdown task loss.

Each task presents a Python program with realistic concurrency code. The model must identify the buggy function, classify the bug type, explain the mechanism, and provide a triggering interleaving.

Crucially, grading is fully deterministic — no LLM judge. We match against reference solutions using function names, bug type synonyms, and concept-based explanation scoring, then compute precision, recall, and F1."

---

## 0:50 – 1:20 | Running the CLI

> *[Screen: Terminal]*

"Let's run it. First, validate the grader — this runs 56 built-in checks, no API keys needed:"

```bash
python run_eval.py --validate-grader
```

> *[Show passing output]*

"Now let's run a real evaluation. With API keys set in `.env`, we can target a specific model:"

```bash
python run_eval.py --model gpt-4o --trials 3
```

> *[Show output: per-task scores, precision, recall, F1]*

"Each task runs 3 trials. We get min, max, and mean F1 scores, plus pass rates at the 80% threshold. Results are saved to `results/summary.json` for further analysis."

---

## 1:20 – 1:50 | The REST API

> *[Screen: Browser at `http://localhost:8000/docs`]*

"The project also ships a full FastAPI backend. Let's start it:"

```bash
docker compose up api
```

> *[Navigate to `/docs`]*

"The Swagger UI shows all our endpoints: health checks, task listing, evaluation triggers, and results retrieval. The `/evaluate` endpoint runs benchmarks asynchronously — submit a request and poll `/results/{run_id}` for the outcome.

Write endpoints require an API key via the `X-API-Key` header. We've also added rate limiting, structured logging with structlog, and Prometheus metrics at `/metrics`."

---

## 1:50 – 2:20 | The Web Dashboard

> *[Screen: Browser showing the React frontend]*

"For a visual experience, we have a React dashboard. It connects to the API and lets you browse tasks, trigger evaluations, and see results in an interactive UI.

You can select a model, set the number of trials, and watch results come in. The dashboard shows per-task F1 scores, precision/recall breakdowns, and highlights which bugs each model caught or missed."

---

## 2:20 – 2:50 | Interpreting Results & CI/CD

> *[Screen: Results summary or CI pipeline]*

"Here's how to read the results. F1 is the primary metric — the harmonic mean of precision and recall. A model that reports extra false positives gets penalized on precision; one that misses bugs gets penalized on recall.

We also track pass@k (did the model succeed at least once?) and pass^k (did it succeed every time?) — which reveals consistency.

On the infrastructure side, our GitHub Actions pipeline runs linting, type checking, and tests on every push. On version tags, it automatically builds and pushes Docker images to GitHub Container Registry. We include a Cloud Run deployment config for production."

---

## 2:50 – 3:00 | Closing

> *[Screen: Architecture diagram or README]*

"ConcurrencyBugBench gives the community a reproducible, deterministic way to measure AI code review on one of the hardest problem categories in software engineering. All code is original, all grading is transparent, and the entire system — from CLI to cloud deployment — is containerized and ready to run.

Thanks for watching."
