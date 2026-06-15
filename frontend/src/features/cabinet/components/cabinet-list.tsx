import { useState } from "react";
import type {
  CabinetEntryOut,
  CabinetPageOut,
} from "@/features/cabinet/api/cabinet-api";

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4 shrink-0 text-slate-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      {expanded ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      )}
    </svg>
  );
}

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  valid: { label: "Ważny", className: "text-green-400" },
  expiring: { label: "Bliski termin", className: "text-orange-400" },
  expired: { label: "Przeterminowany", className: "text-red-400" },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function EntryRow({ entry }: { entry: CabinetEntryOut }) {
  const [expanded, setExpanded] = useState(false);
  const statusInfo = STATUS_LABEL[entry.status] ?? {
    label: entry.status,
    className: "text-slate-400",
  };

  return (
    <>
      <tr
        className="border-b border-slate-700 last:border-0 hover:bg-slate-800/50 cursor-pointer"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <td className="px-4 py-3">
          <span className="inline-flex items-center gap-1">
            <button
              type="button"
              aria-expanded={expanded}
              aria-label="Pokaż szczegóły"
              onClick={(ev) => {
                ev.stopPropagation();
                setExpanded((prev) => !prev);
              }}
              className="inline-flex items-center rounded text-slate-400 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              <ChevronIcon expanded={expanded} />
            </button>
            {entry.name}
          </span>
        </td>
        <td className="px-4 py-3">{entry.package_count}</td>
        <td className="px-4 py-3">
          {entry.total_tablets != null ? entry.total_tablets : "—"}
        </td>
        <td className="px-4 py-3">{formatDate(entry.expiry_date)}</td>
        <td className={`px-4 py-3 font-medium ${statusInfo.className}`}>
          {statusInfo.label}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-700 last:border-0 bg-slate-800/30">
          <td colSpan={5} className="px-6 py-3">
            <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="text-slate-400">Dawka:</dt>
                <dd className="text-white">{entry.strength ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Postać:</dt>
                <dd className="text-white">
                  {entry.pharmaceutical_form ?? "—"}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Substancja czynna:</dt>
                <dd className="text-white">{entry.active_ingredient ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Droga podania:</dt>
                <dd className="text-white">
                  {entry.route_of_administration ?? "—"}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Ulotka:</dt>
                <dd>
                  {entry.leaflet_url ? (
                    <a
                      href={entry.leaflet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      Otwórz
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Charakterystyka:</dt>
                <dd>
                  {entry.specification_url ? (
                    <a
                      href={entry.specification_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      Otwórz
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}

interface CabinetListProps {
  pageData: CabinetPageOut | undefined;
  isLoading: boolean;
  isError: boolean;
  hasFilters: boolean;
  onClearFilters: () => void;
}

export function CabinetList({
  pageData,
  isLoading,
  isError,
  hasFilters,
  onClearFilters,
}: CabinetListProps) {
  if (isLoading) {
    return <p className="text-sm text-slate-400">Ładowanie…</p>;
  }

  if (isError) {
    return <p className="text-sm text-red-400">Błąd ładowania danych.</p>;
  }

  if (!pageData || pageData.total === 0) {
    if (hasFilters) {
      return (
        <div className="text-sm text-slate-400">
          <p>Brak leków spełniających kryteria.</p>
          <button
            type="button"
            onClick={onClearFilters}
            className="mt-2 text-blue-400 hover:underline focus:outline-none"
          >
            Wyczyść filtry
          </button>
        </div>
      );
    }
    return (
      <p className="text-sm text-slate-400">
        Apteczka jest pusta. Dodaj pierwszy lek.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-slate-700">
      <table className="w-full text-sm text-white">
        <thead className="border-b border-slate-700 bg-slate-800">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Nazwa
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Opak.
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Sztuki
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Ważność
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {pageData.items.map((entry) => (
            <EntryRow key={entry.id} entry={entry} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
