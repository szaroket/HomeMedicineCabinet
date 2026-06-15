import { apiJson } from "@/lib/api-client";

export interface ProductOut {
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  active_ingredient: string | null;
}

export interface VariantOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  capacity: number | null;
  capacity_unit: string | null;
  is_tablet_based: boolean;
  active_ingredient: string | null;
  route_of_administration: string | null;
}

export interface AddEntryOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  capacity: number | null;
  capacity_unit: string | null;
  is_tablet_based: boolean;
  package_count: number;
  partial_tablet_count: number | null;
  expiry_date: string;
  total_tablets: number | null;
}

export interface MergeSummary {
  previous_package_count: number;
  previous_partial_tablet_count: number | null;
  previous_total_tablets: number | null;
  added_total_tablets: number | null;
  new_total_tablets: number | null;
}

export interface AddEntryResult {
  merged: boolean;
  entry: AddEntryOut;
  merge_summary: MergeSummary | null;
}

export interface CabinetEntryOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceutical_form: string | null;
  capacity: number | null;
  capacity_unit: string | null;
  is_tablet_based: boolean;
  package_count: number;
  partial_tablet_count: number | null;
  expiry_date: string;
  total_tablets: number | null;
  status: string;
}

export function searchProducts(q: string): Promise<ProductOut[]> {
  return apiJson<ProductOut[]>(
    `/medicines/products?query=${encodeURIComponent(q)}`,
  );
}

export function listVariants(
  name: string,
  strength: string | null,
  form: string | null,
): Promise<VariantOut[]> {
  const params = new URLSearchParams({ name });
  if (strength != null) params.set("strength", strength);
  if (form != null) params.set("form", form);
  return apiJson<VariantOut[]>(`/medicines/variants?${params.toString()}`);
}

export interface AddEntryPayload {
  medication_registry_id: string;
  package_count: number;
  expiry_date: string;
  partial_tablet_count?: number | null;
}

export function addEntry(payload: AddEntryPayload): Promise<AddEntryResult> {
  return apiJson<AddEntryResult>("/cabinet/entries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listEntries(): Promise<CabinetEntryOut[]> {
  return apiJson<CabinetEntryOut[]>("/cabinet/entries");
}
