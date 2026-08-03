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
      isUsed: entry.isUsed,
      isTabletBased: entry.isTabletBased,
      dosageTimes: entry.dosageTimes ?? null,
      dosagePeriod: entry.dosagePeriod ?? null,
      dosageAmount: entry.dosageAmount ?? null,
      dosageStartDate: entry.dosageStartDate ?? null,
      dosageEndDate: entry.dosageEndDate ?? null,
    },
  });

  // useWatch (not the watch() function) so React Compiler can memoize this
  // component instead of skipping it (react-hooks/incompatible-library).
  const isUsed = useWatch({ control, name: "isUsed" });

  function onSubmit(values: UsageValues) {
    const payload = values.isUsed
      ? {
          isUsed: true as const,
          dosageTimes: values.dosageTimes ?? null,
          dosagePeriod: values.dosagePeriod ?? null,
          dosageAmount: values.dosageAmount ?? null,
          dosageStartDate: values.dosageStartDate ?? null,
          dosageEndDate: values.dosageEndDate ?? null,
        }
      : { isUsed: false as const };
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
          id={`isUsed_${entry.id}`}
          type="checkbox"
          className="h-4 w-4 rounded border-slate-600 bg-slate-700 accent-blue-500"
          {...register("isUsed")}
        />
        <label
          htmlFor={`isUsed_${entry.id}`}
          className="cursor-pointer text-sm font-medium text-blue-400"
        >
          Oznacz jako przyjmowany
        </label>
      </div>

      {isUsed && (
        <>
          {entry.isTabletBased && (
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
                    {...register("dosageTimes", {
                      setValueAs: (value: string) =>
                        value === "" || value == null ? null : Number(value),
                    })}
                  />
                  {errors.dosageTimes && (
                    <p className="text-xs text-red-400">
                      {errors.dosageTimes.message}
                    </p>
                  )}
                </div>

                <div className="flex flex-1 flex-col gap-1">
                  <label className="text-sm font-medium text-blue-400">
                    Okres
                  </label>
                  <select
                    className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    {...register("dosagePeriod", {
                      setValueAs: (value: string) =>
                        value === "" ? null : value,
                    })}
                  >
                    <option value="">Wybierz…</option>
                    <option value="day">dzień</option>
                    <option value="week">tydzień</option>
                  </select>
                  {errors.dosagePeriod && (
                    <p className="text-xs text-red-400">
                      {errors.dosagePeriod.message}
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
                  {...register("dosageAmount", {
                    setValueAs: (value: string) =>
                      value === "" || value == null ? null : Number(value),
                  })}
                />
                {errors.dosageAmount && (
                  <p className="text-xs text-red-400">
                    {errors.dosageAmount.message}
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
                {...register("dosageStartDate")}
              />
              {errors.dosageStartDate && (
                <p className="text-xs text-red-400">
                  {errors.dosageStartDate.message}
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
                {...register("dosageEndDate")}
              />
              {errors.dosageEndDate && (
                <p className="text-xs text-red-400">
                  {errors.dosageEndDate.message}
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
