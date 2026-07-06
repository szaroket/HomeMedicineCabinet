import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/features/auth/store";

export function AccountDeletedPage() {
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  const partial = searchParams.get("partial") === "1";

  // A valid token means the account still exists, so this visitor cannot be a
  // just-deleted user seeing their confirmation — send them to the dashboard.
  // Legitimately-deleted users have their session torn down first (see
  // useDeleteAccount), so they arrive here token-less and still see the page.
  if (token) return <Navigate to="/" replace />;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 px-6 text-center">
      <h1 className="text-2xl font-semibold text-white">
        Konto zostało usunięte
      </h1>
      <p className="text-red-400">
        {partial
          ? "Konto zostało częściowo usunięte — zaloguj się ponownie, aby dokończyć."
          : "Twoje konto oraz wszystkie powiązane dane zostały trwale usunięte."}
      </p>
      <Link
        to="/login"
        className="rounded text-blue-500 hover:text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        Powrót
      </Link>
    </main>
  );
}
