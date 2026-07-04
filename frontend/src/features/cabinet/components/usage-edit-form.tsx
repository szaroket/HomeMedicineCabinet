import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";
import { useSetUsage } from "@/features/cabinet/api/cabinet-queries";
import {
  usageSchema,
  type UsageValues,
} from "@/features/cabinet/schemas/cabinet-schemas";

interface UsageEditFormProps {
  entry: CabinetEntryOut;
  onClose: () => void;
}

export function UsageEditForm({ entry, onClose }: UsageEditFormProps) {
  const { mutate: setUsage, isPending } = useSetUsage();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<UsageValues>({
    resolver: zodResolver(usageSchema),
    defaultValues: {
      is_used: entry.is_used,
      is_tablet_based: entry.is_tablet_based,
      dosage_times: entry.dosage_times ?? null,
      dosage_period: entry.dosage_period ?? null,
      dosage_amount: entry.dosage_amount ?? null,
      dosage_start_date: entry.dosage_start_date ?? null,
      dosage_end_date: entry.dosage_end_date ?? null,
    },
  });

  // useWatch (not the watch() function) so React Compiler can memoize this
  // component instead of skipping it (react-hooks/incompatible-library).
  const isUsed = useWatch({ control, name: "is_used" });

  function onSubmit(values: UsageValues) {
    const payload = values.is_used
      ? {
          is_used: true as const,
          dosage_times: values.dosage_times ?? null,
          dosage_period: values.dosage_period ?? null,
          dosage_amount: values.dosage_amount ?? null,
          dosage_start_date: values.dosage_start_date ?? null,
          dosage_end_date: values.dosage_end_date ?? null,
        }
      : { is_used: false as const };
    setServerError(null);
    setUsage(
      { id: entry.id, payload },
      {
        onSuccess: onClose,
        onError: () =>
          setServerError("Wystąpił błąd. Sprawdź dane i spróbuj ponownie."),
      },
    );
  }

  return (
    <form
      onSubmit={(ev) => {
        ev.stopPropagation();
        void handleSubmit(onSubmit)(ev);
      }}
      onClick={(ev) => ev.stopPropagation()}
      className="mt-2 flex flex-col gap-3 rounded border border-slate-600 bg-slate-900/50 p-3"
    >
      <div className="flex items-center gap-2">
        <input
          id={`is_used_${entry.id}`}
          type="checkbox"
          className="h-4 w-4 rounded border-slate-600 bg-slate-700 accent-blue-500"
          {...register("is_used")}
        />
        <label
          htmlFor={`is_used_${entry.id}`}
          className="cursor-pointer text-sm font-medium text-blue-400"
        >
          Oznacz jako przyjmowany
        </label>
      </div>

      {isUsed && (
        <>
          {entry.is_tablet_based && (
            <>
              <div className="flex flex-col gap-2 sm:flex-row">
                <div className="flex flex-1 flex-col gap-1">
                  <label className="text-sm font-medium text-blue-400">
                    Ile razy
                  </label>
                  <input
                    type="number"
                    min={1}
                    placeholder="np. 3"
                    className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    {...register("dosage_times", {
                      setValueAs: (value: string) =>
                        value === "" || value == null ? null : Number(value),
                    })}
                  />
                  {errors.dosage_times && (
                    <p className="text-xs text-red-400">
                      {errors.dosage_times.message}
                    </p>
                  )}
                </div>

                <div className="flex flex-1 flex-col gap-1">
                  <label className="text-sm font-medium text-blue-400">
                    Okres
                  </label>
                  <select
                    className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    {...register("dosage_period", {
                      setValueAs: (value: string) =>
                        value === "" ? null : value,
                    })}
                  >
                    <option value="">Wybierz…</option>
                    <option value="day">dzień</option>
                    <option value="week">tydzień</option>
                  </select>
                  {errors.dosage_period && (
                    <p className="text-xs text-red-400">
                      {errors.dosage_period.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-blue-400">
                  Tabletek na raz
                </label>
                <input
                  type="number"
                  min={1}
                  placeholder="np. 2"
                  className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  {...register("dosage_amount", {
                    setValueAs: (value: string) =>
                      value === "" || value == null ? null : Number(value),
                  })}
                />
                {errors.dosage_amount && (
                  <p className="text-xs text-red-400">
                    {errors.dosage_amount.message}
                  </p>
                )}
              </div>
            </>
          )}

          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex flex-1 flex-col gap-1">
              <label className="text-sm font-medium text-blue-400">
                Data rozpoczęcia
              </label>
              <input
                type="date"
                className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                {...register("dosage_start_date")}
              />
              {errors.dosage_start_date && (
                <p className="text-xs text-red-400">
                  {errors.dosage_start_date.message}
                </p>
              )}
            </div>

            <div className="flex flex-1 flex-col gap-1">
              <label className="text-sm font-medium text-blue-400">
                Data zakończenia
              </label>
              <input
                type="date"
                className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                {...register("dosage_end_date")}
              />
              {errors.dosage_end_date && (
                <p className="text-xs text-red-400">
                  {errors.dosage_end_date.message}
                </p>
              )}
            </div>
          </div>
        </>
      )}

      {serverError && <p className="text-sm text-red-400">{serverError}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isPending}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        >
          {isPending ? "Zapisywanie…" : "Zapisz"}
        </button>
        <button
          type="button"
          onClick={(ev) => {
            ev.stopPropagation();
            onClose();
          }}
          className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
        >
          Anuluj
        </button>
      </div>
    </form>
  );
}
