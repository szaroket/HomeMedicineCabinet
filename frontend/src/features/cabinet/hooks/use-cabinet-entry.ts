import { useState } from "react";
import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";
import {
  useToggleImportant,
  useDeleteEntry,
  useUpdateQuantity,
} from "@/features/cabinet/api/cabinet-queries";

export const OUT_OF_STOCK_LABEL = "Brak w apteczce";

export const STATUS_LABEL: Record<
  string,
  { label: string; className: string; pillClassName: string }
> = {
  valid: {
    label: "Aktualny",
    className: "text-green-400",
    pillClassName: "bg-green-950/60 text-green-400",
  },
  expiring: {
    label: "Bliski termin",
    className: "text-orange-400",
    pillClassName: "bg-orange-950/60 text-orange-400",
  },
  expired: {
    label: "Przeterminowany",
    className: "text-red-400",
    pillClassName: "bg-red-950/60 text-red-400",
  },
};

export const SUFFICIENCY_LABEL: Record<
  "insufficient" | "sufficient",
  { label: string; pillClassName: string }
> = {
  insufficient: {
    label: "Zabraknie",
    pillClassName: "bg-red-950/60 text-red-400",
  },
  sufficient: {
    label: "Wystarczy",
    pillClassName: "bg-green-950/60 text-green-400",
  },
};

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function computeFinishDate(
  startDateStr: string,
  daysOfSupply: number,
): string {
  const start = new Date(startDateStr + "T00:00:00");
  start.setDate(start.getDate() + daysOfSupply - 1);
  return start.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export interface UsageView {
  finishDate: string | null;
  daysOfSupply: number | null;
  daysUntilEnd: number | null;
  isSufficient: boolean | null;
  schedule: string | null;
  startDate: string | null;
  endDate: string | null;
}

function buildUsageView(entry: CabinetEntryOut): UsageView {
  if (!entry.is_used) {
    return {
      finishDate: null,
      daysOfSupply: null,
      daysUntilEnd: null,
      isSufficient: null,
      schedule: null,
      startDate: null,
      endDate: null,
    };
  }

  const startDate = entry.dosage_start_date
    ? formatDate(entry.dosage_start_date)
    : null;
  const endDate = entry.dosage_end_date
    ? formatDate(entry.dosage_end_date)
    : null;

  if (!entry.is_tablet_based) {
    return {
      finishDate: null,
      daysOfSupply: null,
      daysUntilEnd: null,
      isSufficient: null,
      schedule: null,
      startDate,
      endDate,
    };
  }

  const periodLabel = entry.dosage_period === "week" ? "tydzień" : "dzień";
  const schedule =
    entry.dosage_times != null && entry.dosage_amount != null
      ? `${entry.dosage_times} × ${entry.dosage_amount} tabl. / ${periodLabel}`
      : null;

  const finishDate =
    entry.days_of_supply != null &&
    entry.dosage_end_date == null &&
    entry.dosage_start_date != null
      ? computeFinishDate(entry.dosage_start_date, entry.days_of_supply)
      : null;

  return {
    finishDate,
    daysOfSupply: entry.days_of_supply,
    daysUntilEnd: entry.days_until_end,
    isSufficient: entry.is_sufficient,
    schedule,
    startDate,
    endDate,
  };
}

export function useCabinetEntry(entry: CabinetEntryOut) {
  const [expanded, setExpanded] = useState(false);
  const [showUsageEdit, setShowUsageEdit] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteReason, setDeleteReason] = useState<"trash" | "zero">("trash");
  const [editingPartial, setEditingPartial] = useState(false);
  const [partialError, setPartialError] = useState<string | null>(null);
  const { mutate: toggleImportant } = useToggleImportant();
  const { mutate: deleteEntry, isPending: deletePending } = useDeleteEntry();
  const { mutate: updateQuantity, isPending: quantityPending } =
    useUpdateQuantity();
  const mutationPending = deletePending || quantityPending;

  const statusInfo = STATUS_LABEL[entry.status] ?? {
    label: entry.status,
    className: "text-slate-400",
    pillClassName: "bg-slate-800 text-slate-400",
  };

  const sufficiencyInfo =
    entry.is_sufficient === false
      ? SUFFICIENCY_LABEL.insufficient
      : entry.is_sufficient === true
        ? SUFFICIENCY_LABEL.sufficient
        : null;

  function toggleExpanded() {
    setExpanded((prev) => !prev);
  }

  function toggleImportantFlag() {
    toggleImportant({ id: entry.id, is_important: !entry.is_important });
  }

  function openDeleteConfirm() {
    setDeleteReason("trash");
    setConfirmingDelete(true);
  }

  function closeDeleteConfirm() {
    setConfirmingDelete(false);
  }

  function confirmDelete() {
    deleteEntry(
      { id: entry.id },
      { onSuccess: () => setConfirmingDelete(false) },
    );
  }

  const isZeroDeleteCategory = !entry.is_important && !entry.is_used;

  function incrementPackage() {
    if (mutationPending) return;
    updateQuantity({
      id: entry.id,
      payload: {
        package_count: entry.package_count + 1,
        partial_tablet_count: entry.partial_tablet_count,
      },
    });
  }

  function decrementPackage() {
    if (mutationPending || entry.package_count <= 0) return;
    const nextCount = entry.package_count - 1;
    if (nextCount === 0 && entry.package_count === 1 && isZeroDeleteCategory) {
      setDeleteReason("zero");
      setConfirmingDelete(true);
      return;
    }
    updateQuantity({
      id: entry.id,
      payload: {
        package_count: nextCount,
        partial_tablet_count: entry.partial_tablet_count,
      },
    });
  }

  function openPartialEdit() {
    setPartialError(null);
    setEditingPartial(true);
  }

  function closePartialEdit() {
    setEditingPartial(false);
    setPartialError(null);
  }

  function savePartialTablet(rawValue: string) {
    if (mutationPending) return;
    if (rawValue.trim() === "") {
      updateQuantity(
        {
          id: entry.id,
          payload: {
            package_count: entry.package_count,
            partial_tablet_count: null,
          },
        },
        { onSuccess: closePartialEdit },
      );
      return;
    }
    const parsed = Number(rawValue);
    const capacity = entry.capacity ?? 0;
    if (!Number.isInteger(parsed) || parsed < 1 || parsed >= capacity) {
      setPartialError(`Podaj liczbę od 1 do ${Math.max(capacity - 1, 1)}`);
      return;
    }
    updateQuantity(
      {
        id: entry.id,
        payload: {
          package_count: entry.package_count,
          partial_tablet_count: parsed,
        },
      },
      { onSuccess: closePartialEdit },
    );
  }

  const deleteMessage =
    deleteReason === "zero"
      ? `Zmniejszenie liczby opakowań do zera usunie „${entry.name}” z apteczki. Kontynuować?`
      : `Czy na pewno chcesz usunąć „${entry.name}” z apteczki?`;
  const deleteNote =
    deleteReason === "zero"
      ? entry.partial_tablet_count != null && entry.partial_tablet_count > 0
        ? "Luźne tabletki z otwartego opakowania również zostaną usunięte."
        : undefined
      : entry.below_minimum
        ? `Oznaczenie „${OUT_OF_STOCK_LABEL}” również zniknie.`
        : undefined;

  return {
    expanded,
    toggleExpanded,
    toggleImportant: toggleImportantFlag,
    showUsageEdit,
    setShowUsageEdit,
    statusInfo,
    sufficiencyInfo,
    belowMinimum: entry.below_minimum,
    formattedExpiryDate: formatDate(entry.expiry_date),
    usageView: buildUsageView(entry),
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
  };
}
