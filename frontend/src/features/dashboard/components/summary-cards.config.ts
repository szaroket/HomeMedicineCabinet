import type { CabinetSummaryOut } from "@/features/dashboard/api/dashboard-api";

export type SummaryCardAccent =
  "total" | "valid" | "expiring" | "expired" | "out_of_stock";

export interface SummaryCardConfig {
  key: keyof CabinetSummaryOut;
  label: string;
  to: string;
  accent: SummaryCardAccent;
}

export const SUMMARY_CARDS: SummaryCardConfig[] = [
  { key: "total", label: "Łącznie leków", to: "/cabinet", accent: "total" },
  {
    key: "valid",
    label: "Aktualne leki",
    to: "/cabinet?status=valid",
    accent: "valid",
  },
  {
    key: "expiring",
    label: "Leki bliskie terminu ważności",
    to: "/cabinet?status=expiring",
    accent: "expiring",
  },
  {
    key: "expired",
    label: "Leki przeterminowane",
    to: "/cabinet?status=expired",
    accent: "expired",
  },
  {
    key: "out_of_stock",
    label: "Leki bez zapasu",
    to: "/cabinet?below_minimum=true",
    accent: "out_of_stock",
  },
];
