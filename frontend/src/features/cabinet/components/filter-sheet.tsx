import { useState } from "react";
import {
  STATUS_OPTIONS,
  CATEGORY_OPTIONS,
  STOCK_OPTIONS,
  type StatusFilter,
  type CategoryFilter,
} from "@/features/cabinet/components/filter-options";

interface FilterSheetProps {
  status: StatusFilter | undefined;
  category: CategoryFilter | undefined;
  belowMinimum: boolean;
  setParam: (key: string, value: string | null, resetPage?: boolean) => void;
  clearFilters: () => void;
  hasFilters: boolean;
}

export function FilterSheet({
  status,
  category,
  belowMinimum,
  setParam,
  clearFilters,
  hasFilters,
}: FilterSheetProps) {
  const [isOpen, setIsOpen] = useState(false);

  const activeCount =
    (status ? 1 : 0) + (category ? 1 : 0) + (belowMinimum ? 1 : 0);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="relative rounded border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        Filtry
        {activeCount > 0 && (
          <span className="ml-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-600 px-1 text-xs font-medium text-white">
            {activeCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute bottom-0 left-0 right-0 rounded-t-xl bg-slate-800 p-4 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Filtry</h3>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Zamknij"
                className="text-slate-400 hover:text-white focus:outline-none"
              >
                ✕
              </button>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-400">
                  Kategoria ważności (status)
                </label>
                <select
                  value={status ?? ""}
                  onChange={(ev) => {
                    setParam("status", ev.target.value || null, true);
                  }}
                  className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-400">Kategoria</label>
                <select
                  value={category ?? ""}
                  onChange={(ev) => {
                    setParam("category", ev.target.value || null, true);
                  }}
                  className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-400">Zapasy</label>
                <select
                  value={belowMinimum ? "low" : ""}
                  onChange={(ev) => {
                    setParam(
                      "below_minimum",
                      ev.target.value === "low" ? "true" : null,
                      true,
                    );
                  }}
                  className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {STOCK_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={clearFilters}
                disabled={!hasFilters}
                className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Wyczyść filtry
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
