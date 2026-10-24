// Lecturer: group students into classes so an exam can be assigned to the whole class at once.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import StudentPicker from "../components/StudentPicker.jsx";

const MAX = 10;

function ClassForm({ initial, onSaved, onCancel }) {
  const [name, setName] = useState(initial ? initial.name : "");
  const [people, setPeople] = useState(initial ? initial.students.map((s) => ({ student_id: s.student_id, name: s.name })) : []);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true); setErr(null);
    try {
      const data = { name, student_ids: people.map((s) => s.student_id) };
      if (initial) await api.updateClass(initial.id, data); else await api.createClass(data);
      onSaved();
    } catch (e) { setErr(e); } finally { setBusy(false); }
  };

  return (
    <div className="panel stack">
      <h2>{initial ? "Edit class" : "New class"}</h2>
      <div><label htmlFor="cn">Class name</label><input id="cn" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="For example: Year 2 Section 3" /></div>
      <div>
        <label>Students (search by name or ID)</label>
        <StudentPicker selected={people} onChange={setPeople} search={(q) => api.students(q)} max={MAX} />
        <p className="muted small">A class holds at most {MAX} students, because one exam is graded as one batch.</p>
      </div>
      <ErrorBanner error={err} />
      <div className="row"><button className="btn primary" disabled={busy} onClick={save}>{busy ? "Saving..." : "Save class"}</button><button className="btn" onClick={onCancel}>Cancel</button></div>
    </div>
  );
}

export default function ClassesPage() {
  const [list, setList] = useState(null);
  const [form, setForm] = useState(null);
  const [del, setDel] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api.classes().then(setList).catch(setErr);
  useEffect(() => { load(); }, []);
  const saved = () => { setForm(null); load(); };
  const remove = () => api.deleteClass(del.id).then(() => { setDel(null); load(); }).catch((e) => { setErr(e); setDel(null); });

  if (form) return <div className="stack"><div className="pagehead"><h1>Classes</h1></div><ClassForm initial={form.initial} onSaved={saved} onCancel={() => setForm(null)} /></div>;
  return (
    <div className="stack">
      <div className="pagehead"><div><h1>Classes</h1><p className="muted">Group students so you can assign an exam to all of them at once.</p></div>
        <button className="btn primary" onClick={() => setForm({})}>New class</button></div>
      <ErrorBanner error={err} />
      {list && !list.length && <div className="empty">No classes yet. Create one, or assign exams to individual students.</div>}
      {(list || []).map((c) => (
        <div key={c.id} className="panel row between">
          <div><strong>{c.name}</strong><div className="muted small">{c.students.length} students: {c.students.map((s) => s.student_id).join(", ")}</div></div>
          <div className="row"><button className="btn" onClick={() => setForm({ initial: c })}>Edit</button><button className="btn danger" onClick={() => setDel(c)}>Delete</button></div>
        </div>
      ))}
      <ConfirmDialog open={!!del} title="Delete this class?" body="Exams already assigned to it keep their students. Only the group is removed." yes="Delete" onYes={remove} onNo={() => setDel(null)} />
    </div>
  );
}
