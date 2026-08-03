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
import { DeleteAccountSection } from "@/features/settings/components/delete-account-section";

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
    defaultValues: {
      expiryThresholdDays: 30,
      closeToFinishThresholdDays: 7,
      minPackageCount: 1,
    },
  });

  useEffect(() => {
    if (prefs) {
      reset({
        expiryThresholdDays: prefs.expiryThresholdDays,
        closeToFinishThresholdDays: prefs.closeToFinishThresholdDays,
        minPackageCount: prefs.minPackageCount,
      });
    }
  }, [prefs, reset]);

  function onSubmit(values: UpdatePreferencesFormValues) {
    setSuccessMessage(null);
    setServerError(null);
    mutate(
      {
        expiryThresholdDays: values.expiryThresholdDays,
        closeToFinishThresholdDays: values.closeToFinishThresholdDays,
        minPackageCount: values.minPackageCount,
      },
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
      <div className="-mx-6 -my-8 h-[calc(100%+4rem)] overflow-y-auto px-6 py-8">
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
            noValidate
            className="w-full max-w-sm space-y-6"
          >
            <div className="space-y-1">
              <label
                htmlFor="expiryThresholdDays"
                className="block text-sm font-medium text-slate-300"
              >
                Próg ważności (dni)
              </label>
              <p className="text-xs text-slate-400">
                Leki, którym kończy się ważność w ciągu tylu dni, zostaną
                oznaczone jako wygasające (7–90).
              </p>
              <input
                id="expiryThresholdDays"
                type="number"
                min={7}
                max={90}
                {...register("expiryThresholdDays", {
                  valueAsNumber: true,
                })}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.expiryThresholdDays && (
                <p className="text-xs text-red-400">
                  {errors.expiryThresholdDays.message}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label
                htmlFor="closeToFinishThresholdDays"
                className="block text-sm font-medium text-slate-300"
              >
                Próg kończącego się zapasu (dni)
              </label>
              <p className="text-xs text-slate-400">
                Leki, których zapas skończy się w ciągu tylu dni przed
                zakończeniem kuracji, zostaną oznaczone jako zagrożone (minimum
                1).
              </p>
              <input
                id="closeToFinishThresholdDays"
                type="number"
                min={1}
                {...register("closeToFinishThresholdDays", {
                  valueAsNumber: true,
                })}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.closeToFinishThresholdDays && (
                <p className="text-xs text-red-400">
                  {errors.closeToFinishThresholdDays.message}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label
                htmlFor="minPackageCount"
                className="block text-sm font-medium text-slate-300"
              >
                Minimalna liczba opakowań
              </label>
              <p className="text-xs text-slate-400">
                Ważne leki poniżej tego progu będą oznaczone jako brak w
                apteczce (1–10).
              </p>
              <input
                id="minPackageCount"
                type="number"
                min={1}
                max={10}
                {...register("minPackageCount", { valueAsNumber: true })}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {errors.minPackageCount && (
                <p className="text-xs text-red-400">
                  {errors.minPackageCount.message}
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
              className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {isPending ? "Zapisywanie…" : "Zapisz"}
            </button>
          </form>
        )}

        <DeleteAccountSection />
      </div>
    </AppLayout>
  );
}
