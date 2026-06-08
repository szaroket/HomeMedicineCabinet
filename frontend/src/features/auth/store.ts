import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { createElement } from "react";

const TOKEN_KEY = "auth_token";

export interface AuthUser {
  id: string;
  email: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser) => void;
  clearSession: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [user, setUser] = useState<AuthUser | null>(null);

  const setSession = useCallback((newToken: string, newUser: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(newUser);
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return createElement(
    AuthContext.Provider,
    { value: { token, user, setSession, clearSession } },
    children,
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
