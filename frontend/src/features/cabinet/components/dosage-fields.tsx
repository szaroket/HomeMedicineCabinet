import type { UseFormRegister, FieldErrors } from "react-hook-form";
import type { AddEntryValues } from "@/features/cabinet/schemas/cabinet-schemas";

interface DosageFieldsProps {
  isTabletBased: boolean;
  isUsed: boolean;
  register: UseFormRegister<AddEntryValues>;
  errors: FieldErrors<AddEntryValues>;
}

export function DosageFields({
  isTabletBased,
  isUsed,
  register,
  errors,
}: DosageFieldsProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <input
          id="isUsed"
          type="checkbox"
          className="h-4 w-4 rounded border-slate-600 bg-slate-700 accent-blue-500"
          {...register("isUsed")}
        />
        <label
          htmlFor="isUsed"
          className="cursor-pointer text-sm font-medium text-blue-400"
        >
          Oznacz jako przyjmowany
        </label>
      </div>

      {isUsed && (
        <>
          {isTabletBased && (
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
    </div>
  );
}
