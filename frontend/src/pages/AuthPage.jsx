// Sign in, sign up and forgotten passwords. The person first says who they are: student or lecturer.
// Sign in takes an email, a student id or a staff id. A forgotten password needs a one-time code from staff.
import { useState } from "react";
import { api, setToken } from "../api/client.js";
import Logo from "../components/Logo.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

const HINT = {
  student: "Your lecturer approves new student accounts. Your student id is issued for you.",
  lecturer: "A super admin approves new lecturer accounts. Your staff id is issued for you.",
};
const TITLE = { in: "Sign in", up: "Create your account", forgot: "Forgot your password?", reset: "Choose a new password" };

export default function AuthPage({ onLogin, theme, setTheme }) {
  const [role, setRole] = useState("student");
  const [mode, setMode] = useState("in");
  const [f, setF] = useState({ name: "", email: "", password: "", code: "" });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const admin = role === "admin";
  const pick = (r) => { setRole(r); setErr(null); if (r === "admin") setMode("in"); };
  const go = (m) => { setMode(m); setErr(null); };

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      if (mode === "in") { const r = await api.login(f.email, f.password, role); setToken(r.token); onLogin(r.user); }
      else if (mode === "up") setDone({ text: (await api.register({ name: f.name, email: f.email, password: f.password, role })).message, next: "in" });
      else if (mode === "forgot") setDone({ text: (await api.forgot(f.email)).message, next: "reset" });
      else setDone({ text: (await api.resetPassword({ identifier: f.email, code: f.code, password: f.password })).message, next: "in" });
    } catch (x) { setErr(x); } finally { setBusy(false); }
  };

  const idLabel = mode === "up" ? "Email" : "Email, student ID or staff ID";
  const button = { in: "Sign in", up: "Request account", forgot: "Ask for a code", reset: "Change password" }[mode];

  return (
    <div className="auth">
      <div className="hero">
        <Logo />
        <p>The AI proposes. The code validates. The lecturer decides.</p>
      </div>
      <div className="formside">
        <div className="authcard">
          {done ? (
            <div className="stack">
              <h1>{done.next === "reset" ? "Request sent" : "Done"}</h1>
              <p>{done.text}</p>
              <button className="btn primary" onClick={() => { setDone(null); setMode(done.next); setF({ ...f, password: "", code: "" }); }}>
                {done.next === "reset" ? "I have a code" : "Back to sign in"}</button>
            </div>
          ) : (
            <form onSubmit={submit} className="stack">
              <h1>{admin && mode === "in" ? "Administrator sign in" : TITLE[mode]}</h1>
              {!admin && (mode === "in" || mode === "up") && (
                <div className="seg" role="group" aria-label="I am a">
                  {["student", "lecturer"].map((r) => <button type="button" key={r} aria-pressed={role === r} onClick={() => pick(r)}>{r === "student" ? "Student" : "Lecturer"}</button>)}
                </div>
              )}
              {mode === "forgot" && <p className="muted small">Enter your email, student ID or staff ID. Your lecturer (or a super admin, for lecturers) will give you a one-time code.</p>}
              {mode === "up" && <div><label htmlFor="nm">Full name</label><input id="nm" value={f.name} onChange={up("name")} required /></div>}
              <div><label htmlFor="em">{idLabel}</label><input id="em" type={mode === "up" ? "email" : "text"} autoComplete="username" autoCapitalize="none" value={f.email} onChange={up("email")} required /></div>
              {mode === "reset" && <div><label htmlFor="cd">One-time code</label><input id="cd" inputMode="numeric" pattern="[0-9]*" maxLength={8} autoComplete="one-time-code" value={f.code} onChange={up("code")} required /></div>}
              {mode !== "forgot" && (
                <div><label htmlFor="pw">{mode === "reset" ? "New password" : "Password"}</label>
                  <input id="pw" type="password" autoComplete={mode === "in" ? "current-password" : "new-password"} value={f.password} onChange={up("password")} required minLength={mode === "in" ? undefined : 8} />
                  {mode !== "in" && <p className="muted small">At least 8 characters.</p>}
                  {mode === "in" && !admin && <p className="small" style={{ margin: ".4rem 0 0" }}><button type="button" className="link" onClick={() => go("forgot")}>Forgot your password?</button></p>}</div>
              )}
              <ErrorBanner error={err} />
              {mode === "up" && <p className="muted small">{HINT[role]}</p>}
              <button className="btn primary wide" disabled={busy}>{busy ? "Please wait..." : button}</button>
              {!admin && (mode === "in" || mode === "up") && (
                <p className="small">{mode === "in" ? "New here? " : "Already approved? "}
                  <button type="button" className="link" onClick={() => go(mode === "in" ? "up" : "in")}>{mode === "in" ? "Create an account" : "Sign in"}</button></p>
              )}
              {mode === "forgot" && <p className="small"><button type="button" className="link" onClick={() => go("reset")}>I already have a code</button> · <button type="button" className="link" onClick={() => go("in")}>Back to sign in</button></p>}
              {mode === "reset" && <p className="small"><button type="button" className="link" onClick={() => go("forgot")}>I need a new code</button> · <button type="button" className="link" onClick={() => go("in")}>Back to sign in</button></p>}
            </form>
          )}
          <div className="row between authfoot">
            <button className="link small" onClick={() => { setDone(null); pick(admin ? "student" : "admin"); }}>{admin ? "Back to student and lecturer" : "Administrator?"}</button>
            <button className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Light mode" : "Dark mode"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
