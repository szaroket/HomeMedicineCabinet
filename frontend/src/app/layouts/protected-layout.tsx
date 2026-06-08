import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/store";

export function ProtectedLayout() {
  const { token } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
