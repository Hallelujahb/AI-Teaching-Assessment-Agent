// A student sees only their own confirmed results.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function StudentDashboard() {
  const [list, setList] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api.myResults().then(setList).catch(setErr); }, []);

  return (
    <div className="stack">
      <h1>My results</h1>
      <ErrorBanner error={err} />
      {list && !list.length && <p className="muted">No results yet. They appear here once your lecturer confirms the marking.</p>}
      {(list || []).map((r, i) => (
        <div key={i} className="panel stack">
          <div className="row"><h2 style={{ flex: 1, margin: 0 }}>{r.assessment}</h2><span className="big num">{r.total}<span className="muted small"> / {r.max_total} ({r.percentage}%)</span></span></div>
          <table>
            <tbody>{r.criteria.map((c) => <tr key={c.name}><td>{c.name}</td><td className="num" style={{ textAlign: "right" }}>{c.score} / {c.max_score}</td></tr>)}</tbody>
          </table>
          {r.feedback && <div className="answer">{r.feedback}</div>}
        </div>
      ))}
    </div>
  );
}