// Sign in and sign up. The person first says who they are: student or lecturer.
import { useState } from "react";
import { api, setToken } from "../api/client.js";
import Logo from "../components/Logo.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

const HINT = {
  student: "Your lecturer approves new student accounts. Your student id is issued for you.",
  lecturer: "A super admin approves new lecturer accounts. Your staff id is issued for you.",
};

export default function AuthPage({ onLogin, theme, setTheme }) {
  const [role, setRole] = useState("student");
  const [mode, setMode] = useState("in");
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const admin = role === "admin";
  const pick = (r) => { setRole(r); setErr(null); if (r === "admin") setMode("in"); };

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      if (mode === "in") { const r = await api.login(f.email, f.password, role); setToken(r.token); onLogin(r.user); }
      else setSent((await api.register({ ...f, role })).message);
    } catch (x) { setErr(x); } finally { setBusy(false); }
  };

  return (
    <div className="auth">
      <div className="hero">
        <Logo />
        <p>The AI proposes. The code validates. The lecturer decides.</p>
      </div>
      <div className="formside">
        <div className="authcard">
          {sent ? (
            <div className="stack">
              <h1>Request sent</h1>
              <p>{sent}</p>
              <button className="btn primary" onClick={() => { setSent(null); setMode("in"); }}>Back to sign in</button>
            </div>
          ) : (
            <form onSubmit={submit} className="stack">
              <h1>{admin ? "Administrator sign in" : mode === "in" ? "Sign in" : "Create your account"}</h1>
              {!admin && (
                <div className="seg" role="group" aria-label="I am a">
                  {["student", "lecturer"].map((r) => <button type="button" key={r} aria-pressed={role === r} onClick={() => pick(r)}>{r === "student" ? "Student" : "Lecturer"}</button>)}
                </div>
              )}
              {mode === "up" && <div><label htmlFor="nm">Full name</label><input id="nm" value={f.name} onChange={up("name")} required /></div>}
              <div><label htmlFor="em">Email</label><input id="em" type="email" autoComplete="username" value={f.email} onChange={up("email")} required /></div>
              <div><label htmlFor="pw">Password</label><input id="pw" type="password" autoComplete={mode === "in" ? "current-password" : "new-password"} value={f.password} onChange={up("password")} required minLength={mode === "up" ? 8 : undefined} />
                {mode === "up" && <p className="muted small">At least 8 characters.</p>}</div>
              <ErrorBanner error={err} />
              {mode === "up" && <p className="muted small">{HINT[role]}</p>}
              <button className="btn primary wide" disabled={busy}>{busy ? "Please wait..." : mode === "in" ? "Sign in" : "Request account"}</button>
              {!admin && (
                <p className="small">{mode === "in" ? "New here? " : "Already approved? "}
                  <button type="button" className="link" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(null); }}>{mode === "in" ? "Create an account" : "Sign in"}</button></p>
              )}
            </form>
          )}
          <div className="row between authfoot">
            <button className="link small" onClick={() => pick(admin ? "student" : "admin")}>{admin ? "Back to student and lecturer" : "Administrator?"}</button>
            <button className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Light mode" : "Dark mode"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}