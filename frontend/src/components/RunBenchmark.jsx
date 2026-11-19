import React, { useState } from "react";

const DEFAULT_MODELS = [
  "gpt-4o",
  "gpt-4o-mini",
  "o3-mini",
  "claude-sonnet-4-20250514",
  "claude-3-5-haiku-20241022",
  "gemini-2.5-flash",
  "gemini-2.5-pro",
];

export default function RunBenchmark({ models, onRun }) {
  const [selectedModel, setSelectedModel] = useState(
    models.length > 0 ? models[0] : "gpt-4o"
  );
  const [trials, setTrials] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  const modelOptions = models.length > 0 ? models : DEFAULT_MODELS;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onRun(selectedModel, parseInt(trials, 10));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 600, margin: "0 auto" }}>
      <h2>⚡ Launch Benchmark Evaluation</h2>
      <p className="text-muted text-sm mb-4">
        Select a configured model and trial count to run the full
        7-task suite through the deterministic evaluation grader.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Target AI Model</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          {models.length === 0 && (
            <p className="text-sm text-muted mt-4" style={{ color: "var(--warning)" }}>
              ⚠️ No API keys actively detected in backend environment. Ensure
              OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY are configured.
            </p>
          )}
        </div>

        <div className="form-group">
          <label>Trials per Task (1 to 10)</label>
          <input
            type="number"
            min="1"
            max="10"
            value={trials}
            onChange={(e) => setTrials(e.target.value)}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: "100%", marginTop: 12 }}
          disabled={submitting}
        >
          {submitting ? "Initiating Run..." : "🚀 Start Evaluation Run"}
        </button>
      </form>
    </div>
  );
}
