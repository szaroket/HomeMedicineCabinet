import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CabinetList } from "@/features/cabinet/components/cabinet-list";
import { FilterSheet } from "@/features/cabinet/components/filter-sheet";
import { AppLayout } from "@/app/components/app-layout";
import { useCabinetEntries } from "@/features/cabinet/api/cabinet-queries";
import { useDebounce } from "@/hooks/use-debounce";
import type { CabinetListParams } from "@/features/cabinet/api/cabinet-api";
import {
  STATUS_OPTIONS,
  CATEGORY_OPTIONS,
  STOCK_OPTIONS,
  type StatusFilter,
  type CategoryFilter,
  type StockFilter,
} from "@/features/cabinet/components/filter-options";

type OrderDir = "asc" | "desc";
type PageSize = 20 | 50 | 100;

const PAGE_SIZE_OPTIONS: PageSize[] = [20, 50, 100];

// Minimum characters before a search is sent to the API (mirrors the backend
// tsquery threshold). Shorter input is treated as no search at all.
const MIN_SEARCH_LEN = 2;

function parsePageSize(raw: string | null): PageSize {
  const num = Number(raw);
  if (num === 50 || num === 100) return num;
  return 20;
}

function parsePage(raw: string | null): number {
  const num = Math.floor(Number(raw));
  return Number.isFinite(num) && num >= 1 ? num : 1;
}

function parseOrder(raw: string | null): OrderDir {
  return raw === "desc" ? "desc" : "asc";
}

function parseStatus(raw: string | null): StatusFilter | undefined {
  if (raw === "valid" || raw === "expiring" || raw === "expired") return raw;
  return undefined;
}

function parseCategory(raw: string | null): CategoryFilter | undefined {
  if (raw === "important" || raw === "used") return raw;
  return undefined;
}

