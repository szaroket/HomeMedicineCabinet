import { Link } from "react-router-dom";
import { LogoutButton } from "@/features/auth/components/logout-button";
import { AppHeader } from "@/app/components/app-header";
import { AppFooter } from "@/app/components/app-footer";

export function DashboardPage() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900">
      <AppHeader />
      <Link
        to="/cabinet"
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        Moja apteczka
      </Link>
      <LogoutButton />
      <div className="absolute bottom-0 w-full">
        <AppFooter />
      </div>
    </div>
  );
}
