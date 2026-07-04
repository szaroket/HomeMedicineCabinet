import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 px-6 text-center">
      <h1 className="text-2xl font-semibold text-white">
        Nie znaleziono strony
      </h1>
      <p className="text-slate-400">
        Strona, której szukasz, nie istnieje lub została przeniesiona.
      </p>
      <Link
        to="/"
        className="rounded text-blue-500 hover:text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        Wróć do strony głównej
      </Link>
    </div>
  );
}
