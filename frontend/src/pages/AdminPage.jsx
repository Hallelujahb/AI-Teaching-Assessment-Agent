// Super admin: every account, add one (the id is issued automatically), reset a password, remove one.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const blank = { name: "", email: "", role: "lecturer", password: "" };
const gen = () => Array.from(crypto.getRandomValues(new Uint8Array(10)), (b) => "abcdefghjkmnpqrstuvwxyz23456789"[b % 31]).join("") + "A1";

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [f, setF] = useState(blank);
  const [err, setErr] = useState(null);
  const [del, setDel] = useState(null);
  const [made, setMade] = useState(null);
  const load = () => api.adminUsers().then(setUsers).catch(setErr);
  useEffect(() => { load(); }, []);
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const add = async (e) => {
    e.preventDefault(); setErr(null);
    try { const r = await api.adminAddUser(f); setMade({ ...r, password: f.password }); setF(blank); load(); } catch (x) { setErr(x); }
  };
  const reset = (u) => { const p = window.prompt(`New password for ${u.email} (8+ characters)`); if (p) api.adminResetPassword(u.id, p).then(() => setErr(null)).catch(setErr); };
  const remove = async () => { try { await api.adminDeleteUser(del.id); setDel(null); load(); } catch (x) { setErr(x); setDel(null); } };

  return (
    <div className="stack">
      <div className="pagehead"><div><h1>Users</h1><p className="muted">Ids are issued by the system: ST001 for students, LT001 for lecturers.</p></div></div>
      <ErrorBanner error={err} />
      {made && <div className="panel ai"><strong>{made.name} was added.</strong><p style={{ margin: ".3rem 0 0" }}>Issued id: <strong className="num">{made.issued_id}</strong>. Share the email and password with them: <span className="num">{made.email}</span> / <span className="num">{made.password}</span></p></div>}
      <form className="panel stack" onSubmit={add}>
        <h2>Add an account</h2>
        <div className="grid2">
          <div><label>Name</label><input value={f.name} onChange={up("name")} required /></div>
          <div><label>Email</label><input type="email" value={f.email} onChange={up("email")} required /></div>
          <div><label>Role</label><select value={f.role} onChange={up("role")}><option value="lecturer">Lecturer</option><option value="student">Student</option></select></div>
          <div><label>Password (8+)</label><div className="row nowrap"><input value={f.password} onChange={up("password")} required minLength={8} /><button type="button" className="btn" onClick={() => setF({ ...f, password: gen() })}>Generate</button></div></div>
        </div>
        <div><button className="btn primary">Create account</button></div>
      </form>
      <div className="panel scroll">
        <table style={{ minWidth: 640 }}>
          <thead><tr><th>Id</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th /></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td className="num">{u.student_id || u.staff_id || "-"}</td><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td>
              <td><StatusBadge status={u.status === "active" ? "confirmed" : "review"} /></td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{u.role !== "superadmin" && <><button className="btn" onClick={() => reset(u)}>Reset password</button> <button className="btn danger" onClick={() => setDel(u)}>Remove</button></>}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <ConfirmDialog open={!!del} title="Remove this account?" body={del ? `${del.name} (${del.email}) will no longer be able to sign in. Their marking data is kept.` : ""} yes="Remove account" onYes={remove} onNo={() => setDel(null)} />
    </div>
  );
}