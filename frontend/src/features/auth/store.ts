import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from "react";
import type { ReactNode } from "react";
import { createElement } from "react";
import { queryClient } from "@/lib/query-client";
import { AuthError } from "@/lib/errors";

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

  // Centralised auth-failure handling: when any query/mutation rejects with an
  // AuthError (refresh failed in the api-client), clear the session so
  // ProtectedLayout redirects to /login — keeping navigation out of transport.
  useEffect(() => {
    const handle = (error: unknown) => {
      if (error instanceof AuthError) clearSession();
    };
    const unsubQueries = queryClient
      .getQueryCache()
      .subscribe((event) => handle(event.query.state.error));
    const unsubMutations = queryClient
      .getMutationCache()
      .subscribe((event) => handle(event.mutation?.state.error));
    return () => {
      unsubQueries();
      unsubMutations();
    };
  }, [clearSession]);

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

// Single source of truth for the token's localStorage key. Non-React callers
// (api-client, use-session-init) persist the token through this so the key and
// format live in exactly one place.
export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}
