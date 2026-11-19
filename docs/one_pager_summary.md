# ConcurrBench: Showcase & Impact One-Pager
**Benchmark & Developer Platform for Evaluating AI on Concurrency Bug Detection**

---

## 1. Executive Summary & Problem Statement
Modern multi-core systems and cloud-native services depend fundamentally on concurrent software. However, **concurrency bugs** (data races, deadlocks, atomicity violations, reader-writer starvation, stale-read TOCTOU) remain the costliest and most elusive defects in production:
- **Heisenbugs**: Non-deterministic interleavings rarely fail in typical unit tests, but crash systems under live production traffic.
- **Catastrophic Impact**: Infamous historic race conditions caused the 2003 Northeast blackout (55M people affected), Therac-25 medical radiation overdoses, and severe financial ledger desynchronizations.
- **The AI Review Gap**: Engineers increasingly rely on LLM-assisted code reviews. If an AI reviewer cannot rigorously mentally simulate thread interleavings, dangerous code gets merged into mission-critical pipelines.

**ConcurrBench** provides an automated, rigorous, and 100% deterministic evaluation harness measuring whether AI models can identify, classify, and explain subtle concurrency flaws with concrete execution interleavings.

---

## 2. System Architecture

```
                    +------------------------------------+
                    |        ConcurrBench Harness        |
                    +------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                                                         |
         v                                                         v
+-----------------+   REST (HTTP)    +-------------------+   REST    +------------------+
|   React + Vite  | <--------------> |  FastAPI Service  | <-------> | Evaluation CLI   |
|  SPA Dashboard  |                  | (Prometheus, Auth)|           | (run_eval.py)    |
+-----------------+                  +-------------------+           +------------------+
         |                                     |                              |
         v                                     v                              v
[ Interactive UI ]                    [ Structured Logs ]             [ Grader Engine ]
- Real-time runs                      - JSON structlog                - Deterministic F1
- Filter & Sort Results               - Metrics (/metrics)            - Keyword concept check
- Score charts (Recharts)             - Sentry Integration            - Bug type synonym map
```

---

## 3. Key Benchmark Tasks & Vulnerabilities

| # | Benchmark Task | Real-World Scenario | Concurrency Bugs Audited |
|---|----------------|---------------------|--------------------------|
| **1** | **Bank Account Transfer** | Financial ledger & balances | Lock-ordering deadlock, non-atomic conditional transfer, unprotected audit sum |
| **2** | **Producer-Consumer Queue** | Message broker buffer | Missed signals, condition predicate not rechecked in loop after wake (`wait` vs `while`) |
| **3** | **Thread-Safe Singleton** | Database connection pool | Double-checked locking breakdown, reset race, pool synchronization leaks |
| **4** | **Read-Write Lock** | High-throughput in-memory cache | Writer starvation, stale-read TOCTOU in read-modify-write, unsynchronized metrics |
| **5** | **Thread Pool Executor** | Background worker queue | Non-atomic task ID generation, shutdown-submit race, task loss on termination |
| **6** | **Publish-Subscribe Event Bus** | Event-driven microservices | Live collection mutation during subscriber dispatch, callback corruption |
| **7** | **Token Bucket Rate Limiter** | API gateway throttling | Double-refill race, token check-then-decrement race condition |

---

## 4. Key Metrics & Technical Achievements
- **Deterministic Grader**: Zero LLM-judge hallucination or grading drift. Matches function name, canonicalized bug-type synonym graphs, and key concept regexes.
- **Mathematical Scoring Rigor**: Measures Precision, Recall, Task F1 score, Pass@k, and Pass^k.
- **Quality & Test Coverage**: **75 tests passing (100% pass rate)** with **92% line coverage** across backend, evaluation harness, and grading suite.
- **Enterprise Observability & Security**:
  - API Key protection (`X-API-Key`) on execution endpoints.
  - Rate limiting via `slowapi` to protect against DDoS.
  - Prometheus metrics instrumentation (`/metrics`) and provisioned Grafana dashboards.
  - Production-ready Docker Compose stack (`api`, `frontend`, `prometheus`, `grafana`).

---

## 5. Repository & Links
- **GitHub**: [https://github.com/anubhavjha084-web/ConcurrBench](https://github.com/anubhavjha084-web/ConcurrBench)
- **License**: MIT Open Source
