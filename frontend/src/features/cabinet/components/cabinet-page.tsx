import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CabinetList } from "@/features/cabinet/components/cabinet-list";
import { LogoutButton } from "@/features/auth/components/logout-button";
import { AppHeader } from "@/app/components/app-header";
import { AppFooter } from "@/app/components/app-footer";
import { useCabinetEntries } from "@/features/cabinet/api/cabinet-queries";
import { useDebounce } from "@/hooks/use-debounce";
import type { CabinetListParams } from "@/features/cabinet/api/cabinet-api";

type StatusFilter = "valid" | "expiring" | "expired";
type OrderDir = "asc" | "desc";
type PageSize = 20 | 50 | 100;

const STATUS_OPTIONS: { value: StatusFilter | ""; label: string }[] = [
  { value: "", label: "Wszystkie" },
  { value: "valid", label: "Ważny" },
  { value: "expiring", label: "Bliski termin" },
  { value: "expired", label: "Przeterminowany" },
];

const PAGE_SIZE_OPTIONS: PageSize[] = [20, 50, 100];

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

export function CabinetPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawSearch = searchParams.get("search") ?? "";
  const status = parseStatus(searchParams.get("status"));
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

  // Reflect the debounced search into the URL. Uses replace so a single typed
  // word doesn't push one history entry per keystroke, and resets pagination
  // whenever the query changes.
  useEffect(() => {
    if (debouncedSearch === rawSearch) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (debouncedSearch === "") {
          next.delete("search");
        } else {
          next.set("search", debouncedSearch);
        }
        next.delete("page");
        return next;
      },
      { replace: true },
    );
  }, [debouncedSearch, rawSearch, setSearchParams]);

  const hasFilters = !!status || debouncedSearch.length >= 2;

  const params: CabinetListParams = {
    order,
    page,
    page_size: pageSize,
    ...(status ? { status } : {}),
    ...(debouncedSearch.length >= 2 ? { search: debouncedSearch } : {}),
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

  function clearFilters() {
    setSearchInput("");
    setSearchParams({});
  }

  const totalPages = pageData
    ? Math.ceil(pageData.total / pageData.page_size)
    : 1;

  return (
    <div className="flex min-h-screen flex-col bg-slate-900">
      <header className="border-b border-slate-700 bg-slate-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <AppHeader />
          <LogoutButton />
        </div>
      </header>

      <main className="grow px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Lista leków</h2>
          <Link
            to="/cabinet/add"
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Dodaj lek
          </Link>
        </div>

        {/* Controls */}
        <div className="mb-4 flex flex-wrap gap-3">
          {/* Search */}
          <input
            type="search"
            placeholder="Szukaj po nazwie lub składniku…"
            value={searchInput}
            onChange={(ev) => {
              setSearchInput(ev.target.value);
            }}
            className="rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-[220px] flex-1"
          />

          {/* Status filter */}
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

          {/* Sort order toggle */}
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

        <CabinetList
          pageData={pageData}
          isLoading={isLoading}
          isError={isError}
          hasFilters={hasFilters}
          onClearFilters={clearFilters}
        />

        {/* Pagination */}
        {pageData && pageData.total > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
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
      </main>
      <AppFooter />
    </div>
  );
}
