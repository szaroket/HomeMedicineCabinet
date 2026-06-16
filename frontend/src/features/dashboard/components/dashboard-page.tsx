import { Link } from "react-router-dom";
import { AppLayout } from "@/app/components/app-layout";

export function DashboardPage() {
  return (
    <AppLayout>
      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <Link
          to="/cabinet"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
        >
          Moja apteczka
        </Link>
      </div>
    </AppLayout>
  );
}
