import { useLogout } from "@/features/auth/api/auth-queries";
import { useNavigate } from "react-router-dom";

export function LogoutButton() {
  const navigate = useNavigate();
  const { mutate, isPending } = useLogout();

  return (
    <button
      onClick={() => mutate(undefined, { onSettled: () => navigate("/login") })}
      disabled={isPending}
      className="rounded border border-slate-600 px-4 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:bg-slate-700 hover:text-white disabled:opacity-50"
    >
      {isPending ? "Wylogowywanie…" : "Wyloguj się"}
    </button>
  );
}
