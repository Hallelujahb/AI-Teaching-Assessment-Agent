// Owner: P1. Every server call goes through this file.
// Plan: section 12, Person 1
const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    // Agree the real error shape with P2 and show field errors from 422 responses.
    const error = new Error((body && body.message) || "Request failed");
    error.status = res.status;
    error.details = body;
    throw error;
  }
  return body;
}

export const api = {
  health: () => request("/api/health"),
};
