"""
ConcurrencyBugBench — FastAPI Backend
======================================
Endpoints:
    GET  /health              → Service health & available models.
    GET  /tasks               → List every benchmark task.
    GET  /tasks/{task_id}     → Single task detail.
    POST /evaluate            → Start an evaluation run (background).
    GET  /results             → List all completed runs.
    GET  /results/{run_id}    → Detailed result for one run.
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ── Path setup ────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "graders") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "graders"))

from api.models import (
    EvaluateRequest,
    HealthResponse,
    RunStatus,
    RunSummary,
    TaskInfo,
    TaskResult,
    TrialResult,
)
from graders.grader import grade_task

# ── Structured logging setup ─────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# ── Rate limiter setup ────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ── Load .env ─────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# ── Sentry observability (optional) ──────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=1.0)
        logger.info("sentry_initialized")
    except ImportError:
        logger.warning("sentry_sdk_not_installed")

# ── In-memory stores ─────────────────────────────────────────────

TASKS: dict[str, dict[str, Any]] = {}
RUNS: dict[str, RunSummary] = {}


def reload_tasks() -> None:
    TASKS.clear()
    tasks_dir = BASE_DIR / "tasks"
    if tasks_dir.exists():
        for fpath in sorted(tasks_dir.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                task = json.load(f)
            TASKS[task["task_id"]] = task


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup", tasks_loaded=len(TASKS))
    reload_tasks()
    yield
    logger.info("application_shutdown")


# ── App creation ──────────────────────────────────────────────────

app = FastAPI(
    title="ConcurrencyBugBench API",
    description=(
        "REST API for running and inspecting concurrency-bug-detection benchmarks."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiter middleware ───────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded, _rate_limit_exceeded_handler  # type: ignore[arg-type]
)

# ── Prometheus metrics ────────────────────────────────────────────
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app, endpoint="/metrics")

# Eagerly load tasks so they are available immediately
reload_tasks()

# ── Simple API-key auth ──────────────────────────────────────────

API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("BENCH_API_KEY", "dev-key-change-me")

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(
    key: str | None = Security(api_key_header),
) -> str | None:
    """Reject requests without a valid API key on write endpoints."""
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key


# ── Model configuration (mirrors run_eval.py) ────────────────────

MODEL_CONFIGS: dict[str, dict[str, Any]] = {
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
        "temperature": 1.0,
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

SYSTEM_PROMPT = (
    "You are an expert systems engineer specializing in concurrent and "
    "multithreaded programming. You have deep knowledge of threading primitives "
    "(locks, condition variables, semaphores), memory models, and common "
    "concurrency pitfalls.\n\n"
    "Your task is to perform a thorough code review of concurrent code and "
    "identify ALL concurrency bugs. Be precise and specific — identify the exact "
    "function, the exact type of bug, explain the mechanism, and provide a "
    "concrete interleaving that triggers it.\n\n"
    "You must return your answer as valid JSON. Do not include any text outside "
    "the JSON object."
)


# ── Helpers ───────────────────────────────────────────────────────


def _available_models() -> list[str]:
    key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    available = []
    for name, cfg in MODEL_CONFIGS.items():
        provider = str(cfg.get("provider", ""))
        if provider == "mock":
            available.append(name)
        elif os.environ.get(key_map.get(provider, ""), ""):
            available.append(name)
    return available


def _build_prompt(task: dict[str, Any]) -> str:
    return (
        f"## Task: {task['title']}\n\n"
        f"### Scenario\n{task['scenario']}\n\n"
        f"### Code to Review\n```python\n{task['code']}\n```\n\n"
        f"### Instructions\n{task['instruction']}\n\n"
        "### Output Format\n"
        'Return ONLY a valid JSON object with the key "bugs" '
        "containing an array of bug objects, each with keys: "
        '"function", "bug_type", "explanation", "interleaving".'
    )


def _call_model(prompt: str, config: dict[str, Any]):
    """Synchronous model call (runs in a thread via run_in_executor)."""
    import time

    provider = config["provider"]

    if provider == "openai":
        from openai import OpenAI

        openai_client = OpenAI()
        kwargs: dict[str, Any] = {
            "model": config["model_id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": config["max_tokens"],
        }
        if not str(config["model_id"]).startswith("o"):
            kwargs["temperature"] = config["temperature"]
        start = time.time()
        resp = openai_client.chat.completions.create(**kwargs)
        elapsed = time.time() - start
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        prompt_tokens = resp.usage.prompt_tokens if resp.usage else 0
        completion_tokens = resp.usage.completion_tokens if resp.usage else 0
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": tokens,
        }

    elif provider == "anthropic":
        from anthropic import Anthropic

        anthropic_client = Anthropic()
        start = time.time()
        anthropic_kwargs: dict[str, Any] = {
            "model": config["model_id"],
            "max_tokens": config["max_tokens"],
            "temperature": config["temperature"],
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = anthropic_client.messages.create(**anthropic_kwargs)
        elapsed = time.time() - start
        content = resp.content[0].text if resp.content else ""
        usage = {
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        }

    elif provider == "google":
        from google import genai
        from google.genai import types

        google_client = genai.Client()
        start = time.time()
        resp = google_client.models.generate_content(
            model=config["model_id"],
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=config["temperature"],
                max_output_tokens=config["max_tokens"],
            ),
        )
        elapsed = time.time() - start
        content = resp.text or ""
        usage = {
            "prompt_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0),
            "completion_tokens": getattr(
                resp.usage_metadata, "candidates_token_count", 0
            ),
            "total_tokens": getattr(resp.usage_metadata, "total_token_count", 0),
        }

    elif provider == "mock":
        tasks_dir = BASE_DIR / "tasks"
        ref_dir = BASE_DIR / "reference"
        matched_bugs = []
        for tf in sorted(tasks_dir.glob("*.json")):
            with open(tf, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            if tdata.get("title", "") in prompt or tdata.get("task_id", "") in prompt:
                ref_path = ref_dir / f"{tdata['task_id']}_reference.json"
                if ref_path.exists():
                    with open(ref_path, "r", encoding="utf-8") as rf:
                        matched_bugs = json.load(rf).get("bugs", [])
                break
        content = json.dumps({"bugs": matched_bugs}, indent=2)
        elapsed = 0.05
        usage = {
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": (len(prompt) + len(content)) // 4,
        }

    else:
        raise ValueError(f"Unknown provider: {provider}")

    return content, elapsed, usage


# ── Background evaluation runner ─────────────────────────────────


async def _run_evaluation(
    run_id: str,
    model_name: str,
    trials: int,
    task_ids: list[str] | None,
) -> None:
    """Execute the benchmark in the background and update RUNS."""
    run = RUNS[run_id]
    run.status = RunStatus.running
    config = MODEL_CONFIGS[model_name]
    reference_dir = BASE_DIR / "reference"
    total_tokens = 0
    task_results: list[TaskResult] = []
    loop = asyncio.get_event_loop()

    tasks_to_run = task_ids if task_ids else list(TASKS.keys())

    try:
        for tid in tasks_to_run:
            task = TASKS.get(tid)
            if task is None:
                continue
            ref_path = reference_dir / f"{tid}_reference.json"
            if not ref_path.exists():
                continue

            prompt = _build_prompt(task)
            trial_results: list[TrialResult] = []

            for t in range(trials):
                try:
                    content, elapsed, usage = await loop.run_in_executor(
                        None, _call_model, prompt, config
                    )
                    total_tokens += usage.get("total_tokens", 0)
                    grade = grade_task(content, str(ref_path))
                    trial_results.append(
                        TrialResult(
                            trial=t + 1,
                            score=grade["score"],
                            precision=grade["precision"],
                            recall=grade["recall"],
                            matched_bugs=grade.get("matched_bugs", []),
                            missed_bugs=grade.get("missed_bugs", []),
                            false_positives=grade.get("false_positives", []),
                            total_reference_bugs=grade["total_reference_bugs"],
                            model_bugs_reported=grade.get("model_bugs_reported", 0),
                            elapsed_seconds=elapsed,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    trial_results.append(
                        TrialResult(
                            trial=t + 1,
                            score=0.0,
                            precision=0.0,
                            recall=0.0,
                            total_reference_bugs=0,
                            error=str(exc),
                        )
                    )

            scores = [tr.score for tr in trial_results if tr.error is None]
            mean_s = sum(scores) / len(scores) if scores else 0.0
            task_results.append(
                TaskResult(
                    task_id=tid,
                    mean_score=mean_s,
                    max_score=max(scores) if scores else 0.0,
                    min_score=min(scores) if scores else 0.0,
                    pass_rate_80pct=(
                        (sum(1 for s in scores if s >= 0.8) / len(scores))
                        if scores
                        else 0.0
                    ),
                    pass_at_k=(max(scores) >= 0.8) if scores else False,
                    pass_all_k=(
                        (len(scores) == trials and min(scores) >= 0.8)
                        if scores
                        else False
                    ),
                    num_trials=len(scores),
                    trials=trial_results,
                )
            )

        run.tasks = task_results
        all_means = [tr.mean_score for tr in task_results]
        run.overall_mean_score = sum(all_means) / len(all_means) if all_means else 0.0
        all_pass = [tr.pass_rate_80pct for tr in task_results]
        run.overall_pass_rate = sum(all_pass) / len(all_pass) if all_pass else 0.0
        run.total_tokens = total_tokens
        run.status = RunStatus.completed
        run.completed_at = datetime.now(timezone.utc)

    except Exception:  # noqa: BLE001
        run.status = RunStatus.failed
        run.completed_at = datetime.now(timezone.utc)


# ── Endpoints ─────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    logger.info("health_check", tasks_loaded=len(TASKS), models_available=len(_available_models()))
    return HealthResponse(
        version="0.1.0",
        tasks_loaded=len(TASKS),
        models_available=_available_models(),
    )


@app.get("/tasks", response_model=list[TaskInfo], tags=["Tasks"])
async def list_tasks():
    return [
        TaskInfo(
            task_id=t["task_id"],
            title=t["title"],
            domain=t.get("domain", ""),
            difficulty=t.get("difficulty", ""),
            expected_bug_count=t.get("expected_bug_count", 0),
        )
        for t in TASKS.values()
    ]


@app.get("/tasks/{task_id}", response_model=TaskInfo, tags=["Tasks"])
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskInfo(
        task_id=task["task_id"],
        title=task["title"],
        domain=task.get("domain", ""),
        difficulty=task.get("difficulty", ""),
        expected_bug_count=task.get("expected_bug_count", 0),
    )


@app.post(
    "/evaluate",
    response_model=RunSummary,
    tags=["Evaluation"],
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit("10/minute")
async def start_evaluation(
    request: Request,
    req: EvaluateRequest,
    background_tasks: BackgroundTasks,
):
    logger.info("evaluation_request_received", model=req.model, trials=req.trials, tasks=req.tasks)
    if req.model not in MODEL_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown model '{req.model}'. "
                f"Available: {list(MODEL_CONFIGS.keys())}"
            ),
        )

    available = _available_models()
    if req.model not in available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No API key configured for model '{req.model}'. "
                "Set the appropriate env var."
            ),
        )

    run_id = str(uuid.uuid4())
    run = RunSummary(
        run_id=run_id,
        model=req.model,
        provider=str(MODEL_CONFIGS[req.model]["provider"]),
        status=RunStatus.pending,
        trials_per_task=req.trials,
        created_at=datetime.now(timezone.utc),
    )
    RUNS[run_id] = run

    logger.info("evaluation_started", run_id=run_id, model=req.model, trials=req.trials)
    background_tasks.add_task(_run_evaluation, run_id, req.model, req.trials, req.tasks)
    return run


@app.get("/results", response_model=list[RunSummary], tags=["Results"])
async def list_results():
    return list(RUNS.values())


@app.get("/results/{run_id}", response_model=RunSummary, tags=["Results"])
async def get_result(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
