import { useState } from "react";
import { useAuth } from "./auth.jsx";
import { useT } from "./i18n.jsx";
import Login from "./views/Login.jsx";
import Dashboard from "./views/Dashboard.jsx";
import Cabinet from "./views/Cabinet.jsx";
import AdminPanel from "./views/AdminPanel.jsx";
import Chat from "./views/Chat.jsx";

export default function App() {
  const { t, lang, setLang } = useT();
  const { user, ready, logout, isSuperuser } = useAuth();
  const [view, setView] = useState("dashboard");

  if (!ready) {
    return (
      <div className="app boot">
        <span className="spinner" /> {t("app.title")}
      </div>
    );
  }

  if (!user) return <Login />;

  const nav = [
    { id: "dashboard", label: t("nav.dashboard") },
    { id: "cabinet", label: t("nav.cabinet") },
    { id: "chat", label: t("nav.chat") },
  ];
  if (isSuperuser) nav.push({ id: "admin", label: t("nav.admin") });

  // Guard: only super-users may render the admin view.
  const current = view === "admin" && !isSuperuser ? "dashboard" : view;

  return (
    <div className="app">
      <div className="topbar">
        <div className="logo">
          <span className="dot" /> {t("app.title")}
        </div>
        <nav className="nav">
          {nav.map((n) => (
            <button
              key={n.id}
              className={`nav-btn ${current === n.id ? "active" : ""}`}
              onClick={() => setView(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className="topbar-right">
          <select
            className="lang-select"
            value={lang}
            onChange={(e) => setLang(e.target.value)}
          >
            <option value="ru">RU</option>
            <option value="en">EN</option>
          </select>
          <span className="user-chip">{user.display_name || user.email}</span>
          <button className="ghost" onClick={logout}>
            {t("nav.logout")}
          </button>
        </div>
      </div>

      {current === "dashboard" && <Dashboard />}
      {current === "cabinet" && <Cabinet />}
      {current === "chat" && <Chat />}
      {current === "admin" && isSuperuser && <AdminPanel />}
    </div>
  );
}
