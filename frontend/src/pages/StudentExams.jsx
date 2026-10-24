// A student's assigned exams: open one, start the clock if it is timed, write the answer, hand it in.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

const LABEL = { open: "Not started", in_progress: "In progress", submitted: "Handed in", expired: "Time is up", closed: "Closed" };

const clock = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

function Exam({ id, onBack }) {
  const [exam, setExam] = useState(null);
  const [answer, setAnswer] = useState("");
  const [left, setLeft] = useState(null);
  const [ask, setAsk] = useState(false);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.myExam(id).then(setExam).catch(setErr); }, [id]);
  useEffect(() => {
    if (!exam || !exam.deadline || exam.status !== "in_progress") { setLeft(null); return; }
    const tick = () => setLeft(new Date(exam.deadline) - Date.now());
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [exam]);

  const start = () => { setBusy(true); setErr(null); api.startExam(id).then(setExam).catch(setErr).finally(() => setBusy(false)); };
  const submit = async () => {
    setBusy(true); setErr(null);
    try { await api.submitExam(id, answer); setAsk(false); setExam(await api.myExam(id)); }
    catch (e) { setAsk(false); setErr(e); } finally { setBusy(false); }
  };

  if (!exam) return <div className="stack"><button className="link small" onClick={onBack}>All exams</button><ErrorBanner error={err} />{!err && <p className="muted">Loading...</p>}</div>;
  const writing = exam.question && (exam.status === "open" || exam.status === "in_progress");
  return (
    <div className="stack">
      <button className="link small" onClick={onBack}>All exams</button>
      <div className="pagehead"><div><h1>{exam.title}</h1><p className="muted">{LABEL[exam.status]}{exam.time_limit_minutes ? ` · ${exam.time_limit_minutes} minute limit` : ""}</p></div>
        {left !== null && <strong className="big num" aria-live="off">{clock(left)}</strong>}</div>
      <ErrorBanner error={err} />
      {exam.status === "open" && !exam.question && (
        <div className="panel stack">
          <p>This exam is timed. The question appears when you press Start, and you then have {exam.time_limit_minutes} minutes.</p>
          <div><button className="btn primary" disabled={busy} onClick={start}>Start the exam</button></div>
        </div>
      )}
      {exam.question && <div className="panel stack"><h3>Question</h3><p style={{ whiteSpace: "pre-wrap" }}>{exam.question}</p></div>}
      {writing && (
        <div className="panel stack">
          <label htmlFor="ans">Your answer <span className="num">({answer.length}/2000)</span></label>
          <textarea id="ans" maxLength={2000} value={answer} onChange={(e) => setAnswer(e.target.value)} />
          <div><button className="btn primary" disabled={busy || !answer.trim()} onClick={() => setAsk(true)}>Hand in</button></div>
        </div>
      )}
      {exam.status === "submitted" && <p className="muted">Your answer was handed in. Your result appears under My results once your lecturer confirms the marking.</p>}
      {exam.status === "expired" && <p className="muted">The time limit ended before an answer was handed in.</p>}
      {exam.status === "closed" && <p className="muted">This exam is closed because marking has started.</p>}
      <ConfirmDialog open={ask} title="Hand in this answer?" body="You cannot change it afterwards." yes="Hand in" onYes={submit} onNo={() => setAsk(false)} busy={busy} />
    </div>
  );
}

export default function StudentExams() {
  const [list, setList] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api.myExams().then(setList).catch(setErr);
  useEffect(() => { load(); }, []);
  if (openId) return <Exam id={openId} onBack={() => { setOpenId(null); load(); }} />;
  return (
    <div className="stack">
      <h1>My exams</h1>
      <ErrorBanner error={err} />
      {list && !list.length && <p className="muted">Nothing is assigned to you yet.</p>}
      {(list || []).map((x) => (
        <div key={x.id} className="panel row between">
          <div><strong>{x.title}</strong><div className="muted small">{LABEL[x.status]}{x.time_limit_minutes ? ` · ${x.time_limit_minutes} minute limit` : ""}</div></div>
          <button className="btn" onClick={() => setOpenId(x.id)}>{x.status === "open" || x.status === "in_progress" ? "Open" : "View"}</button>
        </div>
      ))}
    </div>
  );
}
