/**
 * API client for the ConcurrencyBugBench backend.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

function getApiKey() {
  return localStorage.getItem("bench_api_key") || "";
}

export function setApiKey(key) {
  localStorage.setItem("bench_api_key", key);
}

export function getStoredApiKey() {
  return getApiKey();
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  return res.json();
}

// ── Endpoints ────────────────────────────────────────────────────

export async function fetchHealth() {
  return request("/health");
}

export async function fetchTasks() {
  return request("/tasks");
}

export async function fetchTask(taskId) {
  return request(`/tasks/${taskId}`);
}

export async function startEvaluation(model, trials, tasks = null) {
  const body = { model, trials };
  if (tasks) body.tasks = tasks;
  return request("/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchResults() {
  return request("/results");
}

export async function fetchResult(runId) {
  return request(`/results/${runId}`);
}

/**
 * Export results as a downloadable JSON/CSV file.
 */
export function downloadAsJson(data, filename = "results.json") {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadAsCsv(rows, filename = "results.csv") {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => JSON.stringify(r[h] ?? "")).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
