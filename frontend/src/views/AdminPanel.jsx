import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth.jsx";
import { useT } from "../i18n.jsx";

const fmtTime = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString();
  } catch (_) {
    return iso;
  }
};

export default function AdminPanel() {
  const { t } = useT();
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const [form, setForm] = useState({ email: "", display_name: "", password: "", role: "user" });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setUsers(await api.adminUsers());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const patch = async (id, body) => {
    setBusyId(id);
    setError(null);
    try {
      await api.adminUpdateUser(id, body);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (u) => {
    if (!window.confirm(t("admin.confirmDelete", { email: u.email }))) return;
    setBusyId(u.id);
    setError(null);
    try {
      await api.adminDeleteUser(u.id);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const create = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await api.adminCreateUser({ ...form, is_active: true });
      setForm({ email: "", display_name: "", password: "", role: "user" });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="view">
      <div className="panel">
        <h3>
          <span>{t("admin.title")}</span>
          <span className="muted">{t("admin.subtitle")}</span>
        </h3>
        <div className="body">
          {error && <div className="error">⚠ {error}</div>}
          <table>
            <thead>
              <tr>
                <th>{t("admin.col.email")}</th>
                <th>{t("admin.col.name")}</th>
                <th>{t("admin.col.role")}</th>
                <th>{t("admin.col.status")}</th>
                <th>{t("admin.col.lastLogin")}</th>
                <th>{t("admin.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me?.id;
                const busy = busyId === u.id;
                return (
                  <tr key={u.id}>
                    <td>{u.email}</td>
                    <td>{u.display_name}</td>
                    <td>
                      <span className="tag">
                        {u.role === "superuser"
                          ? t("admin.role.superuser")
                          : t("admin.role.user")}
                      </span>
                    </td>
                    <td className={u.is_active ? "green" : "yellow"}>
                      {u.is_active ? t("admin.active") : t("admin.inactive")}
                    </td>
                    <td className="muted">{fmtTime(u.last_login_at) || t("admin.never")}</td>
                    <td>
                      <div className="admin-actions">
                        <button
                          className="ghost sm"
                          disabled={busy || self}
                          onClick={() => patch(u.id, { is_active: !u.is_active })}
                        >
                          {u.is_active ? t("admin.deactivate") : t("admin.activate")}
                        </button>
                        <button
                          className="ghost sm"
                          disabled={busy || self}
                          onClick={() =>
                            patch(u.id, {
                              role: u.role === "superuser" ? "user" : "superuser",
                            })
                          }
                        >
                          {u.role === "superuser" ? t("admin.makeUser") : t("admin.makeAdmin")}
                        </button>
                        <button
                          className="ghost sm danger"
                          disabled={busy || self}
                          onClick={() => remove(u)}
                        >
                          {t("admin.delete")}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <h3>{t("admin.createTitle")}</h3>
        <div className="body">
          <form className="admin-create" onSubmit={create}>
            <div className="field">
              <label>{t("admin.col.email")}</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="field">
              <label>{t("admin.col.name")}</label>
              <input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </div>
            <div className="field">
              <label>{t("auth.password")}</label>
              <input
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="field">
              <label>{t("admin.col.role")}</label>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                <option value="user">{t("admin.role.user")}</option>
                <option value="superuser">{t("admin.role.superuser")}</option>
              </select>
            </div>
            <div className="field">
              <label>&nbsp;</label>
              <button type="submit" disabled={creating}>
                {t("admin.create")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
