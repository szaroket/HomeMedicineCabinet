import { createBrowserRouter } from "react-router-dom";
import { PublicLayout } from "@/app/layouts/public-layout";
import { ProtectedLayout } from "@/app/layouts/protected-layout";
import { LoginPlaceholder } from "@/features/auth/components/login-placeholder";
import { RegisterPlaceholder } from "@/features/auth/components/register-placeholder";
import { DashboardPlaceholder } from "@/features/dashboard/components/dashboard-placeholder";

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: "/login", element: <LoginPlaceholder /> },
      { path: "/register", element: <RegisterPlaceholder /> },
    ],
  },
  {
    element: <ProtectedLayout />,
    children: [{ path: "/", element: <DashboardPlaceholder /> }],
  },
]);
