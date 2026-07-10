import { apiJson } from "@/lib/api-client";

export interface CabinetSummaryOut {
  total: number;
  valid: number;
  expiring: number;
  expired: number;
  out_of_stock: number;
}

export function getCabinetSummary(): Promise<CabinetSummaryOut> {
  return apiJson<CabinetSummaryOut>("/cabinet/summary");
}
