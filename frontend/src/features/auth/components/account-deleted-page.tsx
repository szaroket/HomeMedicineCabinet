import { Link, useSearchParams } from "react-router-dom";

export function AccountDeletedPage() {
  const [searchParams] = useSearchParams();
  const partial = searchParams.get("partial") === "1";

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
