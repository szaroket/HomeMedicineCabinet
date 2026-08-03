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
  if (!entry.isUsed) {
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

  const startDate = entry.dosageStartDate
    ? formatDate(entry.dosageStartDate)
    : null;
  const endDate = entry.dosageEndDate ? formatDate(entry.dosageEndDate) : null;

  if (!entry.isTabletBased) {
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

  const periodLabel = entry.dosagePeriod === "week" ? "tydzień" : "dzień";
  const schedule =
    entry.dosageTimes != null && entry.dosageAmount != null
      ? `${entry.dosageTimes} × ${entry.dosageAmount} tabl. / ${periodLabel}`
      : null;

  const finishDate =
    entry.daysOfSupply != null &&
    entry.dosageEndDate == null &&
    entry.dosageStartDate != null
      ? computeFinishDate(entry.dosageStartDate, entry.daysOfSupply)
      : null;

  return {
    finishDate,
    daysOfSupply: entry.daysOfSupply,
    daysUntilEnd: entry.daysUntilEnd,
    isSufficient: entry.isSufficient,
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
  const [deleteError, setDeleteError] = useState<string | null>(null);
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
    entry.isSufficient === false
      ? SUFFICIENCY_LABEL.insufficient
      : entry.isSufficient === true
        ? SUFFICIENCY_LABEL.sufficient
        : null;

  function toggleExpanded() {
    setExpanded((prev) => !prev);
  }

  function toggleImportantFlag() {
    toggleImportant({ id: entry.id, isImportant: !entry.isImportant });
  }

  function openDeleteConfirm() {
    setDeleteError(null);
    setDeleteReason("trash");
    setConfirmingDelete(true);
  }

  function closeDeleteConfirm() {
    setConfirmingDelete(false);
    setDeleteError(null);
  }

  function confirmDelete() {
    setDeleteError(null);
    deleteEntry(
      { id: entry.id },
      {
        onSuccess: () => setConfirmingDelete(false),
        onError: () =>
          setDeleteError("Nie udało się usunąć leku. Spróbuj ponownie."),
      },
    );
  }

  const isZeroDeleteCategory = !entry.isImportant && !entry.isUsed;

  function incrementPackage() {
    if (mutationPending) return;
    updateQuantity({
      id: entry.id,
      payload: {
        packageCount: entry.packageCount + 1,
        partialTabletCount: entry.partialTabletCount,
      },
    });
  }

  function decrementPackage() {
    if (mutationPending || entry.packageCount <= 0) return;
    const nextCount = entry.packageCount - 1;
    if (nextCount === 0 && entry.packageCount === 1 && isZeroDeleteCategory) {
      setDeleteError(null);
      setDeleteReason("zero");
      setConfirmingDelete(true);
      return;
    }
    updateQuantity({
      id: entry.id,
      payload: {
        packageCount: nextCount,
        partialTabletCount: entry.partialTabletCount,
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
            packageCount: entry.packageCount,
            partialTabletCount: null,
          },
        },
        { onSuccess: closePartialEdit },
      );
      return;
    }
    const parsed = Number(rawValue);
    const capacity = entry.capacity;
    if (capacity == null) {
      setPartialError("Nie można zapisać luźnych tabletek dla tego leku.");
      return;
    }
    if (!Number.isInteger(parsed) || parsed < 1 || parsed >= capacity) {
      setPartialError(`Podaj liczbę od 1 do ${capacity - 1}`);
      return;
    }
    updateQuantity(
      {
        id: entry.id,
        payload: {
          packageCount: entry.packageCount,
          partialTabletCount: parsed,
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
      ? entry.partialTabletCount != null && entry.partialTabletCount > 0
        ? "Luźne tabletki z otwartego opakowania również zostaną usunięte."
        : undefined
      : entry.belowMinimum
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
    belowMinimum: entry.belowMinimum,
    formattedExpiryDate: formatDate(entry.expiryDate),
    usageView: buildUsageView(entry),
    confirmingDelete,
    openDeleteConfirm,
    closeDeleteConfirm,
    confirmDelete,
    deletePending,
    deleteMessage,
    deleteNote,
    deleteError,
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
