// Per student review: answer, AI scores, evidence, editable scores and feedback, confirm.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import StudentList from "../components/StudentList.jsx";
import CriterionCard from "../components/CriterionCard.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import ToolLog from "../components/ToolLog.jsx";

const whole = (v, max) => v !== "" && v !== null && /^\d+$/.test(String(v)) && +v <= max;

export default function ReviewPage({ runId, onConfirmed, onBack }) {
  const [run, setRun] = useState(null);
  const [edit, setEdit] = useState({});
  const [sel, setSel] = useState(0);
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api.run(runId).then((r) => {
      const e = {};
      r.proposals.forEach((p) => { e[p.student_id] = { scores: Object.fromEntries(p.criteria.map((c) => [c.criterion_id, c.proposed_score ?? ""])), feedback: p.feedback || "" }; });
      setRun(r); setEdit(e);
    }).catch(setErr);
  }, [runId]);

  if (!run) return err ? <ErrorBanner error={err} /> : <p className="muted">Loading the proposals...</p>;
  const maxOf = Object.fromEntries(run.rubric.map((c) => [c.id, c.max_score]));
  const okStudent = (p) => p.criteria.every((c) => whole(edit[p.student_id].scores[c.criterion_id], c.max_score));
  const done = Object.fromEntries(run.proposals.map((p) => [p.student_id, okStudent(p)]));
  const allOk = run.proposals.every(okStudent);
  const p = run.proposals[sel];
  const e = edit[p.student_id];
  const total = (x) => p.criteria.reduce((s, c) => s + (+x.scores[c.criterion_id] || 0), 0);
  const setScore = (cid, v) => setEdit({ ...edit, [p.student_id]: { ...e, scores: { ...e.scores, [cid]: v } } });

  const confirm = async () => {
    setBusy(true); setErr(null);
    try {
      await api.review(run.batch_id, {
        run_id: run.run_id,
        results: run.proposals.map((q) => ({
          student_id: q.student_id, feedback: edit[q.student_id].feedback,
          scores: q.criteria.map((c) => ({ criterion_id: c.criterion_id, score: +edit[q.student_id].scores[c.criterion_id] })),
        })),
      });
      onConfirmed();
    } catch (x) { setErr(x); setAsk(false); } finally { setBusy(false); }
  };

  return (
    <div className="stack">
      <div className="row"><h1 style={{ flex: 1, margin: 0 }}>Review: {run.batch_label}</h1>
        <button className="btn" onClick={onBack}>Leave without saving</button>
        <button className="btn primary" disabled={!allOk} onClick={() => setAsk(true)}>Confirm all scores</button></div>
      {!allOk && <p className="muted small">Confirm unlocks when every student has a whole-number score in range for every criterion.</p>}
      <ErrorBanner error={err} />
      <div className="split">
        <StudentList proposals={run.proposals} selected={sel} onSelect={setSel} done={done} />
        <div className="panel stack">
          <div className="row"><h2 style={{ margin: 0, flex: 1 }}>{p.student_id}</h2><StatusBadge status={p.answer_status} />
            <span className="num">Total {total(e)} / {run.max_total}</span></div>
          <div className="answer">{p.answer || "(blank)"}</div>
          {p.attention_flags.map((f, i) => <div key={i} className="flag">{f}</div>)}
          <div>{p.criteria.map((c) => <CriterionCard key={c.criterion_id} c={c} value={e.scores[c.criterion_id]} onChange={(v) => setScore(c.criterion_id, v)} />)}</div>
          <div><label htmlFor="fb">Feedback for the student</label>
            <textarea id="fb" value={e.feedback} onChange={(x) => setEdit({ ...edit, [p.student_id]: { ...e, feedback: x.target.value } })} /></div>
        </div>
      </div>
      <ToolLog log={run.tool_log} />
      <ConfirmDialog open={ask} busy={busy} title="Confirm these scores?" yes="Confirm and save" onYes={confirm} onNo={() => setAsk(false)}
        body="Scores are saved for every student and the batch becomes read-only. Students will see their result." />
    </div>
  );
}