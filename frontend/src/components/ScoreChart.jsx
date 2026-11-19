import React from "react";

export default function ScoreChart({ results }) {
  // Take up to the 6 most recent completed runs
  const completed = results
    .filter((r) => r.status === "completed" && r.overall_mean_score != null)
    .slice(-6);

  if (completed.length === 0) {
    return (
      <div className="empty-state" style={{ padding: 24 }}>
        <p className="text-muted text-sm">
          Run evaluations to see comparative performance metrics.
        </p>
      </div>
    );
  }

  const chartHeight = 250;
  const barWidth = 45;
  const gap = 35;
  const paddingLeft = 60;
  const paddingBottom = 40;
  const width = Math.max(500, paddingLeft + completed.length * (barWidth + gap) + 40);

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${width} ${chartHeight + paddingBottom}`}
        style={{ width: "100%", height: "300px" }}
      >
        {/* Y-axis guidelines */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((tick) => {
          const y = chartHeight - tick * chartHeight + 20;
          return (
            <g key={tick}>
              <line
                x1={paddingLeft}
                y1={y}
                x2={width - 20}
                y2={y}
                stroke="var(--border)"
                strokeDasharray="4 4"
              />
              <text
                x={paddingLeft - 10}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="var(--text-muted)"
              >
                {(tick * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {completed.map((run, i) => {
          const score = run.overall_mean_score ?? 0;
          const barH = score * chartHeight;
          const x = paddingLeft + i * (barWidth + gap) + 15;
          const y = chartHeight - barH + 20;

          const color =
            score >= 0.8
              ? "var(--success)"
              : score >= 0.5
              ? "var(--warning)"
              : "var(--danger)";

          return (
            <g key={run.run_id}>
              {/* Bar */}
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barH}
                fill={color}
                rx={6}
                opacity={0.85}
              />
              {/* Score label above bar */}
              <text
                x={x + barWidth / 2}
                y={y - 8}
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="var(--text)"
              >
                {(score * 100).toFixed(1)}%
              </text>
              {/* Model label below bar */}
              <text
                x={x + barWidth / 2}
                y={chartHeight + 38}
                textAnchor="middle"
                fontSize="10"
                fill="var(--text-muted)"
              >
                {run.model.length > 12
                  ? `${run.model.slice(0, 10)}..`
                  : run.model}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
