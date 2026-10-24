// Starts the grading run, then shows a clarification question or an error with retry.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function RunPage({ params, onDone, onBack }) {
  const [state, setState] = useState({ s: "running" });
  const [answer, setAnswer] = useState("");

  const go = (p) => {
    setState({ s: "running" });
    api.grade(p)
      .then((r) => (r.status === "graded" ? onDone(r.run_id) : setState({ s: "ask", q: r.clarification, p })))
      .catch((e) => setState({ s: "error", e, p }));
  };
  useEffect(() => { go(params); }, []);

  return (
    <div className="stack">
      <h1>Grading</h1>
      {state.s === "running" && <p><span className="dots"><span /><span /><span /></span> The agent is reading the rubric and the answers. This can take up to a minute.</p>}
      {state.s === "ask" && (
        <div className="panel stack">
          <p><strong>{state.q}</strong></p>
          <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Type your answer" />
          <div className="row">
            <button className="btn primary" disabled={!answer.trim()} onClick={() => go({ ...state.p, request: ((state.p.request || "") + " " + answer).trim() })}>Send answer</button>
            <button className="btn" onClick={onBack}>Back</button>
          </div>
        </div>
      )}
      {state.s === "error" && (
        <div className="stack">
          <ErrorBanner error={state.e} onRetry={() => go(state.p)} />
          <button className="btn" onClick={onBack}>Back</button>
        </div>
      )}
    </div>
  );
}