export function CabinetPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawSearch = searchParams.get("search") ?? "";
  const status = parseStatus(searchParams.get("status"));
  const category = parseCategory(searchParams.get("category"));
  const belowMinimum = searchParams.get("below_minimum") === "true";
  const sufficiency = searchParams.get("sufficiency") as
    "insufficient" | "sufficient" | null;
  const stockFilter: StockFilter | "" = belowMinimum
    ? "low"
    : sufficiency === "insufficient"
      ? "insufficient"
      : sufficiency === "sufficient"
        ? "sufficient"
        : "";
  const order = parseOrder(searchParams.get("order"));
  const page = parsePage(searchParams.get("page"));
  const pageSize = parsePageSize(searchParams.get("page_size"));

  const [searchInput, setSearchInput] = useState(rawSearch);
  const debouncedSearch = useDebounce(searchInput, 400);

  // When the URL's search changes externally (Back/Forward, cleared filters),
  // reflect it into the input. Adjusting state during render is React's
  // recommended pattern over calling setState inside an effect.
  const [prevRawSearch, setPrevRawSearch] = useState(rawSearch);
  if (rawSearch !== prevRawSearch) {
    setPrevRawSearch(rawSearch);
    setSearchInput(rawSearch);
  }

  // Only searches of at least MIN_SEARCH_LEN characters are sent to the API, so
  // shorter input must not leak into the URL either — otherwise the URL would
  // advertise a search the query ignores.
  const effectiveSearch =
    debouncedSearch.length >= MIN_SEARCH_LEN ? debouncedSearch : "";

  // Reflect the effective search into the URL. Uses replace so a single typed
  // word doesn't push one history entry per keystroke, and resets pagination
  // whenever the query changes.
  useEffect(() => {
    if (effectiveSearch === rawSearch) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (effectiveSearch === "") {
          next.delete("search");
        } else {
          next.set("search", effectiveSearch);
        }
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  }, [effectiveSearch, rawSearch, setSearchParams]);

  const hasFilters =
    !!status ||
    !!category ||
    belowMinimum ||
    !!sufficiency ||
    effectiveSearch !== "";

  const params: CabinetListParams = {
    order,
    page,
    page_size: pageSize,
    ...(status ? { status } : {}),
    ...(category ? { category } : {}),
    ...(belowMinimum ? { below_minimum: true } : {}),
    ...(sufficiency ? { sufficiency } : {}),
    ...(effectiveSearch !== "" ? { search: effectiveSearch } : {}),
  };

  const { data: pageData, isLoading, isError } = useCabinetEntries(params);

  function setParam(key: string, value: string | null, resetPage = false) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value == null || value === "") {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      if (resetPage) next.delete("page");
      return next;
    });
  }

  function setStockFilter(value: StockFilter | "") {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("below_minimum");
      next.delete("sufficiency");
      next.delete("page");
      if (value === "low") next.set("below_minimum", "true");
      if (value === "insufficient" || value === "sufficient")
        next.set("sufficiency", value);
      return next;
    });
  }

  function clearFilters() {
    setSearchInput("");
    // Clear only the filters (status/search) and reset pagination; sort order
    // and page size are display preferences, not filters, so they are kept.
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("status");
        next.delete("category");
        next.delete("below_minimum");
        next.delete("sufficiency");
        next.delete("search");
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  const totalPages = pageData
    ? Math.max(1, Math.ceil(pageData.total / pageData.page_size))
    : 1;

  // Guard against an out-of-range page (e.g. ?page=999, or a page that no longer
  // exists after filtering): once the real total is known, redirect to the last
  // valid page so the list never renders headers over an empty body.
  useEffect(() => {
    if (!pageData || page <= totalPages) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (totalPages <= 1) {
          next.delete("page");
        } else {
          next.set("page", String(totalPages));
        }
        return next;
      },
      { replace: true },
    );
  }, [pageData, page, totalPages, setSearchParams]);

  return (
    <AppLayout>
      <div className="flex h-full flex-col min-h-0">
        {/* Title + add button */}
        <div className="mb-4 flex flex-shrink-0 items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Lista leków</h2>
          <Link
            to="/cabinet/add"
            className="inline-flex rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Dodaj lek
          </Link>
        </div>

        {/* Mobile controls */}
        <div className="mb-4 flex flex-shrink-0 items-center gap-2 md:hidden">
          <input
            type="search"
            placeholder="Szukaj po nazwie lub składniku…"
            value={searchInput}
            onChange={(ev) => {
              setSearchInput(ev.target.value);
            }}
            className="min-w-0 flex-1 rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <FilterSheet
            status={status}
            category={category}
            stockFilter={stockFilter}
            setParam={setParam}
            setStockFilter={setStockFilter}
            clearFilters={clearFilters}
            hasFilters={hasFilters}
          />
          <button
            type="button"
            onClick={() =>
              setParam("order", order === "asc" ? "desc" : "asc", true)
            }
            className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Sortowanie {order === "asc" ? "A→Z" : "Z→A"}
          </button>
        </div>

        {/* Desktop controls */}
        <div className="mb-4 hidden flex-shrink-0 flex-wrap gap-3 items-end md:flex">
          <div className="flex flex-col gap-1 min-w-[220px] flex-1">
            <label className="text-xs text-slate-400">Szukaj</label>
            <input
              type="search"
              placeholder="Szukaj po nazwie lub składniku…"
              value={searchInput}
              onChange={(ev) => {
                setSearchInput(ev.target.value);
              }}
              className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">
              Kategoria ważności (status)
            </label>
            <select
              value={status ?? ""}
              onChange={(ev) => {
                setParam("status", ev.target.value || null, true);
              }}
              className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              value={stockFilter}
              onChange={(ev) =>
                setStockFilter(ev.target.value as StockFilter | "")
              }
              className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            onClick={() =>
              setParam("order", order === "asc" ? "desc" : "asc", true)
            }
            className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Nazwa {order === "asc" ? "A→Z" : "Z→A"}
          </button>

          <button
            type="button"
            onClick={clearFilters}
            disabled={!hasFilters}
            className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Wyczyść filtry
          </button>
        </div>

        {/* Scrollable table */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <CabinetList
            pageData={pageData}
            isLoading={isLoading}
            isError={isError}
            hasFilters={hasFilters}
            onClearFilters={clearFilters}
          />
        </div>

        {/* Mobile compact pagination */}
        {pageData && pageData.total > 0 && (
          <div className="mt-2 flex flex-shrink-0 items-center justify-center gap-3 text-sm text-slate-400 md:hidden">
            <button
              type="button"
              aria-label="Poprzednia strona"
              disabled={page <= 1}
              onClick={() => setParam("page", String(page - 1))}
              className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              ‹
            </button>
            <span>
              {page} / {totalPages} · Leków: {pageData.total}
            </span>
            <button
              type="button"
              aria-label="Następna strona"
              disabled={page >= totalPages}
              onClick={() => setParam("page", String(page + 1))}
              className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              ›
            </button>
          </div>
        )}

        {/* Desktop pagination */}
        {pageData && pageData.total > 0 && (
          <div className="mt-4 hidden flex-shrink-0 items-center justify-between text-sm text-slate-400 md:flex">
            <span>
              Strona {pageData.page} z {totalPages} (łącznie {pageData.total})
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setParam("page", String(page - 1))}
                className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                ← Poprzednia
              </button>
              <select
                value={pageSize}
                onChange={(ev) => {
                  setParam("page_size", ev.target.value, true);
                }}
                className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size} / strona
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setParam("page", String(page + 1))}
                className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-white disabled:opacity-40 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Następna →
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
