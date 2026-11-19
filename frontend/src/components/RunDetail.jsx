import React from "react";

export default function RunDetail({ run, onBack }) {
  const getScoreClass = (score) => {
    if (score == null) return "";
    if (score >= 0.8) return "high";
    if (score >= 0.5) return "mid";
    return "low";
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <button className="btn btn-sm" onClick={onBack}>
          ← Back to All Runs
        </button>
        <span className={`status-badge ${run.status}`}>{run.status}</span>
      </div>

      <div className="card">
        <h2>Run Overview: {run.model}</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="value">
              {run.overall_mean_score != null
                ? `${(run.overall_mean_score * 100).toFixed(1)}%`
                : "—"}
            </div>
            <div className="label">Overall F1 Score</div>
          </div>
          <div className="stat-card">
            <div className="value">
              {run.overall_pass_rate != null
                ? `${(run.overall_pass_rate * 100).toFixed(1)}%`
                : "—"}
            </div>
            <div className="label">Pass Rate (≥0.8)</div>
          </div>
          <div className="stat-card">
            <div className="value">
              {run.total_tokens?.toLocaleString() ?? 0}
            </div>
            <div className="label">Total Tokens</div>
          </div>
          <div className="stat-card">
            <div className="value">{run.tasks?.length ?? 0}</div>
            <div className="label">Tasks Evaluated</div>
          </div>
        </div>

        <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
          <p>
            <strong>Run ID:</strong> <code>{run.run_id}</code> |{" "}
            <strong>Provider:</strong> {run.provider} |{" "}
            <strong>Created:</strong> {new Date(run.created_at).toLocaleString()}
          </p>
        </div>
      </div>

      <div className="card">
        <h2>Per-Task Performance Breakdown</h2>
        {(!run.tasks || run.tasks.length === 0) ? (
          <p className="text-muted text-sm">
            {run.status === "running"
              ? "Evaluation is currently running in the background. Refresh in a moment..."
              : "No task results recorded for this run."}
          </p>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>Mean Score</th>
                  <th>Score Range</th>
                  <th>Pass Rate</th>
                  <th>pass@k</th>
                  <th>pass^k</th>
                  <th>Trials</th>
                </tr>
              </thead>
              <tbody>
                {run.tasks.map((t) => (
                  <tr key={t.task_id}>
                    <td>
                      <code>{t.task_id}</code>
                    </td>
                    <td>
                      <span
                        className={`score-badge ${getScoreClass(t.mean_score)}`}
                      >
                        {(t.mean_score * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="text-muted">
                      [{(t.min_score * 100).toFixed(0)}% -{" "}
                      {(t.max_score * 100).toFixed(0)}%]
                    </td>
                    <td>{(t.pass_rate_80pct * 100).toFixed(0)}%</td>
                    <td>{t.pass_at_k ? "✅" : "❌"}</td>
                    <td>{t.pass_all_k ? "✅" : "❌"}</td>
                    <td>{t.num_trials}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
