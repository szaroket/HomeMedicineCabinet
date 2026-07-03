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
  TrashIcon,
} from "@/features/cabinet/components/entry-icons";
import { StatusBadge } from "@/features/cabinet/components/status-badge";
import { CabinetCard } from "@/features/cabinet/components/cabinet-card";
import { UsageEditForm } from "@/features/cabinet/components/usage-edit-form";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

function EntryRow({ entry }: { entry: CabinetEntryOut }) {
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
    deleteMessage,
    deleteNote,
    incrementPackage,
    decrementPackage,
    mutationPending,
    editingPartial,
    openPartialEdit,
    closePartialEdit,
    savePartialTablet,
    partialError,
  } = useCabinetEntry(entry);
  const rowBg = belowMinimum
    ? "bg-amber-950/40 hover:bg-amber-950/60"
    : entry.is_sufficient === false
      ? "bg-red-950/40 hover:bg-red-950/60"
      : "hover:bg-slate-800/50";

  return (
    <>
      <tr
        className={`border-b border-slate-700 last:border-0 ${showUsageEdit ? "" : "cursor-pointer"} ${rowBg}`}
        onClick={showUsageEdit ? undefined : toggleExpanded}
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
        <td className="px-4 py-3">
          <span className="inline-flex items-center gap-1">
            <button
              type="button"
              aria-label="Zmniejsz liczbę opakowań"
              disabled={mutationPending || entry.package_count <= 0}
              onClick={(ev) => {
                ev.stopPropagation();
                decrementPackage();
              }}
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-slate-600 text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              −
            </button>
            <span className="w-6 text-center">{entry.package_count}</span>
            <button
              type="button"
              aria-label="Zwiększ liczbę opakowań"
              disabled={mutationPending}
              onClick={(ev) => {
                ev.stopPropagation();
                incrementPackage();
              }}
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-slate-600 text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
            >
              +
            </button>
          </span>
          {entry.is_tablet_based && (
            <div className="mt-1" onClick={(ev) => ev.stopPropagation()}>
              {editingPartial ? (
                <form
                  onSubmit={(ev) => {
                    ev.preventDefault();
                    const input = ev.currentTarget.elements.namedItem(
                      "partial",
                    ) as HTMLInputElement;
                    savePartialTablet(input.value);
                  }}
                  className="flex items-center gap-1"
                >
                  <input
                    name="partial"
                    aria-label="Liczba luźnych tabletek"
                    type="number"
                    min={1}
                    defaultValue={entry.partial_tablet_count ?? ""}
                    placeholder="Pełne opak."
                    className="w-20 rounded border border-slate-600 bg-slate-700 px-1 py-0.5 text-xs text-white"
                  />
                  <button
                    type="submit"
                    disabled={mutationPending}
                    className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
                  >
                    Zapisz
                  </button>
                  <button
                    type="button"
                    onClick={closePartialEdit}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    Anuluj
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={openPartialEdit}
                  className="text-xs text-blue-400 hover:text-blue-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  {entry.partial_tablet_count != null
                    ? `Luźne: ${entry.partial_tablet_count} szt.`
                    : "Ustaw luźne tabletki"}
                </button>
              )}
              {partialError && (
                <p className="mt-0.5 text-xs text-red-400">{partialError}</p>
              )}
            </div>
          )}
        </td>
        <td className="px-4 py-3">
          {entry.total_tablets != null ? entry.total_tablets : "—"}
        </td>
        <td className="px-4 py-3">{formattedExpiryDate}</td>
        <td className="px-4 py-3">
          <StatusBadge status={statusInfo} />
        </td>
        <td className="px-4 py-3">
          <span className="inline-flex flex-wrap gap-1">
            {belowMinimum && (
              <span className="inline-flex items-center rounded-full bg-amber-950/60 px-2 py-0.5 text-xs font-medium text-amber-400">
                {OUT_OF_STOCK_LABEL}
              </span>
            )}
            {sufficiencyInfo && <StatusBadge status={sufficiencyInfo} />}
          </span>
        </td>
        <td className="px-4 py-3">
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
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-700 last:border-0 bg-slate-800/30">
          <td colSpan={7} className="px-6 py-3">
            <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
              <div className="w-full pb-2 mb-2 border-b border-slate-700">
                {entry.is_used && (
                  <div className="flex flex-wrap gap-x-8 gap-y-1 mb-2">
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
                          <dt className="text-slate-400">
                            Zapas / dni do końca:
                          </dt>
                          <dd className="text-white">
                            {usageView.daysOfSupply} dni /{" "}
                            {usageView.daysUntilEnd} dni
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
                  className="text-xs text-blue-400 hover:text-blue-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
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
              <th className="px-4 py-3 text-left font-medium text-blue-400">
                <span className="sr-only">Akcje</span>
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
