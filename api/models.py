"""
Pydantic models for the ConcurrencyBugBench API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ── Enums ─────────────────────────────────────────────────────────


class ModelProvider(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    google = "google"


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ── Request schemas ───────────────────────────────────────────────


class EvaluateRequest(BaseModel):
    model: str = Field(..., description="Model key, e.g. 'gpt-4o'")
    trials: int = Field(default=3, ge=1, le=10, description="Number of trials per task")
    tasks: list[str] | None = Field(
        default=None,
        description="Specific task IDs to run (default: all)",
    )


# ── Response schemas ──────────────────────────────────────────────


class BugFinding(BaseModel):
    function: str
    bug_type: str
    explanation: str
    interleaving: str | None = None


class TaskInfo(BaseModel):
    task_id: str
    title: str
    domain: str
    difficulty: str
    expected_bug_count: int


class TrialResult(BaseModel):
    trial: int
    score: float
    precision: float
    recall: float
    matched_bugs: list[str] = []
    missed_bugs: list[str] = []
    false_positives: list[str] = []
    total_reference_bugs: int = 0
    model_bugs_reported: int = 0
    elapsed_seconds: float | None = None
    error: str | None = None


class TaskResult(BaseModel):
    task_id: str
    mean_score: float
    max_score: float
    min_score: float
    pass_rate_80pct: float
    pass_at_k: bool
    pass_all_k: bool
    num_trials: int
    trials: list[TrialResult] = []


class RunSummary(BaseModel):
    run_id: str
    model: str
    provider: str
    status: RunStatus
    trials_per_task: int
    created_at: datetime
    completed_at: datetime | None = None
    overall_mean_score: float | None = None
    overall_pass_rate: float | None = None
    total_tokens: int = 0
    tasks: list[TaskResult] = []


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    tasks_loaded: int
    models_available: list[str]
