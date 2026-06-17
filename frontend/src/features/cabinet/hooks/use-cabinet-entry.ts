import { useState } from "react";
import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";
import { useToggleImportant } from "@/features/cabinet/api/cabinet-queries";

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

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function useCabinetEntry(entry: CabinetEntryOut) {
  const [expanded, setExpanded] = useState(false);
  const { mutate: toggleImportant } = useToggleImportant();

  const statusInfo = STATUS_LABEL[entry.status] ?? {
    label: entry.status,
    className: "text-slate-400",
    pillClassName: "bg-slate-800 text-slate-400",
  };

  function toggleExpanded() {
    setExpanded((prev) => !prev);
  }

  function toggleImportantFlag() {
    toggleImportant({ id: entry.id, is_important: !entry.is_important });
  }

  return {
    expanded,
    toggleExpanded,
    toggleImportant: toggleImportantFlag,
    statusInfo,
    belowMinimum: entry.below_minimum,
    formattedExpiryDate: formatDate(entry.expiry_date),
  };
}
