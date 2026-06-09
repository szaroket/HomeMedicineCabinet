import { LogoutButton } from "@/features/auth/components/logout-button";

export function DashboardPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900">
      <p className="text-xl font-semibold text-white">Zalogowano</p>
      <LogoutButton />
    </div>
  );
}
