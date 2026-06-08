import { getStoredToken, setStoredToken } from "@/features/auth/store";
import { AuthError } from "@/lib/errors";

const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`;

// Single-flight latch so concurrent 401s share one refresh promise
let refreshing: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

// Shared single-flight refresh: all callers (api-client 401 retry and
// use-session-init cold start) go through this one latch so only one refresh —
// and one Supabase refresh-token rotation — is ever in flight at a time.
export function refreshOnce(): Promise<string | null> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getStoredToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    const newToken = await refreshOnce();
    if (newToken) {
      // Store the token — we can't call setSession here (no user object),
      // but the store reads from localStorage on next render cycle.
      // The caller's hook will re-query /auth/me to rehydrate the user.
      setStoredToken(newToken);
      const retryHeaders = new Headers(options.headers);
      retryHeaders.set("Authorization", `Bearer ${newToken}`);
      return fetch(`${BASE}${path}`, {
        ...options,
        headers: retryHeaders,
        credentials: "include",
      });
    }
    // Refresh failed — surface a typed error. The React layer (AuthProvider)
    // clears the session and redirects; the transport layer never navigates.
    throw new AuthError("Session expired. Please log in again.");
  }

  return res;
}

export async function apiJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await apiFetch(path, options);
  if (!res.ok) throw res;
  return res.json() as Promise<T>;
}
