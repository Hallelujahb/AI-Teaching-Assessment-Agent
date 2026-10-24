// Saved results ledger: AI proposed next to what the lecturer confirmed.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { initials, when } from "../util.js";

export default function ResultsPage({ initial }) {
  const [list, setList] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState(null);
  const show = (id) => api.batchResults(id).then(setOpen).catch(setErr);
  useEffect(() => { api.results().then(setList).catch(setErr); if (initial) show(initial); }, []);

  let stats = null;
  if (open) {
    const n = open.results.length;
    const mean = open.results.reduce((s, r) => s + r.total, 0) / n;
    const per = open.rubric.map((c, i) => open.results.filter((r) => r.ai_proposal.criteria[i]?.proposed_score === r.scores[i].score).length);
    const kept = per.reduce((a, b) => a + b, 0);
    stats = { n, mean: mean.toFixed(1), agreement: Math.round((100 * kept) / (n * open.rubric.length)), per };
  }

  const exportCsv = () => {
    const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const head = ["student_id", ...open.rubric.map((c) => c.name), "total", "max_total", "percentage", "feedback"];
    const rows = open.results.map((r) => [r.student_id, ...r.scores.map((s) => s.score), r.total, open.max_total, r.percentage, r.feedback]);
    const blob = new Blob([[head, ...rows].map((r) => r.map(q).join(",")).join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${open.batch_label}.csv`; a.click();
  };

  return (
    <div className="stack">
      <h1>Saved results</h1>
      <ErrorBanner error={err} />
      {list && !list.length && <p className="muted">Nothing confirmed yet. Grade a batch and confirm it to see it here.</p>}
      <div className="row">{(list || []).map((b) => <button key={b.batch_id} className={"tab pillbtn" + (open?.batch_id === b.batch_id ? " on" : "")} onClick={() => show(b.batch_id)}>{b.assessment_title}: {b.label}</button>)}</div>
      {open && (
        <>
          <div className="row between">
            <div><h2 style={{ margin: 0 }}>{open.batch_label}</h2><span className="muted small">Confirmed {when(open.approved_at)}</span></div>
            <div className="row noprint"><button className="btn" onClick={exportCsv}>Export CSV</button><button className="btn" onClick={() => window.print()}>Print summary</button></div>
          </div>
          <div className="stats">
            <div className="panel stat"><span className="muted small">Students confirmed</span><div className="big num">{stats.n}</div></div>
            <div className="panel stat"><span className="muted small">Mean score</span><div className="big num">{stats.mean}<span className="muted small"> / {open.max_total}</span></div></div>
            <div className="panel stat"><span className="muted small">Scores kept as proposed</span><div className="big num">{stats.agreement}%</div></div>
          </div>
          <div className="panel" style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Student</th><th>AI proposed</th><th>Confirmed</th><th>What changed</th></tr></thead>
              <tbody>{open.results.map((r) => {
                const diff = open.rubric.map((c, i) => ({ c, ai: r.ai_proposal.criteria[i]?.proposed_score, now: r.scores[i].score })).filter((x) => x.ai !== x.now);
                const aiTotal = r.ai_proposal.proposed_total;
                const delta = aiTotal == null ? null : r.total - aiTotal;
                return (
                  <tr key={r.student_id}>
                    <td><span className="row" style={{ gap: ".6rem" }}><span className="avatar">{initials(r.student_id)}</span>{r.student_id}</span></td>
                    <td className="num">{aiTotal ?? "-"} / {open.max_total}</td>
                    <td className="num"><strong>{r.total} / {open.max_total}</strong>{delta ? <span className={delta > 0 ? " okt" : " badt"}> {delta > 0 ? "+" : ""}{delta}</span> : null}</td>
                    <td className="small">{diff.length ? diff.map((x) => <div key={x.c.id}>{x.c.name}: {x.ai ?? "none"} to {x.now}</div>) : <span className="muted">Kept as proposed</span>}</td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
          <div className="panel stack">
            <h3>Agreement by criterion</h3>
            {open.rubric.map((c, i) => {
              const p = Math.round((100 * stats.per[i]) / stats.n);
              return <div key={c.id}><div className="row between small"><span>{c.name}</span><span className="num">{p}%</span></div><div className="bar"><i style={{ width: p + "%" }} /></div></div>;
            })}
          </div>
        </>
      )}
    </div>
  );
}