// New sign-ups waiting for a yes or no. Lecturers see students; a super admin sees everyone.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import { initials, when } from "../util.js";

export default function ApprovalsPage({ role, onChange }) {
  const [list, setList] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api.approvals().then((l) => { setList(l); onChange(l.length); }).catch(setErr);
  useEffect(() => { load(); }, []);
  const act = (fn, id) => { setErr(null); fn(id).then(load).catch(setErr); };

  return (
    <div className="stack">
      <div className="pagehead"><div><h1>Approvals</h1>
        <p className="muted">{role === "superadmin" ? "Lecturers and students" : "Students"} who asked for an account. Approve only people you recognise.</p></div></div>
      <ErrorBanner error={err} />
      {list && !list.length && <div className="empty">No requests are waiting.</div>}
      {(list || []).map((u) => (
        <div key={u.id} className="panel between row">
          <div className="row nowrap"><span className="avatar">{initials(u.name)}</span>
            <div><strong>{u.name}</strong> <span className="muted small">· {u.role} · {u.student_id || u.staff_id}</span><br />
              <span className="muted small">{u.email} · {when(u.created_at)}</span></div></div>
          <div className="row"><button className="btn primary" onClick={() => act(api.approve, u.id)}>Approve</button><button className="btn danger" onClick={() => act(api.reject, u.id)}>Decline</button></div>
        </div>
      ))}
    </div>
  );
}