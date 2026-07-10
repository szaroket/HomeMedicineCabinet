import { Link } from "react-router-dom";

export function DashboardEmpty() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
      <p className="text-slate-300">
        Twoja apteczka jest pusta. Dodaj pierwszy lek, aby zobaczyć
        podsumowanie.
      </p>
      <Link
        to="/cabinet/add"
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        Dodaj pierwszy lek
      </Link>
    </div>
  );
}
