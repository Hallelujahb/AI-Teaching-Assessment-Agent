// Answers for one batch. Pick each student from the registered list, or type another id. At most 10 answers.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "./ErrorBanner.jsx";

const OTHER = "__other";
const empty = () => ({ student_id: "", custom: false, answer: "" });

export default function AddBatchForm({ assessmentId, onAdded }) {
  const [label, setLabel] = useState("");
  const [rows, setRows] = useState([empty()]);
  const [students, setStudents] = useState([]);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.students().then(setStudents).catch(() => {}); }, []);
  const set = (i, patch) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const pick = (i, v) => (v === OTHER ? set(i, { custom: true, student_id: "" }) : set(i, { custom: false, student_id: v }));
  const taken = (i) => new Set(rows.filter((_, j) => j !== i).map((r) => r.student_id).filter(Boolean));

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.addBatch(assessmentId, { label, submissions: rows.map((r) => ({ student_id: r.student_id, answer: r.answer })) });
      setLabel(""); setRows([empty()]);
      onAdded();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel stack">
      <h3>Add a batch of answers</h3>
      <div><label htmlFor="bl">Batch name</label><input id="bl" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="For example: Week 4 quiz" /></div>
      {rows.map((r, i) => (
        <div key={i} className="slot">
          <div className="row between nowrap">
            <div className="grow">
              <label>Student</label>
              {r.custom ? <input value={r.student_id} onChange={(e) => set(i, { student_id: e.target.value })} placeholder="Type an id" autoFocus />
                : (
                  <select value={r.student_id} onChange={(e) => pick(i, e.target.value)}>
                    <option value="">Choose a student</option>
                    {students.map((s) => <option key={s.student_id} value={s.student_id} disabled={taken(i).has(s.student_id)}>{s.student_id} · {s.name}</option>)}
                    <option value={OTHER}>Another id...</option>
                  </select>
                )}
            </div>
            {rows.length > 1 && <button className="btn danger" onClick={() => setRows(rows.filter((_, j) => j !== i))}>Remove</button>}
          </div>
          <label>Answer <span className="num">({r.answer.length}/2000)</span></label>
          <textarea maxLength={2000} value={r.answer} onChange={(e) => set(i, { answer: e.target.value })} />
          {!r.answer.trim() && r.student_id && <p className="small warnt" style={{ margin: 0 }}>A blank answer scores 0 and is not sent to the AI.</p>}
        </div>
      ))}
      <ErrorBanner error={err} />
      <div className="row">
        <button className="btn" disabled={rows.length >= 10} onClick={() => setRows([...rows, empty()])}>Add another answer</button>
        <button className="btn primary" disabled={busy} onClick={submit}>{busy ? "Saving..." : "Save batch"}</button>
      </div>
    </div>
  );
}