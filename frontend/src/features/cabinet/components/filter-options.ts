export type StatusFilter = "valid" | "expiring" | "expired";
export type CategoryFilter = "important";

export const STATUS_OPTIONS: { value: StatusFilter | ""; label: string }[] = [
  { value: "", label: "Wszystkie" },
  { value: "valid", label: "Aktualny" },
  { value: "expiring", label: "Bliski termin" },
  { value: "expired", label: "Przeterminowany" },
];

export const CATEGORY_OPTIONS: { value: CategoryFilter | ""; label: string }[] =
  [
    { value: "", label: "Wszystkie" },
    { value: "important", label: "Ważne" },
  ];

export const STOCK_OPTIONS: { value: "low" | ""; label: string }[] = [
  { value: "", label: "Wszystkie" },
  { value: "low", label: "Brak w apteczce" },
];
