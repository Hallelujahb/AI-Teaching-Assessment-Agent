// Owner: P1. Shell: sign in, side menu (a drawer on small screens), theme, one set of pages per role.
import { useEffect, useState } from "react";
import { api, hasToken, onUnauthorized, setToken } from "./api/client.js";
import Logo from "./components/Logo.jsx";
import Icon from "./components/Icon.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import Login from "./pages/Login.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AssessmentsPage from "./pages/AssessmentsPage.jsx";
import SelectPage from "./pages/SelectPage.jsx";
import RunPage from "./pages/RunPage.jsx";
import ReviewPage from "./pages/ReviewPage.jsx";
import RunsPage from "./pages/RunsPage.jsx";
import ResultsPage from "./pages/ResultsPage.jsx";
import ApprovalsPage from "./pages/ApprovalsPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import StudentDashboard from "./pages/StudentDashboard.jsx";
import StudentExams from "./pages/StudentExams.jsx";
import ClassesPage from "./pages/ClassesPage.jsx";
import { initials } from "./util.js";

const ROLE = { superadmin: "Super admin", lecturer: "Lecturer", student: "Student" };
const NAV = [
  ["dashboard", "Dashboard", "dashboard"], ["assessments", "Assessments", "assess"], ["classes", "Classes", "classes"], ["grade", "Grade a batch", "grade"],
  ["runs", "AI runs", "runs"], ["results", "Saved results", "results"], ["approvals", "Approvals", "approvals"], ["users", "Users", "users"],
];

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(hasToken());
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || "light");
  const [page, setPage] = useState("dashboard");
  const [flow, setFlow] = useState({ step: "select" });
  const [authView, setAuthView] = useState("login");
  const [batch, setBatch] = useState(null);
  const [pending, setPending] = useState(0);
  const [menu, setMenu] = useState(false);

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("qeleme_theme", theme); }, [theme]);
  const signOut = () => { setToken(""); setUser(null); setPage("dashboard"); setFlow({ step: "select" }); setMenu(false); };
  useEffect(() => {
    api.health().catch(() => {});                       // wakes the database while the sign-in page is showing
    onUnauthorized(signOut);
    if (hasToken()) api.me().then(setUser).catch(signOut).finally(() => setChecking(false));
  }, []);
  useEffect(() => { if (user && user.role !== "student") Promise.all([api.approvals(), api.resets()]).then(([a, r]) => setPending(a.length + r.length)).catch(() => {}); }, [user, page]);

  const go = (p, extra = {}) => { setPage(p); setFlow(extra.flow || { step: "select" }); setBatch(extra.batch ?? null); setMenu(false); window.scrollTo(0, 0); };

  if (checking) return null;
  if (!user) {
    if (authView === "login") return <Login onLogin={(data) => { setToken(data.token); setUser(data.user); setPage(data.user.role === "student" ? "exams" : "dashboard"); }} onRegister={() => setAuthView("auth")} onForgot={() => setAuthView("auth")} />;
    return <AuthPage theme={theme} setTheme={setTheme} onLogin={(u) => { setUser(u); setPage(u.role === "student" ? "exams" : "dashboard"); setAuthView("login"); }} />;
  }

  const student = user.role === "student";
  const nav = student ? [["exams", "My exams", "assess"], ["mine", "My results", "mine"]] : NAV.filter(([id]) => id !== "users" || user.role === "superadmin");
  const title = (nav.find(([id]) => id === page) || [0, ""])[1];
  const code = user.student_id || user.staff_id;
  const startRun = (params) => go("grade", { flow: { step: "run", params } });

  return (
    <div className="app">
      {menu && <div className="navscrim" onClick={() => setMenu(false)} />}
      <aside className={"side" + (menu ? " open" : "")}>
        <div className="brand"><Logo size={36} /><div><strong>Qeleme</strong><small>Teaching assessment agent</small></div></div>
        <nav aria-label="Main">
          {nav.map(([id, label, icon]) => (
            <button key={id} className={"navbtn" + (page === id ? " on" : "")} onClick={() => go(id)} aria-current={page === id ? "page" : undefined}>
              <Icon name={icon} /><span>{label}</span>{id === "approvals" && pending > 0 && <span className="count">{pending}</span>}
            </button>
          ))}
        </nav>
        <div className="gov"><p>The AI proposes. The code validates. The lecturer decides.</p></div>
        <div className="usercard">
          <div className="row nowrap"><span className="avatar">{initials(user.name)}</span>
            <div className="grow"><strong>{user.name}</strong><div className="muted small">{ROLE[user.role]}{code ? ` · ${code}` : ""}</div></div></div>
          <div className="row nowrap">
            <button className="btn grow" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Light mode" : "Dark mode"}</button>
            <button className="btn grow" onClick={signOut}>Sign out</button>
          </div>
        </div>
      </aside>
      <div className="content">
        <header className="top">
          <button className="menubtn" aria-label="Open menu" onClick={() => setMenu(true)}><Icon name="menu" size={22} /></button>
          <span className="crumb">{title}</span>
        </header>
        <main>
          {page === "exams" && <StudentExams />}
          {page === "mine" && <StudentDashboard />}
          {page === "classes" && <ClassesPage />}
          {page === "dashboard" && <DashboardPage user={user} onGo={go} onGrade={startRun}
            onReview={(runId) => go("grade", { flow: { step: "review", runId } })} onResults={(id) => go("results", { batch: id })} />}
          {page === "assessments" && <AssessmentsPage onGrade={startRun} />}
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
