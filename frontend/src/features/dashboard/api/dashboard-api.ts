import { apiJson } from "@/lib/api-client";

export interface CabinetSummaryOut {
  total: number;
  valid: number;
  expiring: number;
  expired: number;
  outOfStock: number;
}

export function getCabinetSummary(): Promise<CabinetSummaryOut> {
  return apiJson<CabinetSummaryOut>("/cabinet/summary");
}
