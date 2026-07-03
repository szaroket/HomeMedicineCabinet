import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";
import {
  useCabinetEntry,
  OUT_OF_STOCK_LABEL,
} from "@/features/cabinet/hooks/use-cabinet-entry";
import { StatusBadge } from "@/features/cabinet/components/status-badge";
import {
  StarIcon,
  ChevronIcon,
  TrashIcon,
} from "@/features/cabinet/components/entry-icons";
import { UsageEditForm } from "@/features/cabinet/components/usage-edit-form";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

interface CabinetCardProps {
  entry: CabinetEntryOut;
}

export function CabinetCard({ entry }: CabinetCardProps) {
  const {
    expanded,
    toggleExpanded,
    toggleImportant,
    showUsageEdit,
    setShowUsageEdit,
    statusInfo,
    sufficiencyInfo,
    belowMinimum,
    formattedExpiryDate,
    usageView,
    confirmingDelete,
    openDeleteConfirm,
    closeDeleteConfirm,
    confirmDelete,
    deletePending,
  } = useCabinetEntry(entry);
  const deleteMessage = `Czy na pewno chcesz usunąć „${entry.name}” z apteczki?`;
  const deleteNote = belowMinimum
    ? `Oznaczenie „${OUT_OF_STOCK_LABEL}” również zniknie.`
    : undefined;

  return (
    <div
      className={`rounded border border-slate-700 p-3 ${
        showUsageEdit ? "" : "cursor-pointer"
      } ${
        belowMinimum
          ? "bg-amber-950/40"
          : entry.is_sufficient === false
            ? "bg-red-950/40"
            : "bg-slate-800/30"
      }`}
      onClick={showUsageEdit ? undefined : toggleExpanded}
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
        <span className="inline-flex items-center gap-1 shrink-0">
          <button
            type="button"
            aria-label="Usuń lek"
            onClick={(ev) => {
              ev.stopPropagation();
              openDeleteConfirm();
            }}
            className="inline-flex items-center rounded text-slate-400 hover:text-red-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
          >
            <TrashIcon />
          </button>
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
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <StatusBadge status={statusInfo} />
        {belowMinimum && (
          <span className="inline-flex items-center rounded-full bg-amber-950/60 px-2 py-0.5 text-xs font-medium text-amber-400">
            {OUT_OF_STOCK_LABEL}
          </span>
        )}
        {sufficiencyInfo && <StatusBadge status={sufficiencyInfo} />}
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
          <div className="w-full pb-2 border-b border-slate-700 mb-1">
            {entry.is_used && (
              <div className="flex flex-col gap-1">
                {usageView.schedule && (
                  <div className="flex gap-2">
                    <dt className="text-slate-400">Dawkowanie:</dt>
                    <dd className="text-white">{usageView.schedule}</dd>
                  </div>
                )}
                {usageView.startDate && (
                  <div className="flex gap-2">
                    <dt className="text-slate-400">Od:</dt>
                    <dd className="text-white">{usageView.startDate}</dd>
                  </div>
                )}
                {usageView.endDate && (
                  <div className="flex gap-2">
                    <dt className="text-slate-400">Do:</dt>
                    <dd className="text-white">{usageView.endDate}</dd>
                  </div>
                )}
                {usageView.finishDate != null && (
                  <div className="flex gap-2">
                    <dt className="text-slate-400">Szacowany koniec:</dt>
                    <dd className="text-white">
                      {usageView.finishDate}
                      <span className="ml-1 text-xs text-slate-500">
                        (na podstawie bieżącego stanu)
                      </span>
                    </dd>
                  </div>
                )}
                {usageView.daysOfSupply != null &&
                  usageView.daysUntilEnd != null && (
                    <div className="flex gap-2">
                      <dt className="text-slate-400">Zapas / dni do końca:</dt>
                      <dd className="text-white">
                        {usageView.daysOfSupply} dni / {usageView.daysUntilEnd}{" "}
                        dni
                      </dd>
                    </div>
                  )}
              </div>
            )}
            <button
              type="button"
              onClick={(ev) => {
                ev.stopPropagation();
                setShowUsageEdit((prev) => !prev);
              }}
              className="mt-2 text-xs text-blue-400 hover:text-blue-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              {showUsageEdit
                ? "Ukryj formularz"
                : entry.is_used
                  ? "Zmień dawkowanie"
                  : "Ustaw dawkowanie"}
            </button>
            {showUsageEdit && (
              <UsageEditForm
                entry={entry}
                onClose={() => setShowUsageEdit(false)}
              />
            )}
          </div>
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
      <ConfirmDialog
        open={confirmingDelete}
        title="Usuń lek"
        message={deleteMessage}
        note={deleteNote}
        confirmLabel="Usuń"
        onConfirm={confirmDelete}
        onCancel={closeDeleteConfirm}
        destructive
        pending={deletePending}
      />
    </div>
  );
}
