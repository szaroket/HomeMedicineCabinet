import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/store";
import { useSessionInit } from "@/features/auth/hooks/use-session-init";

export function ProtectedLayout() {
  const { token } = useAuth();
  const { isValidating } = useSessionInit();

  if (isValidating) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900">
        <p className="text-sm text-slate-400">Ładowanie…</p>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
