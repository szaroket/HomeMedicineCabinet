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

interface FilterGroupProps {
  label: string;
  options: { value: string; label: string }[];
  selected: string;
  onSelect: (value: string) => void;
}

// Tap-to-select rows instead of a native <select>: on mobile a native picker
// slides up over the bottom sheet and dismisses on selection, which reads as
// the sheet flickering closed/open. Plain buttons keep selection inside the
// sheet with no native overlay.
function FilterGroup({ label, options, selected, onSelect }: FilterGroupProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-slate-400">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isActive = option.value === selected;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onSelect(option.value)}
              aria-pressed={isActive}
              className={`rounded-full border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                isActive
                  ? "border-blue-500 bg-blue-600 text-white"
                  : "border-slate-600 bg-slate-900 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
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
              <FilterGroup
                label="Kategoria ważności (status)"
                options={STATUS_OPTIONS}
                selected={status ?? ""}
                onSelect={(value) => setParam("status", value || null, true)}
              />

              <FilterGroup
                label="Kategoria"
                options={CATEGORY_OPTIONS}
                selected={category ?? ""}
                onSelect={(value) => setParam("category", value || null, true)}
              />

              <FilterGroup
                label="Zapasy"
                options={STOCK_OPTIONS}
                selected={belowMinimum ? "low" : ""}
                onSelect={(value) =>
                  setParam(
                    "below_minimum",
                    value === "low" ? "true" : null,
                    true,
                  )
                }
              />

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
