// Owner: P1. Every server call goes through this file.
const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
let token = localStorage.getItem("qeleme_token") || "";
let onExpired = () => {};

export const setToken = (t) => {
  token = t || "";
  if (t) localStorage.setItem("qeleme_token", t); else localStorage.removeItem("qeleme_token");
};
export const hasToken = () => !!token;
export const onUnauthorized = (fn) => { onExpired = fn; };

async function request(path, options = {}) {
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
  return body;
}
const post = (path, data = {}) => request(path, { method: "POST", body: JSON.stringify(data) });

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