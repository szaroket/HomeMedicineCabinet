import type {
  CabinetEntryOut,
  CabinetPageOut,
} from "@/features/cabinet/api/cabinet-api";
import {
  useCabinetEntry,
  OUT_OF_STOCK_LABEL,
} from "@/features/cabinet/hooks/use-cabinet-entry";
import {
  StarIcon,
  ChevronIcon,
} from "@/features/cabinet/components/entry-icons";
import { CabinetCard } from "@/features/cabinet/components/cabinet-card";

function EntryRow({ entry }: { entry: CabinetEntryOut }) {
  const {
    expanded,
    toggleExpanded,
    toggleImportant,
    statusInfo,
    belowMinimum,
    formattedExpiryDate,
  } = useCabinetEntry(entry);
  const rowBg = belowMinimum
    ? "bg-amber-950/40 hover:bg-amber-950/60"
    : "hover:bg-slate-800/50";

  return (
    <>
      <tr
        className={`border-b border-slate-700 last:border-0 cursor-pointer ${rowBg}`}
        onClick={toggleExpanded}
      >
        <td className="px-4 py-3">
          <span className="inline-flex items-center gap-1">
            <button
              type="button"
              aria-expanded={expanded}
              aria-label="Pokaż szczegóły"
              onClick={(ev) => {
                ev.stopPropagation();
                toggleExpanded();
              }}
              className="inline-flex items-center rounded text-slate-400 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              <ChevronIcon expanded={expanded} />
            </button>
            <button
              type="button"
              aria-label={
                entry.is_important ? "Usuń z ważnych" : "Oznacz jako ważny"
              }
              onClick={(ev) => {
                ev.stopPropagation();
                toggleImportant();
              }}
              className="inline-flex items-center rounded hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-yellow-400"
            >
              <StarIcon filled={entry.is_important} />
            </button>
            {entry.name}
          </span>
        </td>
        <td className="px-4 py-3">{entry.package_count}</td>
        <td className="px-4 py-3">
          {entry.total_tablets != null ? entry.total_tablets : "—"}
        </td>
        <td className="px-4 py-3">{formattedExpiryDate}</td>
        <td className={`px-4 py-3 font-medium ${statusInfo.className}`}>
          {statusInfo.label}
        </td>
        <td className="px-4 py-3 font-medium text-amber-400">
          {belowMinimum ? OUT_OF_STOCK_LABEL : ""}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-700 last:border-0 bg-slate-800/30">
          <td colSpan={6} className="px-6 py-3">
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
    <>
      <div className="hidden md:block overflow-x-auto rounded border border-slate-700">
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
              <th className="px-4 py-3 text-left font-medium text-blue-400">
                Zapasy
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

      <div className="md:hidden flex flex-col gap-3">
        {pageData.items.map((entry) => (
          <CabinetCard key={entry.id} entry={entry} />
        ))}
      </div>
    </>
  );
}
