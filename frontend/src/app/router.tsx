import { createBrowserRouter } from "react-router-dom";
import { PublicLayout } from "@/app/layouts/public-layout";
import { ProtectedLayout } from "@/app/layouts/protected-layout";
import { LoginPage } from "@/features/auth/components/login-page";
import { RegisterPage } from "@/features/auth/components/register-page";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { CabinetPage } from "@/features/cabinet/components/cabinet-page";
import { AddMedicationPage } from "@/features/cabinet/components/add-medication-page";
import { SettingsPage } from "@/features/settings/components/settings-page";

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <ProtectedLayout />,
    children: [
      { path: "/", element: <DashboardPage /> },
      { path: "/cabinet", element: <CabinetPage /> },
      { path: "/cabinet/add", element: <AddMedicationPage /> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
]);
