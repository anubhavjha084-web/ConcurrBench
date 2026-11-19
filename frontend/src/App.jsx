import { useState, useEffect, useCallback } from "react";
import {
  fetchHealth,
  fetchTasks,
  fetchResults,
  fetchResult,
  startEvaluation,
  setApiKey,
  getStoredApiKey,
  downloadAsJson,
  downloadAsCsv,
} from "./api";
import TasksTable from "./components/TasksTable";
import ResultsTable from "./components/ResultsTable";
import RunDetail from "./components/RunDetail";
import RunBenchmark from "./components/RunBenchmark";
import ScoreChart from "./components/ScoreChart";

const TABS = ["Dashboard", "Tasks", "Run Benchmark", "Results"];

export default function App() {
  const [tab, setTab] = useState("Dashboard");
  const [apiKey, setApiKeyState] = useState(getStoredApiKey());
  const [health, setHealth] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [results, setResults] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [error, setError] = useState(null);

  // ── Load data ──────────────────────────────────────────────────
  const loadHealth = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setHealth(h);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const loadTasks = useCallback(async () => {
    try {
      const t = await fetchTasks();
      setTasks(t);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const loadResults = useCallback(async () => {
    try {
      const r = await fetchResults();
      setResults(r);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadHealth();
    loadTasks();
    loadResults();
  }, [loadHealth, loadTasks, loadResults]);

  // ── API key ────────────────────────────────────────────────────
  const handleSetApiKey = (key) => {
    setApiKey(key);
    setApiKeyState(key);
  };

  // ── Run evaluation ─────────────────────────────────────────────
  const handleRunEval = async (model, trials) => {
    try {
      setError(null);
      await startEvaluation(model, trials);
      setTab("Results");
      setTimeout(loadResults, 1000);
    } catch (e) {
      setError(e.message);
    }
  };

  // ── View run detail ────────────────────────────────────────────
  const handleViewRun = async (runId) => {
    try {
      const run = await fetchResult(runId);
      setSelectedRun(run);
    } catch (e) {
      setError(e.message);
    }
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="app-container">
      <header>
        <h1>🔒 ConcurrencyBugBench</h1>
        <div className="nav-tabs">
          {TABS.map((t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => {
                setTab(t);
                setSelectedRun(null);
                if (t === "Results") loadResults();
              }}
            >
              {t}
            </button>
          ))}
        </div>
      </header>

      {/* API key bar */}
      <div className="card" style={{ padding: "12px 20px" }}>
        <div className="api-key-bar">
          <label style={{ whiteSpace: "nowrap", fontSize: "0.85rem" }}>
            🔑 API Key:
          </label>
          <input
            type="password"
            placeholder="Enter your API key (stored in localStorage)"
            value={apiKey}
            onChange={(e) => handleSetApiKey(e.target.value)}
          />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="card"
          style={{ borderColor: "var(--danger)", color: "var(--danger)" }}
        >
          ⚠️ {error}
          <button
            className="btn btn-sm"
            style={{ marginLeft: 12 }}
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Dashboard ──────────────────────────────────────────── */}
      {tab === "Dashboard" && (
        <>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="value">{health?.tasks_loaded ?? "—"}</div>
              <div className="label">Benchmark Tasks</div>
            </div>
            <div className="stat-card">
              <div className="value">{results.length}</div>
              <div className="label">Evaluation Runs</div>
            </div>
            <div className="stat-card">
              <div className="value">
                {health?.models_available?.length ?? 0}
              </div>
              <div className="label">Models Available</div>
            </div>
            <div className="stat-card">
              <div className="value">{health?.status === "ok" ? "✅" : "❌"}</div>
              <div className="label">API Status</div>
            </div>
          </div>

          {results.length > 0 && (
            <div className="card">
              <h2>📊 Latest Results — Per-Task F1 Scores</h2>
              <div className="chart-container">
                <ScoreChart results={results} />
              </div>
            </div>
          )}

          <div className="card">
            <h2>ℹ️ About ConcurrencyBugBench</h2>
            <p className="text-muted text-sm">
              ConcurrencyBugBench is a 7-task evaluation benchmark for
              concurrency code review. Each task presents a Python program with
              documented concurrency defects. AI models identify bugs, classify
              types, explain mechanisms, and provide triggering interleavings.
              The deterministic grader reports precision, recall, and F1 scores.
            </p>
          </div>
        </>
      )}

      {/* ── Tasks ──────────────────────────────────────────────── */}
      {tab === "Tasks" && <TasksTable tasks={tasks} />}

      {/* ── Run Benchmark ──────────────────────────────────────── */}
      {tab === "Run Benchmark" && (
        <RunBenchmark
          models={health?.models_available || []}
          onRun={handleRunEval}
        />
      )}

      {/* ── Results ────────────────────────────────────────────── */}
      {tab === "Results" && !selectedRun && (
        <ResultsTable
          results={results}
          onViewRun={handleViewRun}
          onRefresh={loadResults}
          onDownloadJson={() => downloadAsJson(results)}
          onDownloadCsv={() => {
            const rows = results.map((r) => ({
              run_id: r.run_id,
              model: r.model,
              status: r.status,
              mean_score: r.overall_mean_score?.toFixed(3) ?? "",
              pass_rate: r.overall_pass_rate?.toFixed(3) ?? "",
              total_tokens: r.total_tokens,
              created_at: r.created_at,
            }));
            downloadAsCsv(rows);
          }}
        />
      )}

      {tab === "Results" && selectedRun && (
        <RunDetail run={selectedRun} onBack={() => setSelectedRun(null)} />
      )}

      {/* Footer */}
      <footer
        style={{
          textAlign: "center",
          padding: "32px 0 16px",
          color: "var(--text-muted)",
          fontSize: "0.8rem",
        }}
      >
        ConcurrencyBugBench v0.1.0 · Built with FastAPI + React + Vite
      </footer>
    </div>
  );
}
