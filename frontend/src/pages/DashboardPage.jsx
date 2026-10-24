// Lecturer and super admin home: where every batch stands, and what to do next.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StatusBadge from "../components/StatusBadge.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { when } from "../util.js";

const TABS = [["all", "All"], ["ready", "Ready to grade"], ["review", "Awaiting review"], ["confirmed", "Confirmed"]];

export default function DashboardPage({ user, onGo, onGrade, onReview, onResults }) {
  const [d, setD] = useState(null);
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [err, setErr] = useState(null);
  useEffect(() => { api.dashboard().then(setD).catch(setErr); }, []);
  if (!d) return err ? <ErrorBanner error={err} /> : <p className="muted">Loading...</p>;

  const s = d.stats;
  const shown = d.batches.filter((b) => (tab === "all" || b.stage === tab) && (b.title + b.label).toLowerCase().includes(q.toLowerCase()));
  const stat = (label, value, note) => <div className="panel stat"><span className="muted small">{label}</span><div className="big num">{value}</div>{note && <span className="muted small">{note}</span>}</div>;

  return (
    <div className="stack">
      <div><h1>Welcome back, {user.name}</h1><p className="muted">Nothing is published until you confirm it.</p></div>
      <div className="stats">
        {stat("Assessments", s.assessments)}
        {stat("Ready to grade", s.ready, "batches")}
        {stat("Awaiting your review", s.review, "batches")}
        {stat("Confirmed", s.confirmed_students, `students in ${s.confirmed_batches} batches`)}
        {stat("AI agreement", s.agreement == null ? "-" : s.agreement + "%", "scores you kept as proposed")}
      </div>
      <div className="dash">
        <div className="stack">
          <div className="panel row">
            <div className="row" style={{ flex: 1, gap: ".25rem" }}>{TABS.map(([id, l]) => <button key={id} className={"tab" + (tab === id ? " on" : "")} onClick={() => setTab(id)}>{l}</button>)}</div>
            <input style={{ maxWidth: 220 }} placeholder="Search batches" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search batches" />
          </div>
          {!shown.length && <p className="muted">No batches here yet.</p>}
          {shown.map((b) => (
            <div key={b.id} className={"panel stack batch " + b.stage}>
              <div className="row between"><span className="muted small">{b.title} · {b.label}</span><StatusBadge status={b.stage} /></div>
              <div className="row" style={{ gap: "2rem" }}>
                <span><strong className="num">{b.student_count}</strong> <span className="muted small">answers</span></span>
                <span><strong className="num">{b.max_total}</strong> <span className="muted small">marks</span></span>
                {b.stage === "review" && <span><strong className="num">{b.flagged}</strong> <span className="muted small">flagged for attention</span></span>}
              </div>
              <div className="row">
                {b.stage === "ready" && <button className="btn primary" onClick={() => onGrade({ assessment_id: b.assessment_id, batch_id: b.id })}>Start grading</button>}
                {b.stage === "review" && <button className="btn primary" onClick={() => onReview(b.latest_run_id)}>Review scores</button>}
                {b.stage === "review" && <button className="btn" onClick={() => onGrade({ assessment_id: b.assessment_id, batch_id: b.id })}>Grade again</button>}
                {b.stage === "confirmed" && <button className="btn" onClick={() => onResults(b.id)}>View saved results</button>}
              </div>
            </div>
          ))}
        </div>
        <aside className="stack">
          <div className="panel stack">
            <h3>Recent AI runs</h3>
            {!d.recent_runs.length && <p className="muted small">No runs yet.</p>}
            {d.recent_runs.slice(0, 6).map((r) => (
              <div key={r.id} className="feed"><div className="row between"><strong className="small">{r.label}</strong><StatusBadge status={r.status} /></div><span className="muted small">{when(r.started_at)}</span></div>
            ))}
            <button className="link small" onClick={() => onGo("runs")}>Open run details</button>
          </div>
        </aside>
      </div>
    </div>
  );
}