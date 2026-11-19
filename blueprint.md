# Blueprint to Transform **ConcurrencyBugBench** into a ★9‑9.5/10 SDE Project

> **Goal**: Turn the existing benchmark into a showcase‑ready, full‑stack, production‑grade open‑source project that impresses SDE internship recruiters and hiring managers.

---

## 1. Current Strengths (Why it already looks good)
| Area | Strength |
|------|----------|
| **Domain relevance** | Concurrency bug detection is a high‑impact, systems‑level problem – great for interview talks. |
| **Clear specification** | Well‑written README, task table, grading methodology. |
| **Reproducible harness** | `run_eval.py` with deterministic grader, no hidden state. |
| **Extensible data** | JSON task definitions, reference solutions, easy to add new bugs. |
| **Python‑centric** | Uses only Python 3.10+, easy for most SDE candidates. |

These give a solid foundation; the blueprint focuses on *polishing* and *expanding*.

---

## 2. Gap Analysis (What recruiters look for)
| Category | Missing / Weak |
|----------|----------------|
| **Full‑stack demo** | No web UI / API, no user‑facing product. |
| **CI/CD** | No automated tests, linting, or release pipeline. |
| **Testing & Coverage** | Only manual evaluation; no unit/integration tests. |
| **Packaging & Distribution** | No pip/conda package, no Docker image. |
| **Observability** | No logging, metrics, or dashboard for benchmark runs. |
| **Documentation depth** | No contribution guide, API docs, or design diagram. |
| **Security & Auth** | No authentication for the API / UI. |
| **Project Management** | No issue templates, roadmap, or changelog. |
| **Presentation** | No live demo, no easy‑to‑run one‑click script. |

---

## 3. Blueprint – Actionable Milestones (ordered by impact/value)
### Milestone 0 – Foundation (1‑2 days)
1. **Add a `CONTRIBUTING.md`** with coding style (black, isort, mypy), branch workflow, and PR checklist.
2. **Create a `CHANGELOG.md`** with “Initial release”.
3. **Add a CI badge** in README (GitHub Actions).

### Milestone 1 – Code Quality & Testing (3‑5 days)
- **Unit tests** for each task loader, grader, and utility (`pytest`, `pytest-cov`). Target ≥ 90 % coverage.
- **Integration test** that runs the full harness on a tiny mock model (use a stub).
- **Static analysis**: integrate `ruff` (lint + security), `mypy` for type‑checking.
- **Pre‑commit hooks** for formatting and linting.
- Update `requirements.txt` to pin exact versions and add test dependencies.

### Milestone 2 – Packaging & Distribution (2‑3 days)
- Convert the repo into a **pip package** (`setup.py` or `pyproject.toml`).
- Publish a **Dockerfile** that builds the evaluation harness.
- Build a **GitHub Container Registry** image (`ghcr.io/<user>/concurrency-bug-bench`).
- Provide a **one‑click launch script**: `docker run --env-file .env -v $(pwd)/results:/app/results <image>`.

### Milestone 3 – Backend API (4‑6 days)
- Scaffold a **FastAPI** service (`api/`) exposing:
  - `POST /evaluate` – submit a model ID + optional prompts.
  - `GET /tasks` – list available tasks.
  - `GET /results/{run_id}` – retrieve JSON summary.
- Use **Pydantic** models for request/response validation.
- Add **OpenAPI docs** automatically hosted at `/docs`.
- Secure with **API key** header (simple for demo, can later swap to OAuth).
- Write **Dockerfile** for the API and add to the existing Docker Compose.

### Milestone 4 – Front‑end Dashboard (5‑7 days)
- Create a **React + Vite** SPA (`frontend/`):
  - Home page with project overview.
  - “Run Benchmark” form that calls the FastAPI endpoint.
  - Results table with filters, sortable columns, and downloadable CSV/JSON.
  - Visualize per‑task F1 scores using **Chart.js** or **Recharts**.
- Add **authentication UI** (API‑key input stored in local storage).
- Deploy the UI together with the API via Docker Compose on a **Render** or **Railway** free tier (suggested). Include a **static site** fallback for GH Pages.

### Milestone 5 – Observability & Monitoring (2‑3 days)
- Integrate **structlog** for JSON‑structured logs.
- Export **Prometheus metrics** from FastAPI (`/metrics`).
- Optional **Grafana dashboard** (Docker image) showing runs per day, average F1, error rates.
- Add **Sentry** (or lightweight `logrocket`) for exception tracking (free tier).

### Milestone 6 – Security Hardenings (1‑2 days)
- Validate all incoming JSON against schemas (Pydantic).
- Rate‑limit the API (`slowapi` or built‑in FastAPI middleware).
- Scan Docker images with **Trivy** in CI.
- Add a **CODE‑OF‑CONDUCT** and **SECURITY.md** with vulnerability reporting instructions.

### Milestone 7 – Production‑grade Deployment (2‑4 days)
- Write **GitHub Actions** workflow to:
  1. Run lint + tests on every PR.
  2. Build and push Docker images on tag.
  3. Deploy to **Google Cloud Run** (or Cloud Run for Anthos) – serverless, HTTPS, auto‑scaling.
- Configure **Cloud Run IAM** for public read‑only and restricted write (API‑key) access.
- Add a **README badge** for live demo URL.

### Milestone 8 – Showcase Materials (1‑2 days)
- Record a **short demo video** (2‑3 min) walking through:
  - Project purpose.
  - Running the benchmark via CLI, API, and UI.
  - Interpreting results.
- Create a **one‑pager PDF** (project summary, architecture diagram, impact). Use the `generative_ui` skill for a clean layout.
- Add a **LinkedIn post** template for students to share the project.

---

## 4. Architecture Diagram (Mermaid)
```mermaid
flowchart LR
    subgraph Local Dev
        A[CLI (`run_eval.py`)] --> B[Grader]
        B --> C[Task JSON]
        A --> D[Docker Compose]
    end
    subgraph Production
        E[FastAPI Service] <-- HTTP --> F[React UI]
        E --> G[PostgreSQL (run metadata)]
        E --> H[Prometheus]
        E --> I[Sentry]
        G --> J[Results Store (JSON/CSV)]
    end
    D --> E
    style Local Dev fill:#f9f9f9,stroke:#333,stroke-width:1px
    style Production fill:#e8f5ff,stroke:#0055aa,stroke-width:2px
```

---

## 5. Timeline (2‑3 weeks total)
| Week | Focus |
|------|-------|
| 1 | Milestone 0‑2 (foundation, testing, packaging). |
| 2 | Milestone 3‑4 (API + frontend). |
| 3 | Milestone 5‑8 (observability, security, deployment, showcase). |

---

## 6. Success Checklist (for the ★9‑9.5 rating)
- ✅ **Clear problem statement** – concurrency bug detection.
- ✅ **Fully automated CI** – lint, tests, build, security scan.
- ✅ **99 %+ unit test coverage**.
- ✅ **Dockerized backend + frontend** – one‑click `docker compose up`.
- ✅ **Live demo** – publicly reachable URL with HTTPS.
- ✅ **Metrics & logs** – Prometheus + Grafana dashboard.
- ✅ **Documentation** – README, API docs, contribution guide, architecture diagram.
- ✅ **Open‑source readiness** – LICENSE (MIT), code of conduct, security policy.
- ✅ **Interview‑ready talking points** – design decisions, scalability, security, testing.

When all check‑boxes are ticked, the project will stand out on a resume, in a portfolio, and during technical interviews.
