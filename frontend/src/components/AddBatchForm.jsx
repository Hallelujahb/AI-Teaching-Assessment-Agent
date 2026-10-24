// Answers for one batch. Add students by name or by ID, then type each student's answer. At most 10 answers.
import { useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "./ErrorBanner.jsx";
import StudentPicker from "./StudentPicker.jsx";

const MAX = 10;

export default function AddBatchForm({ assessmentId, onAdded }) {
  const [label, setLabel] = useState("");
  const [people, setPeople] = useState([]);          // [{student_id, name}]
  const [answers, setAnswers] = useState({});        // student_id -> answer text
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const search = (q) => api.students(q);
  const setAnswer = (id, v) => setAnswers({ ...answers, [id]: v });

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.addBatch(assessmentId, { label, submissions: people.map((p) => ({ student_id: p.student_id, answer: answers[p.student_id] || "" })) });
      setLabel(""); setPeople([]); setAnswers({});
      onAdded();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel stack">
      <h3>Add a batch of answers</h3>
      <div><label htmlFor="bl">Batch name</label><input id="bl" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="For example: Week 4 quiz" /></div>
      <div>
        <label>Students (search by name or ID)</label>
        <StudentPicker selected={people} onChange={setPeople} search={search} max={MAX} allowCustom />
      </div>
      {people.map((p) => {
        const a = answers[p.student_id] || "";
        return (
          <div key={p.student_id} className="slot">
            <label>{p.student_id}{p.name ? ` · ${p.name}` : ""} <span className="num">({a.length}/2000)</span></label>
            <textarea maxLength={2000} value={a} onChange={(e) => setAnswer(p.student_id, e.target.value)} placeholder="Paste or type this student's answer" />
            {!a.trim() && <p className="small warnt" style={{ margin: 0 }}>A blank answer scores 0 and is not sent to the AI.</p>}
          </div>
        );
      })}
      <ErrorBanner error={err} />
      <div><button className="btn primary" disabled={busy || !people.length} onClick={submit}>{busy ? "Saving..." : "Save batch"}</button></div>
    </div>
  );
}