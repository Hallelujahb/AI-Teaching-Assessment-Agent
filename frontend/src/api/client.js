// Owner: P1. Every server call goes through this file.
// GET answers are kept for 30 seconds so moving between pages is instant; any change clears them.
const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
let token = localStorage.getItem("qeleme_token") || "";
let onExpired = () => {};
const cache = new Map();
const TTL = 30000;

export const setToken = (t) => {
  token = t || "";
  cache.clear();
  if (t) localStorage.setItem("qeleme_token", t); else localStorage.removeItem("qeleme_token");
};
export const hasToken = () => !!token;
export const onUnauthorized = (fn) => { onExpired = fn; };

async function request(path, options = {}) {
  const isGet = !options.method || options.method === "GET";
  if (isGet) { const hit = cache.get(path); if (hit && Date.now() - hit.t < TTL) return hit.v; }
  const res = await fetch(base + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token && !path.includes("/auth/")) onExpired();
    const error = new Error((body && (body.message || body.error)) || "Request failed");
    error.status = res.status;
    error.details = body;
    throw error;
  }
  if (isGet) cache.set(path, { v: body, t: Date.now() }); else cache.clear();
  return body;
}
const send = (method) => (path, data = {}) => request(path, { method, body: JSON.stringify(data) });
const post = send("POST");

export const api = {
  health: () => request("/api/health"),
  login: (email, password, as) => post("/api/auth/login", { email, password, as }),
  register: (data) => post("/api/auth/register", data),
  me: () => request("/api/auth/me"),
  dashboard: () => request("/api/dashboard"),
  approvals: () => request("/api/approvals"),
  approve: (id) => post(`/api/approvals/${id}/approve`),
  reject: (id) => post(`/api/approvals/${id}/reject`),
  assessments: () => request("/api/assessments"),
  assessment: (id) => request(`/api/assessments/${id}`),
  createAssessment: (data) => post("/api/assessments", data),
  updateAssessment: (id, data) => send("PUT")(`/api/assessments/${id}`, data),
  deleteAssessment: (id) => request(`/api/assessments/${id}`, { method: "DELETE" }),
  students: () => request("/api/students"),
  batches: (id) => request(`/api/assessments/${id}/batches`),
  addBatch: (id, data) => post(`/api/assessments/${id}/batches`, data),
  grade: (data) => post("/api/agent/grade", data),
  run: (id) => request(`/api/runs/${id}`),
  review: (batchId, data) => post(`/api/batches/${batchId}/review`, data),
  results: () => request("/api/results"),
  batchResults: (id) => request(`/api/batches/${id}/results`),
  myResults: () => request("/api/me/results"),
  adminUsers: () => request("/api/admin/users"),
  adminAddUser: (data) => post("/api/admin/users", data),
  adminResetPassword: (id, password) => post(`/api/admin/users/${id}/password`, { password }),
  adminDeleteUser: (id) => request(`/api/admin/users/${id}`, { method: "DELETE" }),
};