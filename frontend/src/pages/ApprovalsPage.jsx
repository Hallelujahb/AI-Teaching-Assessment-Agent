// New sign-ups waiting for a yes or no, and password reset requests. Lecturers see students; a super admin sees everyone.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { initials, when } from "../util.js";

export default function ApprovalsPage({ role, onChange }) {
  const [list, setList] = useState(null);
  const [resets, setResets] = useState(null);
  const [codes, setCodes] = useState({});
  const [err, setErr] = useState(null);
  const load = () => Promise.all([api.approvals(), api.resets()])
    .then(([a, r]) => { setList(a); setResets(r); onChange(a.length + r.length); }).catch(setErr);
  useEffect(() => { load(); }, []);
  const act = (fn, id) => { setErr(null); fn(id).then(load).catch(setErr); };
  const issue = (id) => { setErr(null); api.issueReset(id).then((r) => { setCodes({ ...codes, [id]: r }); return load(); }).catch(setErr); };
  const dismiss = (id) => { setErr(null); api.dismissReset(id).then(() => { const { [id]: _gone, ...rest } = codes; setCodes(rest); return load(); }).catch(setErr); };

  return (
    <div className="stack">
      <div className="pagehead"><div><h1>Approvals</h1>
        <p className="muted">{role === "superadmin" ? "Lecturers and students" : "Students"} who asked for an account or a new password. Approve only people you recognise.</p></div></div>
      <ErrorBanner error={err} />
      <h2>Account requests</h2>
      {list && !list.length && <div className="empty">No requests are waiting.</div>}
      {(list || []).map((u) => (
        <div key={u.id} className="panel between row">
          <div className="row nowrap"><span className="avatar">{initials(u.name)}</span>
            <div><strong>{u.name}</strong> <span className="muted small">· {u.role} · {u.student_id || u.staff_id}</span><br />
              <span className="muted small">{u.email} · {when(u.created_at)}</span></div></div>
          <div className="row"><button className="btn primary" onClick={() => act(api.approve, u.id)}>Approve</button><button className="btn danger" onClick={() => act(api.reject, u.id)}>Decline</button></div>
        </div>
      ))}
      <h2>Password resets</h2>
      {resets && !resets.length && <div className="empty">Nobody has asked for a password reset.</div>}
      {(resets || []).map((u) => (
        <div key={u.id} className="panel stack">
          <div className="between row">
            <div className="row nowrap"><span className="avatar">{initials(u.name)}</span>
              <div><strong>{u.name}</strong> <span className="muted small">· {u.role} · {u.student_id || u.staff_id}</span><br />
                <span className="muted small">{u.email} · asked {when(u.requested_at)}</span></div></div>
            <div className="row">
              <button className="btn primary" onClick={() => issue(u.id)}>{u.issued || codes[u.id] ? "Make a new code" : "Make a code"}</button>
              <button className="btn danger" onClick={() => dismiss(u.id)}>Dismiss</button>
            </div>
          </div>
          {codes[u.id] && (
            <div className="answer">
              <p style={{ margin: 0 }}>Code for {codes[u.id].name}: <strong className="big num">{codes[u.id].code}</strong></p>
              <p className="muted small" style={{ margin: ".4rem 0 0" }}>Give it to them yourself, and only if you know it is really them. It works once and expires in {codes[u.id].minutes} minutes. This is the only time it is shown.</p>
            </div>
          )}
          {!codes[u.id] && u.issued && <p className="muted small" style={{ margin: 0 }}>A code was issued and has not been used yet. Make a new one if it was lost.</p>}
        </div>
      ))}
    </div>
  );
}
