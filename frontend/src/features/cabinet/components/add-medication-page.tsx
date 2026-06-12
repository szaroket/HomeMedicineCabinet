import { Link } from "react-router-dom";
import { AddMedicationForm } from "@/features/cabinet/components/add-medication-form";
import { AppHeader } from "@/app/components/app-header";
import { LogoutButton } from "@/features/auth/components/logout-button";

export function AddMedicationPage() {
  return (
    <div className="min-h-screen bg-slate-900">
      <header className="border-b border-slate-700 bg-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <AppHeader />
          <LogoutButton />
        </div>
      </header>

      <main className="flex flex-col items-center px-4 py-8">
        <div className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-800 p-6 shadow-lg">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Dodaj lek</h2>
            <Link
              to="/cabinet"
              className="text-sm text-slate-400 hover:text-white"
            >
              ← Apteczka
            </Link>
          </div>
          <AddMedicationForm />
        </div>
      </main>
    </div>
  );
}
