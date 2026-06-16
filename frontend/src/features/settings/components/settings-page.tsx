import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AppLayout } from "@/app/components/app-layout";
import {
  usePreferences,
  useUpdatePreferences,
} from "@/features/settings/api/settings-queries";
import {
  updatePreferencesSchema,
  type UpdatePreferencesFormValues,
} from "@/features/settings/schemas/settings-schemas";

export function SettingsPage() {
  const { data: prefs, isLoading, isError } = usePreferences();
  const { mutate, isPending } = useUpdatePreferences();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UpdatePreferencesFormValues>({
    resolver: zodResolver(updatePreferencesSchema),
    defaultValues: { min_package_count: 1 },
  });

  useEffect(() => {
    if (prefs) {
      reset({ min_package_count: prefs.min_package_count });
    }
  }, [prefs, reset]);

  function onSubmit(values: UpdatePreferencesFormValues) {
    setSuccessMessage(null);
    setServerError(null);
    mutate(
      { min_package_count: values.min_package_count },
      {
        onSuccess: () => {
          setSuccessMessage("Ustawienia zostały zapisane.");
        },
        onError: () => {
          setServerError("Wystąpił błąd podczas zapisywania ustawień.");
        },
      },
    );
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-white">Ustawienia</h2>
        </div>

        {isLoading && (
          <p className="text-sm text-slate-400">Ładowanie ustawień…</p>
        )}

        {isError && (
          <p className="text-sm text-red-400">
            Nie udało się załadować ustawień.
          </p>
        )}

        {!isLoading && !isError && (
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="max-w-sm space-y-6"
          >
            <div className="space-y-1">
              <label
                htmlFor="min_package_count"
                className="block text-sm font-medium text-slate-300"
              >
                Minimalna liczba opakowań
              </label>
              <p className="text-xs text-slate-400 whitespace-nowrap">
                Ważne leki poniżej tego progu będą oznaczone jako brak w
                apteczce (1–10).
              </p>
              <input
                id="min_package_count"
                type="number"
                min={1}
                max={10}
                {...register("min_package_count", { valueAsNumber: true })}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.min_package_count && (
                <p className="text-xs text-red-400">
                  {errors.min_package_count.message}
                </p>
              )}
            </div>

            {successMessage && (
              <p className="text-sm text-green-400">{successMessage}</p>
            )}
            {serverError && (
              <p className="text-sm text-red-400">{serverError}</p>
            )}

            <button
              type="submit"
              disabled={isPending}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isPending ? "Zapisywanie…" : "Zapisz"}
            </button>
          </form>
        )}
      </div>
    </AppLayout>
  );
}
