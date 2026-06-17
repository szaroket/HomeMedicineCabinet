import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";
import {
  useCabinetEntry,
  OUT_OF_STOCK_LABEL,
} from "@/features/cabinet/hooks/use-cabinet-entry";
import { StatusBadge } from "@/features/cabinet/components/status-badge";
import {
  StarIcon,
  ChevronIcon,
} from "@/features/cabinet/components/entry-icons";

interface CabinetCardProps {
  entry: CabinetEntryOut;
}

export function CabinetCard({ entry }: CabinetCardProps) {
  const {
    expanded,
    toggleExpanded,
    toggleImportant,
    statusInfo,
    belowMinimum,
    formattedExpiryDate,
  } = useCabinetEntry(entry);

  return (
    <div
      className={`rounded border border-slate-700 p-3 cursor-pointer ${
        belowMinimum ? "bg-amber-950/40" : "bg-slate-800/30"
      }`}
      onClick={toggleExpanded}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-2 min-w-0">
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
          <span className="truncate font-medium text-white">{entry.name}</span>
        </span>
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
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <StatusBadge status={statusInfo} />
        {belowMinimum && (
          <span className="inline-flex items-center rounded-full bg-amber-950/60 px-2 py-0.5 text-xs font-medium text-amber-400">
            {OUT_OF_STOCK_LABEL}
          </span>
        )}
      </div>

      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-300">
        <div className="flex gap-1">
          <dt className="text-slate-400">Opak.:</dt>
          <dd>{entry.package_count}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-slate-400">Sztuki:</dt>
          <dd>{entry.total_tablets != null ? entry.total_tablets : "—"}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-slate-400">Ważność:</dt>
          <dd>{formattedExpiryDate}</dd>
        </div>
      </dl>

      {expanded && (
        <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-1 border-t border-slate-700 pt-3 text-sm">
          <div className="flex gap-2">
            <dt className="text-slate-400">Dawka:</dt>
            <dd className="text-white">{entry.strength ?? "—"}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-slate-400">Postać:</dt>
            <dd className="text-white">{entry.pharmaceutical_form ?? "—"}</dd>
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
      )}
    </div>
  );
}
