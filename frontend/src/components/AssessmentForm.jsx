// Create or edit an assessment: question, reference answer and rubric.
import { useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "./ErrorBanner.jsx";

const blank = () => ({ name: "", description: "", max_score: 2 });
const GUIDE = "Covers: what a correct answer says.\nMarks: 2 = fully correct; 1 = partly correct; 0 = missing or wrong.\nNot credited here: points that belong to another criterion.";

export default function AssessmentForm({ initial, onSaved, onCancel }) {
  const [f, setF] = useState(() => initial
    ? { title: initial.title, question: initial.question, reference_answer: initial.reference_answer,
        rubric: initial.rubric.map((c) => ({ name: c.name, description: c.description, max_score: c.max_score })) }
    : { title: "", question: "", reference_answer: "", rubric: [blank()] });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const setC = (i, k, v) => setF({ ...f, rubric: f.rubric.map((c, j) => (j === i ? { ...c, [k]: v } : c)) });
  const total = f.rubric.reduce((s, c) => s + (parseInt(c.max_score, 10) || 0), 0);

  const save = async () => {
    setBusy(true); setErr(null);
    const data = { ...f, rubric: f.rubric.map((c) => ({ ...c, max_score: parseInt(c.max_score, 10) })) };
    try { const r = initial ? await api.updateAssessment(initial.id, data) : await api.createAssessment(data); onSaved(r.id); }
    catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="stack">
      <div className="panel stack">
        <h2>The question</h2>
        <div><label htmlFor="t">Title</label><input id="t" value={f.title} onChange={up("title")} placeholder="JS101: Variables in JavaScript" /></div>
        <div><label htmlFor="q">Question for the students</label><textarea id="q" value={f.question} onChange={up("question")} /></div>
        <div><label htmlFor="r">Reference answer</label><textarea id="r" value={f.reference_answer} onChange={up("reference_answer")} />
          <p className="muted small">The model answer the AI compares against. Students never see it.</p></div>
      </div>
      <div className="panel stack">
        <div className="row between"><h2 style={{ margin: 0 }}>Rubric</h2><strong className="num">{total} marks in total</strong></div>
        {f.rubric.map((c, i) => (
          <div key={i} className="slot">
            <div className="grid2">
              <div><label>Criterion {i + 1}</label><input value={c.name} onChange={(e) => setC(i, "name", e.target.value)} placeholder="Defines a variable" /></div>
              <div><label>Maximum marks</label><input type="number" min="1" max="20" value={c.max_score} onChange={(e) => setC(i, "max_score", e.target.value)} /></div>
            </div>
            <label>What earns marks</label>
            <textarea value={c.description} onChange={(e) => setC(i, "description", e.target.value)} placeholder={GUIDE} />
            {f.rubric.length > 1 && <div><button className="btn danger" onClick={() => setF({ ...f, rubric: f.rubric.filter((_, j) => j !== i) })}>Remove criterion</button></div>}
          </div>
        ))}
        <div><button className="btn" disabled={f.rubric.length >= 8} onClick={() => setF({ ...f, rubric: [...f.rubric, blank()] })}>Add a criterion</button></div>
        <p className="muted small">Clear marks per criterion and a line saying what is not credited give the most consistent grading.</p>
      </div>
      <ErrorBanner error={err} />
      <div className="row"><button className="btn primary" disabled={busy} onClick={save}>{busy ? "Saving..." : initial ? "Save changes" : "Create assessment"}</button><button className="btn" onClick={onCancel}>Cancel</button></div>
    </div>
  );
}