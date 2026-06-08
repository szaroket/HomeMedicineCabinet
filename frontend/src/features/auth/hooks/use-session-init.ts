import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/features/auth/store";
import { useMe } from "@/features/auth/api/auth-queries";

const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`;

async function trySilentRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token: string };
    return data.access_token;
  } catch {
    return null;
  }
}

export function useSessionInit() {
  const { token, user, setSession, clearSession } = useAuth();
  const hasToken = Boolean(token);

  // refreshDone starts true when a token already exists (no silent refresh needed)
  const [refreshDone, setRefreshDone] = useState(hasToken);
  const attempted = useRef(false);

  useEffect(() => {
    if (hasToken || attempted.current) return;
    attempted.current = true;
    trySilentRefresh().then((newToken) => {
      if (newToken) {
        localStorage.setItem("auth_token", newToken);
        setSession(newToken, { id: "", email: "" });
      }
      setRefreshDone(true);
    });
  }, [hasToken, setSession]);

  const { data, isError, isLoading } = useMe(
    refreshDone && hasToken && !user?.email,
  );

  useEffect(() => {
    if (data && token) {
      setSession(token, data);
    }
  }, [data, token, setSession]);

  useEffect(() => {
    if (isError) {
      clearSession();
    }
  }, [isError, clearSession]);

  const isValidating =
    !refreshDone || (hasToken && (!user?.email || isLoading));

  return { isValidating };
}
