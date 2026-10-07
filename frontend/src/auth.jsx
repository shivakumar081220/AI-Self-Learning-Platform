import { createContext, useContext, useEffect, useState } from "react";

import { getCurrentUser, loginAccount, registerAccount } from "./api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem("adaptive_access_token")) {
      setLoading(false);
      return;
    }
    getCurrentUser().then(setUser).catch(() => localStorage.removeItem("adaptive_access_token")).finally(() => setLoading(false));
  }, []);

  async function login(credentials) {
    const response = await loginAccount(credentials);
    localStorage.setItem("adaptive_access_token", response.access_token);
    setUser(response.user);
    return response.user;
  }

  async function register(details) {
    const response = await registerAccount(details);
    localStorage.setItem("adaptive_access_token", response.access_token);
    setUser(response.user);
    return response.user;
  }

  function logout() {
    localStorage.removeItem("adaptive_access_token");
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, isAuthenticated: Boolean(user), login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}