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
  active_ingredient: string | null;
  route_of_administration: string | null;
  leaflet_url: string | null;
  specification_url: string | null;
  is_important: boolean;
  below_minimum: boolean;
}

export function searchProducts(search: string): Promise<ProductOut[]> {
  return apiJson<ProductOut[]>(
    `/medicines/products?search=${encodeURIComponent(search)}`,
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
  is_important?: boolean;
}

export function addEntry(payload: AddEntryPayload): Promise<AddEntryResult> {
  return apiJson<AddEntryResult>("/cabinet/entries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface CabinetListParams {
  status?: "valid" | "expiring" | "expired";
  search?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: 20 | 50 | 100;
  category?: "important";
  below_minimum?: boolean;
}

export interface CabinetPageOut {
  items: CabinetEntryOut[];
  total: number;
  page: number;
  page_size: number;
}

export function listEntries(
  params?: CabinetListParams,
): Promise<CabinetPageOut> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.order) searchParams.set("order", params.order);
  if (params?.page != null) searchParams.set("page", String(params.page));
  if (params?.page_size != null)
    searchParams.set("page_size", String(params.page_size));
  if (params?.category) searchParams.set("category", params.category);
  if (params?.below_minimum) searchParams.set("below_minimum", "true");
  const qs = searchParams.toString();
  return apiJson<CabinetPageOut>(`/cabinet/entries${qs ? `?${qs}` : ""}`);
}

export function toggleImportant(
  id: string,
  is_important: boolean,
): Promise<CabinetEntryOut> {
  return apiJson<CabinetEntryOut>(`/cabinet/entries/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_important }),
  });
}
