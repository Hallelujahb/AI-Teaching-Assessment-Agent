// Give an assessment to a class or to chosen students, with an optional time limit in whole minutes.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "./ErrorBanner.jsx";
import StudentPicker from "./StudentPicker.jsx";

const MAX = 10;

export default function AssignForm({ assessmentId, onAssigned }) {
  const [classes, setClasses] = useState([]);
  const [by, setBy] = useState("class");
  const [classId, setClassId] = useState("");
  const [people, setPeople] = useState([]);
  const [limit, setLimit] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.classes().then((l) => { setClasses(l); if (!l.length) setBy("students"); }).catch(setErr);
  }, []);

  const submit = async () => {
    setErr(null);
    if (limit !== "" && !/^\d+$/.test(limit.trim())) { setErr(new Error("The time limit must be a whole number of minutes.")); return; }
    setBusy(true);
    try {
      const data = { time_limit_minutes: limit === "" ? null : parseInt(limit, 10) };
      if (by === "class") data.class_id = classId ? parseInt(classId, 10) : null; else data.student_ids = people.map((s) => s.student_id);
      await api.assign(assessmentId, data);
      onAssigned();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel stack">
      <h3>Assign to students</h3>
      <div className="seg" role="group" aria-label="Assign to">
        <button type="button" aria-pressed={by === "class"} onClick={() => setBy("class")}>A class</button>
        <button type="button" aria-pressed={by === "students"} onClick={() => setBy("students")}>Chosen students</button>
      </div>
      {by === "class" ? (
        <div>
          <label htmlFor="ac">Class</label>
          <select id="ac" value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">Choose a class</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.students.length} students)</option>)}
          </select>
          {!classes.length && <p className="muted small">You have no classes yet. Make one under Classes, or pick students directly.</p>}
        </div>
      ) : (
        <div>
          <label>Students (search by name or ID)</label>
          <StudentPicker selected={people} onChange={setPeople} search={(q) => api.students(q)} max={MAX} />
        </div>
      )}
      <div>
        <label htmlFor="tl">Time limit in minutes (optional)</label>
        <input id="tl" type="number" min="1" max="300" step="1" inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="No limit" />
        <p className="muted small">With a limit, the question stays hidden until the student presses Start. Up to {MAX} students per assignment. The students are fixed when you assign.</p>
      </div>
      <ErrorBanner error={err} />
      <div><button className="btn primary" disabled={busy || (by === "class" ? !classId : !people.length)} onClick={submit}>{busy ? "Assigning..." : "Assign"}</button></div>
    </div>
  );
}
