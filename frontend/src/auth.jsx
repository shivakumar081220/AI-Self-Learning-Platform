import { createContext, useContext, useEffect, useState } from "react";

import { getCurrentUser, loginAccount, registerAccount } from "./api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [restoreError, setRestoreError] = useState("");

  async function restoreSession() {
    setLoading(true);
    setRestoreError("");
    const localToken = localStorage.getItem("adaptive_access_token");
    const sessionToken = sessionStorage.getItem("adaptive_access_token");
    if (!localToken && !sessionToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await getCurrentUser());
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        localStorage.removeItem("adaptive_access_token");
        sessionStorage.removeItem("adaptive_access_token");
        setUser(null);
      } else {
        setRestoreError(error.message);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    restoreSession();
  }, []);

  async function login(credentials, rememberMe = false) {
    const response = await loginAccount(credentials);
    const storage = rememberMe ? localStorage : sessionStorage;
    const otherStorage = rememberMe ? sessionStorage : localStorage;
    otherStorage.removeItem("adaptive_access_token");
    storage.setItem("adaptive_access_token", response.access_token);
    setUser(response.user);
    setRestoreError("");
    return response.user;
  }

  async function register(details) {
    const response = await registerAccount(details);
    localStorage.setItem("adaptive_access_token", response.access_token);
    setUser(response.user);
    setRestoreError("");
    return response.user;
  }

  function logout() {
    localStorage.removeItem("adaptive_access_token");
    sessionStorage.removeItem("adaptive_access_token");
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, restoreError, retryRestore: restoreSession, isAuthenticated: Boolean(user), login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}