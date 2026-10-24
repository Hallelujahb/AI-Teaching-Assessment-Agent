// Super admin: every account, add one, reset a password, remove one.
import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ErrorBanner from "../components/ErrorBanner.jsx";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import StatusBadge from "../components/StatusBadge.jsx";

const blank = { name: "", email: "", role: "lecturer", student_id: "", password: "" };

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [f, setF] = useState(blank);
  const [err, setErr] = useState(null);
  const [del, setDel] = useState(null);
  const load = () => api.adminUsers().then(setUsers).catch(setErr);
  useEffect(() => { load(); }, []);
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const add = async (e) => { e.preventDefault(); setErr(null); try { await api.adminAddUser(f); setF(blank); load(); } catch (x) { setErr(x); } };
  const reset = (u) => { const p = window.prompt(`New password for ${u.email} (8+ characters)`); if (p) api.adminResetPassword(u.id, p).then(() => setErr(null)).catch(setErr); };
  const remove = async () => { try { await api.adminDeleteUser(del.id); setDel(null); load(); } catch (x) { setErr(x); setDel(null); } };

  return (
    <div className="stack">
      <h1>Users</h1>
      <ErrorBanner error={err} />
      <form className="panel stack" onSubmit={add}>
        <h2>Add an account</h2>
        <p className="muted small">Accounts you add are active at once. People who sign up themselves appear under Approvals.</p>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <div style={{ flex: 1, minWidth: 150 }}><label>Name</label><input value={f.name} onChange={up("name")} required /></div>
          <div style={{ flex: 1, minWidth: 190 }}><label>Email</label><input type="email" value={f.email} onChange={up("email")} required /></div>
          <div style={{ width: 130 }}><label>Role</label><select value={f.role} onChange={up("role")}><option value="lecturer">Lecturer</option><option value="student">Student</option></select></div>
          {f.role === "student" && <div style={{ width: 110 }}><label>Student id</label><input value={f.student_id} onChange={up("student_id")} placeholder="ST001" required /></div>}
          <div style={{ width: 160 }}><label>Password (8+)</label><input type="password" value={f.password} onChange={up("password")} required minLength={8} /></div>
          <button className="btn primary">Create account</button>
        </div>
      </form>
      <div className="panel" style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Student id</th><th>Status</th><th /></tr></thead>
          <tbody>{users.map((u) => (
            <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.student_id || ""}</td>
              <td><StatusBadge status={u.status === "active" ? "confirmed" : "review"} /></td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>{u.role !== "superadmin" && <><button className="btn" onClick={() => reset(u)}>Reset password</button> <button className="btn danger" onClick={() => setDel(u)}>Remove</button></>}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <ConfirmDialog open={!!del} title="Remove this account?" body={del ? `${del.name} (${del.email}) will no longer be able to sign in. Their marking data is kept.` : ""} yes="Remove account" onYes={remove} onNo={() => setDel(null)} />
    </div>
  );
}