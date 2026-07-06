import { useId, useState } from "react";
import { useAuth } from "@/features/auth/store";
import { useDeleteAccount } from "@/features/settings/api/settings-queries";

export function DeleteAccountSection() {
  const { user } = useAuth();
  const { mutate, isPending } = useDeleteAccount();
  const [open, setOpen] = useState(false);
  const [confirmValue, setConfirmValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();

  const canConfirm = confirmValue === user?.email;

  function openDialog() {
    setConfirmValue("");
    setError(null);
    setOpen(true);
  }

  function closeDialog() {
    setOpen(false);
    setConfirmValue("");
    setError(null);
  }

  function onConfirm() {
    if (!canConfirm) return;
    setError(null);
    mutate(undefined, {
      onSuccess: () => {
        // Hard redirect (not router `navigate()`): see useDeleteAccount for why.
        window.location.href = "/account-deleted";
      },
      onError: (mutationError) => {
        if (mutationError instanceof Response && mutationError.status === 502) {
          window.location.href = "/account-deleted?partial=1";
          return;
        }
        setError("Nie udało się usunąć konta.");
      },
    });
  }

  return (
    <div className="mt-10 border-t border-slate-700 pt-6">
      <h3 className="text-base font-semibold text-red-400">Usuń konto</h3>
      <p className="mt-1 max-w-sm text-sm text-slate-400">
        Ta operacja jest trwała i nieodwracalna. Usunięte zostaną wszystkie
        Twoje dane oraz konto logowania.
      </p>
      <button
        type="button"
        onClick={openDialog}
        className="mt-4 rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
      >
        Usuń konto
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={closeDialog}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-lg border border-slate-600 bg-slate-800 p-6 shadow-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="mb-3 text-lg font-semibold text-white">
              Usuń konto
            </h2>
            <p className="text-sm text-slate-300">
              Ta operacja jest trwała. Aby potwierdzić, wpisz swój adres e-mail
              (<span className="font-medium">{user?.email}</span>).
            </p>

            <div className="mt-4 space-y-1">
              <label
                htmlFor={inputId}
                className="block text-sm font-medium text-slate-300"
              >
                Adres e-mail
              </label>
              <input
                id={inputId}
                type="email"
                value={confirmValue}
                onChange={(event) => setConfirmValue(event.target.value)}
                className="w-full rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>

            {error && (
              <p role="alert" className="mt-2 text-sm text-red-400">
                {error}
              </p>
            )}

            <div className="mt-5 flex gap-3">
              <button
                type="button"
                onClick={onConfirm}
                disabled={!canConfirm || isPending}
                className="flex-1 rounded bg-red-600 px-4 py-2 text-sm font-medium text-white enabled:hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isPending ? "Usuwanie…" : "Usuń konto trwale"}
              </button>
              <button
                type="button"
                onClick={closeDialog}
                disabled={isPending}
                className="flex-1 rounded border border-slate-500 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
