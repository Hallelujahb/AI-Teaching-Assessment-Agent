// Super admin home: who is on the platform, what is waiting, and how the AI is doing. Oversight only: no grading here.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StatusBadge from "../components/StatusBadge.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { when } from "../util.js";

export default function AdminDashboard({ user, onGo }) {
  const [d, setD] = useState(null);
  const [users, setUsers] = useState([]);
  const [waiting, setWaiting] = useState([]);
  const [err, setErr] = useState(null);
  useEffect(() => {
    Promise.all([api.dashboard(), api.adminUsers(), api.approvals()])
      .then(([dash, u, a]) => { setD(dash); setUsers(u); setWaiting(a); })
      .catch(setErr);
  }, []);
  if (!d) return err ? <ErrorBanner error={err} /> : <p className="muted">Loading...</p>;

  const count = (role) => users.filter((u) => u.role === role && u.status === "active").length;
  const s = d.stats;
  const stat = (label, value, note) => <div className="panel stat"><span className="muted small">{label}</span><div className="big num">{value}</div>{note && <span className="muted small">{note}</span>}</div>;

  return (
    <div className="stack">
      <div><h1>Welcome back, {user.name}</h1><p className="muted">You oversee the platform. Lecturers create assessments and grade; you manage who has access.</p></div>
      <div className="stats">
        {stat("Lecturers", count("lecturer"), "active accounts")}
        {stat("Students", count("student"), "active accounts")}
        {stat("Waiting for approval", waiting.length, "sign-up requests")}
        {stat("Assessments", s.assessments)}
        {stat("Confirmed results", s.confirmed_students, `students in ${s.confirmed_batches} batches`)}
        {stat("AI agreement", s.agreement == null ? "-" : s.agreement + "%", "scores lecturers kept as proposed")}
      </div>
      <div className="row">
        <button className="btn primary" onClick={() => onGo("users")}>Manage users</button>
        <button className="btn" onClick={() => onGo("approvals")}>{waiting.length ? `Review ${waiting.length} request${waiting.length === 1 ? "" : "s"}` : "Approvals"}</button>
        <button className="btn" onClick={() => onGo("results")}>Saved results</button>
      </div>
      <div className="panel stack">
        <h3>Recent AI runs</h3>
        {!d.recent_runs.length && <p className="muted small">No runs yet.</p>}
        {d.recent_runs.slice(0, 6).map((r) => (
          <div key={r.id} className="feed"><div className="row between"><strong className="small">{r.label}</strong><StatusBadge status={r.status} /></div><span className="muted small">{when(r.started_at)}</span></div>
        ))}
        <button className="link small" onClick={() => onGo("runs")}>Open run details</button>
      </div>
    </div>
  );
}
