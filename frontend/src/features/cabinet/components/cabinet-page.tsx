import { Link } from "react-router-dom";
import { CabinetList } from "@/features/cabinet/components/cabinet-list";
import { LogoutButton } from "@/features/auth/components/logout-button";
import { AppHeader } from "@/app/components/app-header";
import { AppFooter } from "@/app/components/app-footer";

export function CabinetPage() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-900">
      <header className="border-b border-slate-700 bg-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <AppHeader />
          <LogoutButton />
        </div>
      </header>

      <main className="grow px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Lista leków</h2>
          <Link
            to="/cabinet/add"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Dodaj lek
          </Link>
        </div>
        <CabinetList />
      </main>
      <AppFooter />
    </div>
  );
}
