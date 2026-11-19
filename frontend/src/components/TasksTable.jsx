import React, { useState } from "react";

export default function TasksTable({ tasks }) {
  const [filterDifficulty, setFilterDifficulty] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const filteredTasks = tasks.filter((t) => {
    const matchesDiff =
      filterDifficulty === "all" ||
      t.difficulty.toLowerCase() === filterDifficulty.toLowerCase();
    const matchesSearch =
      t.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.task_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.domain.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesDiff && matchesSearch;
  });

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2>📋 Benchmark Tasks ({tasks.length})</h2>
        <div className="flex gap-4">
          <input
            type="text"
            placeholder="Search tasks..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              padding: "6px 12px",
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--text)",
              fontSize: "0.85rem",
            }}
          />
          <select
            value={filterDifficulty}
            onChange={(e) => setFilterDifficulty(e.target.value)}
            style={{
              padding: "6px 12px",
              background: "var(--surface2)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              color: "var(--text)",
              fontSize: "0.85rem",
            }}
          >
            <option value="all">All Difficulties</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Task ID</th>
              <th>Title</th>
              <th>Domain</th>
              <th>Difficulty</th>
              <th>Expected Bugs</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.map((t) => (
              <tr key={t.task_id}>
                <td>
                  <code>{t.task_id}</code>
                </td>
                <td style={{ fontWeight: 500 }}>{t.title}</td>
                <td className="text-muted">{t.domain}</td>
                <td>
                  <span
                    className={`score-badge ${
                      t.difficulty === "hard" ? "high" : "mid"
                    }`}
                  >
                    {t.difficulty}
                  </span>
                </td>
                <td>
                  <strong>{t.expected_bug_count}</strong> reference bugs
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
