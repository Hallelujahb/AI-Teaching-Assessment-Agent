// AI runs and diagnostics: every run, and exactly what the agent did in it.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StatusBadge from "../components/StatusBadge.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { when } from "../util.js";

const RULES = [
  "Scores are whole numbers within each criterion maximum. They are rejected, never rounded.",
  "Every quote is checked against the student's answer.",
  "Blank and too-short answers never reach the model.",
  "One retry for invalid students, then manual grading.",
  "At most 4 tool calls and 60 seconds per run.",
];

export default function RunsPage({ onReview }) {
  const [runs, setRuns] = useState(null);
  const [run, setRun] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.dashboard().then((d) => setRuns(d.recent_runs)).catch(setErr); }, []);

  return (
    <div className="stack">
      <h1>AI runs and diagnostics</h1>
      <ErrorBanner error={err} />
      <div className="split">
        <div className="list">
          {runs && !runs.length && <p className="muted" style={{ padding: ".8rem" }}>No runs yet.</p>}
          {(runs || []).map((r) => (
            <button key={r.id} className={"item" + (run?.run_id === r.id ? " on" : "")} onClick={() => api.run(r.id).then(setRun).catch(setErr)}>
              <span><strong className="small">{r.label}</strong><br /><span className="muted small">{when(r.started_at)}</span></span><StatusBadge status={r.status} />
            </button>
          ))}
        </div>
        <div className="stack">
          {run ? (
            <div className="panel stack">
              <div className="row between"><h2 style={{ margin: 0 }}>{run.batch_label}</h2><StatusBadge status={run.status} /></div>
              <p className="muted small">Model: {run.model || "not recorded"} · {run.proposals.length} proposals · started {when(run.started_at)}</p>
              {run.error && <div className="banner">{run.error}</div>}
              <div className="term" role="log">
                {run.tool_log.length ? run.tool_log.map((l, i) => (
                  <div key={i}><span className="t-name">{l.tool_name}</span> {JSON.stringify(l.arguments)} <span className="t-out">{l.outcome}</span> <span className="t-ms">{l.duration_ms} ms</span></div>
                )) : <div>No steps were recorded.</div>}
              </div>
              {run.status === "succeeded" && run.is_latest && <div><button className="btn primary" onClick={() => onReview(run.run_id)}>Open review</button></div>}
            </div>
          ) : <p className="muted">Choose a run to see its steps.</p>}
          <div className="panel stack ai">
            <h3>Rules enforced by code</h3>
            <ul className="rules">{RULES.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        </div>
      </div>
    </div>
  );
}