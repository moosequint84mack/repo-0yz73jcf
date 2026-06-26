import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "./api";

const AuthContext = createContext({
  user: null,
  ready: false,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    setToken("");
    setUser(null);
  }, []);

  // Restore session from a stored token on first load.
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      if (!getToken()) {
        setReady(true);
        return;
      }
      try {
        const me = await api.me();
        if (!cancelled) setUser(me);
      } catch (_) {
        setToken("");
      } finally {
        if (!cancelled) setReady(true);
      }
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  // A 401 from any request forces a logout.
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const value = useMemo(
    () => ({ user, ready, login, logout, isSuperuser: user?.role === "superuser" }),
    [user, ready, login, logout]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
