import { Link } from "react-router-dom";
import { RegisterForm } from "@/features/auth/components/register-form";
import logo from "@/assets/logo.png";

export function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      <div className="w-full max-w-md rounded-lg border border-slate-700 bg-slate-800 p-8 shadow-xl">
        <div className="mb-6">
          <div className="mb-3 flex flex-col items-center gap-0">
            <img src={logo} alt="Apteczka domowa" className="h-16 w-16" />
            <h1 className="my-0 whitespace-nowrap text-center text-2xl font-bold text-white">
              Apteczka domowa
            </h1>
          </div>
          <p className="mt-1 text-center text-sm text-slate-400">
            Kontroluj stan swojej apteczki — terminy ważności, zapasy i aktywne
            leki, zanim zabraknie ich w połowie kuracji.
          </p>
        </div>
        <h2 className="mb-4 text-center text-base font-semibold text-slate-200">
          Utwórz konto
        </h2>
        <RegisterForm />
        <p className="mt-4 text-center text-sm text-slate-400">
          Masz już konto?{" "}
          <Link
            to="/login"
            className="text-blue-400 hover:text-blue-300 hover:underline"
          >
            Zaloguj się
          </Link>
        </p>
      </div>
    </div>
  );
}
