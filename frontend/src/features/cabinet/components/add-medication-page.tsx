import { Link } from "react-router-dom";
import { AddMedicationForm } from "@/features/cabinet/components/add-medication-form";
import { AppLayout } from "@/app/components/app-layout";

export function AddMedicationPage() {
  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="flex flex-col items-center">
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
        </div>
      </div>
    </AppLayout>
  );
}
