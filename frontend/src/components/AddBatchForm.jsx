// Rows of student id and answer. At most 10 rows, 2000 characters each.
import { useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "./ErrorBanner.jsx";

export default function AddBatchForm({ assessmentId, onAdded }) {
  const [label, setLabel] = useState("");
  const [rows, setRows] = useState([{ student_id: "", answer: "" }]);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (i, k, v) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.addBatch(assessmentId, { label, submissions: rows });
      setLabel(""); setRows([{ student_id: "", answer: "" }]);
      onAdded();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel stack">
      <h3>Add a batch of answers</h3>
      <div><label htmlFor="bl">Batch name</label><input id="bl" value={label} onChange={(e) => setLabel(e.target.value)} /></div>
      {rows.map((r, i) => (
        <div key={i} className="row" style={{ alignItems: "flex-start" }}>
          <div style={{ width: 130 }}><label>Student id</label><input value={r.student_id} onChange={(e) => set(i, "student_id", e.target.value)} /></div>
          <div style={{ flex: 1, minWidth: 220 }}><label>Answer ({r.answer.length}/2000)</label><textarea maxLength={2000} value={r.answer} onChange={(e) => set(i, "answer", e.target.value)} /></div>
        </div>
      ))}
      <ErrorBanner error={err} />
      <div className="row">
        <button className="btn" disabled={rows.length >= 10} onClick={() => setRows([...rows, { student_id: "", answer: "" }])}>Add another answer</button>
        <button className="btn primary" disabled={busy} onClick={submit}>Save batch</button>
      </div>
    </div>
  );
}