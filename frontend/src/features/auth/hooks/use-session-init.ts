import { useEffect, useRef, useState } from "react";
import { useAuth, setStoredToken } from "@/features/auth/store";
import { useMe } from "@/features/auth/api/auth-queries";
import { refreshOnce } from "@/lib/api-client";

export function useSessionInit() {
  const { token, user, setSession, clearSession } = useAuth();
  const hasToken = Boolean(token);

  // refreshDone starts true when a token already exists (no silent refresh needed)
  const [refreshDone, setRefreshDone] = useState(hasToken);
  const attempted = useRef(false);

  useEffect(() => {
    if (hasToken || attempted.current) return;
    attempted.current = true;
    refreshOnce().then((newToken) => {
      if (newToken) {
        setStoredToken(newToken);
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
