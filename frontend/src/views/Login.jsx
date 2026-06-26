import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth.jsx";
import { useT } from "../i18n.jsx";

export default function Login() {
  const { t, lang, setLang } = useT();
  const { login } = useAuth();
  const [mode, setMode] = useState("login"); // login | register
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await api.register({ email: email.trim(), password, display_name: displayName });
        setNotice(t("auth.registered"));
        setMode("login");
        setPassword("");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-lang">
        <select value={lang} onChange={(e) => setLang(e.target.value)}>
          <option value="ru">RU</option>
          <option value="en">EN</option>
        </select>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-logo">
          <span className="dot" /> {t("app.title")}
        </div>
        <div className="auth-sub">{t("auth.subtitle")}</div>

        <div className="auth-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            {t("auth.signin")}
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            {t("auth.signup")}
          </button>
        </div>

        {mode === "register" && (
          <label className="auth-field">
            <span>{t("auth.displayName")}</span>
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="name"
            />
          </label>
        )}
        <label className="auth-field">
          <span>{t("auth.email")}</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>
        <label className="auth-field">
          <span>{t("auth.password")}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={mode === "register" ? 8 : 1}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
          {mode === "register" && <small className="muted">{t("auth.passwordHint")}</small>}
        </label>

        {error && <div className="auth-error">⚠ {error}</div>}
        {notice && <div className="auth-notice">{notice}</div>}

        <button type="submit" disabled={busy} className="auth-submit">
          {busy
            ? t("auth.loggingIn")
            : mode === "login"
              ? t("auth.loginBtn")
              : t("auth.registerBtn")}
        </button>

        <button
          type="button"
          className="auth-switch"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
            setNotice(null);
          }}
        >
          {mode === "login" ? t("auth.toRegister") : t("auth.toLogin")}
        </button>
      </form>
    </div>
  );
}
