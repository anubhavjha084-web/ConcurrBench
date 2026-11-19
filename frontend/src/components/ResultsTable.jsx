import React, { useState } from "react";

export default function ResultsTable({
  results,
  onViewRun,
  onRefresh,
  onDownloadJson,
  onDownloadCsv,
}) {
  const [filterModel, setFilterModel] = useState("all");
  const [sortCol, setSortCol] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  const models = Array.from(new Set(results.map((r) => r.model)));

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };

  const filteredResults = results.filter((r) => {
    return filterModel === "all" || r.model === filterModel;
  });

  const sortedResults = [...filteredResults].sort((a, b) => {
    let valA = a[sortCol];
    let valB = b[sortCol];

    if (valA == null) valA = sortDir === "asc" ? Infinity : -Infinity;
    if (valB == null) valB = sortDir === "asc" ? Infinity : -Infinity;

    if (sortCol === "created_at") {
      valA = new Date(a.created_at).getTime();
      valB = new Date(b.created_at).getTime();
    }

    if (typeof valA === "string") {
      const cmp = valA.localeCompare(valB);
      return sortDir === "asc" ? cmp : -cmp;
    }

    return sortDir === "asc" ? valA - valB : valB - valA;
  });

  const getScoreClass = (score) => {
    if (score === null || score === undefined) return "";
    if (score >= 0.8) return "high";
    if (score >= 0.5) return "mid";
    return "low";
  };

  const renderSortIndicator = (col) => {
    if (sortCol !== col) return <span style={{ opacity: 0.3 }}> ↕</span>;
    return sortDir === "asc" ? " ▲" : " ▼";
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2>📊 Benchmark Runs ({results.length})</h2>
        <div className="flex gap-4">
          <select
            value={filterModel}
            onChange={(e) => setFilterModel(e.target.value)}
            style={{
              padding: "6px 12px",
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--text)",
              fontSize: "0.85rem",
            }}
          >
            <option value="all">All Models</option>
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button className="btn btn-sm btn-primary" onClick={onRefresh}>
            🔄 Refresh
          </button>
          <button className="btn btn-sm" onClick={onDownloadJson}>
            💾 JSON
          </button>
          <button className="btn btn-sm" onClick={onDownloadCsv}>
            📄 CSV
          </button>
        </div>
      </div>

      {results.length === 0 ? (
        <div className="empty-state">
          <div className="icon">🚀</div>
          <p>No evaluation runs yet.</p>
          <p className="text-sm text-muted">
            Go to the "Run Benchmark" tab to trigger your first evaluation!
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th onClick={() => handleSort("model")}>
                  Model{renderSortIndicator("model")}
                </th>
                <th onClick={() => handleSort("status")}>
                  Status{renderSortIndicator("status")}
                </th>
                <th onClick={() => handleSort("trials_per_task")}>
                  Trials/Task{renderSortIndicator("trials_per_task")}
                </th>
                <th onClick={() => handleSort("overall_mean_score")}>
                  Mean F1 Score{renderSortIndicator("overall_mean_score")}
                </th>
                <th onClick={() => handleSort("overall_pass_rate")}>
                  Pass Rate (≥0.8){renderSortIndicator("overall_pass_rate")}
                </th>
                <th onClick={() => handleSort("total_tokens")}>
                  Tokens{renderSortIndicator("total_tokens")}
                </th>
                <th onClick={() => handleSort("created_at")}>
                  Timestamp{renderSortIndicator("created_at")}
                </th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((r) => (
                <tr key={r.run_id}>
                  <td>
                    <code>{r.run_id.slice(0, 8)}...</code>
                  </td>
                  <td style={{ fontWeight: 600 }}>{r.model}</td>
                  <td>
                    <span className={`status-badge ${r.status}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.trials_per_task}</td>
                  <td>
                    {r.overall_mean_score != null ? (
                      <span
                        className={`score-badge ${getScoreClass(
                          r.overall_mean_score
                        )}`}
                      >
                        {(r.overall_mean_score * 100).toFixed(1)}%
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {r.overall_pass_rate != null
                      ? `${(r.overall_pass_rate * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                  <td>{r.total_tokens?.toLocaleString() ?? 0}</td>
                  <td className="text-muted text-sm">
                    {new Date(r.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={() => onViewRun(r.run_id)}
                    >
                      Details →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
