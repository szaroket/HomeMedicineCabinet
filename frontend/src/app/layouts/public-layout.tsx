import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/features/auth/store";

export function PublicLayout() {
  const { token } = useAuth();

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
