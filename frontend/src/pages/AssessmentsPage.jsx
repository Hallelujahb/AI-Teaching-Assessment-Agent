// Lecturer: create an assessment (question, reference answer, rubric), then add the students' answers.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import AssessmentForm from "../components/AssessmentForm.jsx";
import AddBatchForm from "../components/AddBatchForm.jsx";
import AssignForm from "../components/AssignForm.jsx";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function AssessmentsPage({ onGrade }) {
  const [list, setList] = useState(null);
  const [view, setView] = useState({ mode: "list" });
  const [a, setA] = useState(null);
  const [batches, setBatches] = useState([]);
  const [adding, setAdding] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assigned, setAssigned] = useState([]);
  const [drop, setDrop] = useState(null);
  const [del, setDel] = useState(false);
  const [err, setErr] = useState(null);

  const load = () => api.assessments().then(setList).catch(setErr);
  const loadBatches = (id) => { api.batches(id).then(setBatches).catch(setErr); api.assignments(id).then(setAssigned).catch(setErr); };
  useEffect(() => { load(); }, []);
  const open = (id) => { setView({ mode: "open", id }); setA(null); setAdding(false); setAssigning(false); setErr(null); api.assessment(id).then(setA).catch(setErr); loadBatches(id); };
  const back = () => { setView({ mode: "list" }); load(); };
  const remove = () => api.deleteAssessment(a.id).then(() => { setDel(false); back(); }).catch((e) => { setErr(e); setDel(false); });

  if (view.mode === "new") return (
    <div className="stack"><div className="pagehead"><h1>New assessment</h1></div>
      <AssessmentForm onSaved={open} onCancel={back} /></div>
  );
  if (view.mode === "edit") return (
    <div className="stack"><div className="pagehead"><h1>Edit assessment</h1></div>
      <AssessmentForm initial={a} onSaved={open} onCancel={() => open(a.id)} /></div>
  );

  if (view.mode === "open") return (
    <div className="stack">
      <button className="link small" onClick={back}>All assessments</button>
      <ErrorBanner error={err} />
      {!a ? <p className="muted">Loading...</p> : (
        <>
          <div className="pagehead"><div><h1>{a.title}</h1><p className="muted">{a.max_total} marks · {a.rubric.length} criteria</p></div>
            <div className="row">
              {!a.locked && <button className="btn" onClick={() => setView({ mode: "edit" })}>Edit</button>}
              {!a.locked && <button className="btn danger" onClick={() => setDel(true)}>Delete</button>}
            </div></div>
          {a.locked && <p className="muted small">This assessment has been graded or assigned, so the question and rubric are locked. Remove its assignments (before marking starts) to edit it.</p>}
          <div className="panel stack"><div><h3>Question</h3><p>{a.question}</p></div><div><h3>Reference answer</h3><p className="muted">{a.reference_answer}</p></div></div>
          <div className="panel scroll"><table style={{ minWidth: 520 }}>
            <thead><tr><th>Criterion</th><th>What earns marks</th><th>Marks</th></tr></thead>
            <tbody>{a.rubric.map((c) => <tr key={c.id}><td><strong>{c.name}</strong></td><td className="small" style={{ whiteSpace: "pre-wrap" }}>{c.description}</td><td className="num">{c.max_score}</td></tr>)}</tbody>
          </table></div>
          <div className="pagehead"><h2>Assigned to students</h2><button className="btn primary" onClick={() => setAssigning(!assigning)}>{assigning ? "Close" : "Assign"}</button></div>
          {assigning && <AssignForm assessmentId={a.id} onAssigned={() => { loadBatches(a.id); api.assessment(a.id).then(setA); setAssigning(false); }} />}
          {!assigned.length && !assigning && <div className="empty">Not assigned yet. Students see an exam here once you assign it.</div>}
          {assigned.map((x) => (
            <div key={x.id} className="panel row between">
              <div><strong>{x.class_name || x.label}</strong>
                <div className="muted small">{x.submitted_count} of {x.assigned_count} handed in{x.time_limit_minutes ? ` · ${x.time_limit_minutes} minute limit` : ""}{x.closed ? " · marking started" : ""}</div></div>
              <div className="row">
                <button className="btn" disabled={!x.submitted_count} onClick={() => onGrade({ assessment_id: a.id, batch_id: x.batch_id })}>Grade this batch</button>
                {!x.closed && <button className="btn danger" onClick={() => setDrop(x)}>Remove</button>}
              </div>
            </div>
          ))}
          <div className="pagehead"><h2>Batches of answers</h2><button className="btn primary" onClick={() => setAdding(!adding)}>{adding ? "Close" : "Add answers"}</button></div>
          {adding && <AddBatchForm assessmentId={a.id} onAdded={() => { loadBatches(a.id); setAdding(false); }} />}
          {!batches.length && !adding && <div className="empty">No answers yet. Add a batch to start grading.</div>}
          {batches.filter((b) => !assigned.some((x) => x.batch_id === b.id)).map((b) => (
            <div key={b.id} className="panel row between">
              <div><strong>{b.label}</strong><div className="muted small">{b.student_count} answers{b.confirmed ? " · confirmed" : ""}</div></div>
              {!b.confirmed && <button className="btn" disabled={!b.student_count} onClick={() => onGrade({ assessment_id: a.id, batch_id: b.id })}>Grade this batch</button>}
            </div>
          ))}
          <ConfirmDialog open={!!drop} title="Remove this assignment?" body="Students lose access to this exam and any answers already handed in are deleted." yes="Remove"
            onYes={() => api.deleteAssignment(drop.id).then(() => { setDrop(null); loadBatches(a.id); api.assessment(a.id).then(setA); }).catch((e) => { setErr(e); setDrop(null); })} onNo={() => setDrop(null)} />
          <ConfirmDialog open={del} title="Delete this assessment?" body="Its rubric and any ungraded batches of answers will be removed." yes="Delete" onYes={remove} onNo={() => setDel(false)} />
        </>
      )}
    </div>
  );

  return (
    <div className="stack">
      <div className="pagehead"><div><h1>Assessments</h1><p className="muted">A question, its reference answer and a rubric. Add the students' answers, then grade.</p></div>
        <button className="btn primary" onClick={() => setView({ mode: "new" })}>New assessment</button></div>
      <ErrorBanner error={err} />
      {list && !list.length && <div className="empty">No assessments yet. Create your first one.</div>}
      <div className="cards">
        {(list || []).map((x) => (
          <button key={x.id} className="panel card" onClick={() => open(x.id)}>
            <strong>{x.title}</strong>
            <span className="muted small clamp">{x.question}</span>
            <span className="small">{x.max_total} marks · {x.criteria_count} criteria · {x.batch_count} batches{x.locked ? " · graded" : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
