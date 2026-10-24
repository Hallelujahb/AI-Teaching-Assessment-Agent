// Owner: P1. Shell: sign in, side navigation, theme, one set of pages per role.
import { useEffect, useState } from "react";
import { api, hasToken, onUnauthorized, setToken } from "./api/client.js";
import Logo from "./components/Logo.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import SelectPage from "./pages/SelectPage.jsx";
import RunPage from "./pages/RunPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import RunsPage from "./pages/RunsPage.jsx";
import ResultsPage from "./pages/ResultsPage.jsx";
import ApprovalsPage from "./pages/ApprovalsPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import StudentDashboard from "./pages/StudentDashboard.jsx";

const ROLE = { superadmin: "Super admin", lecturer: "Lecturer", student: "Student" };
const NAV = [["dashboard", "Dashboard"], ["grade", "Grade a batch"], ["runs", "AI runs"], ["results", "Saved results"], ["approvals", "Approvals"], ["users", "Users"]];

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(hasToken());
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || "light");
  const [page, setPage] = useState("dashboard");
  const [flow, setFlow] = useState({ step: "select" });
  const [batch, setBatch] = useState(null);
  const [pending, setPending] = useState(0);

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("qeleme_theme", theme); }, [theme]);
  const signOut = () => { setToken(""); setUser(null); setPage("dashboard"); setFlow({ step: "select" }); };
  useEffect(() => {
    onUnauthorized(signOut);
    if (hasToken()) api.me().then(setUser).catch(signOut).finally(() => setChecking(false));
  }, []);
  useEffect(() => { if (user && user.role !== "student") api.approvals().then((l) => setPending(l.length)).catch(() => {}); }, [user, page]);

  const go = (p, extra = {}) => { setPage(p); setFlow(extra.flow || { step: "select" }); setBatch(extra.batch ?? null); };

  if (checking) return null;
  if (!user) return <AuthPage theme={theme} setTheme={setTheme} onLogin={(u) => { setUser(u); setPage(u.role === "student" ? "mine" : "dashboard"); }} />;

  const student = user.role === "student";
  const nav = student ? [["mine", "My results"]] : NAV.filter(([id]) => id !== "users" || user.role === "superadmin");
  const title = (nav.find(([id]) => id === page) || [0, ""])[1];

  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><Logo size={34} /><div><strong>Qeleme</strong><small>Teaching assessment agent</small></div></div>
        <nav>
          {nav.map(([id, label]) => (
            <button key={id} className={"navbtn" + (page === id ? " on" : "")} onClick={() => go(id)}>
              {label}{id === "approvals" && pending > 0 && <span className="count">{pending}</span>}
            </button>
          ))}
        </nav>
        <div className="gov"><small>Governance</small><p>The AI proposes. The code validates. The lecturer decides.</p></div>
      </aside>
      <div className="content">
        <header className="top">
          <span className="crumb">{title}</span>
          <div className="who">
            <span>{user.name} <span className="muted">· {ROLE[user.role]}</span></span>
            <button className="btn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Light mode" : "Dark mode"}</button>
            <button className="btn" onClick={signOut}>Sign out</button>
          </div>
        </header>
        <main>
          {page === "mine" && <StudentDashboard />}
          {page === "dashboard" && <DashboardPage user={user} onGo={go}
            onGrade={(params) => go("grade", { flow: { step: "run", params } })}
            onReview={(runId) => go("grade", { flow: { step: "review", runId } })}
            onResults={(id) => go("results", { batch: id })} />}
          {page === "grade" && flow.step === "select" && <SelectPage onStart={(params) => setFlow({ step: "run", params })} />}
          {page === "grade" && flow.step === "run" && <RunPage params={flow.params} onBack={() => go("grade")} onDone={(runId) => setFlow({ step: "review", runId })} />}
          {page === "grade" && flow.step === "review" && <ReviewPage runId={flow.runId} onBack={() => go("grade")} onConfirmed={() => go("results")} />}
          {page === "runs" && <RunsPage onReview={(runId) => go("grade", { flow: { step: "review", runId } })} />}
          {page === "results" && <ResultsPage initial={batch} />}
          {page === "approvals" && <ApprovalsPage role={user.role} onChange={setPending} />}
          {page === "users" && <AdminPage />}
        </main>
      </div>
    </div>
  );
}