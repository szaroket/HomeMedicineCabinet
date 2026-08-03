import { apiFetch, apiJson } from "@/lib/api-client";

export interface ProductOut {
  name: string;
  strength: string | null;
  pharmaceuticalForm: string | null;
  activeIngredient: string | null;
}

export interface VariantOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceuticalForm: string | null;
  capacity: number | null;
  capacityUnit: string | null;
  isTabletBased: boolean;
  activeIngredient: string | null;
  routeOfAdministration: string | null;
}

export interface AddEntryOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceuticalForm: string | null;
  capacity: number | null;
  capacityUnit: string | null;
  isTabletBased: boolean;
  packageCount: number;
  partialTabletCount: number | null;
  expiryDate: string;
  totalTablets: number | null;
}

export interface MergeSummary {
  previousPackageCount: number;
  previousPartialTabletCount: number | null;
  previousTotalTablets: number | null;
  addedTotalTablets: number | null;
  newTotalTablets: number | null;
}

export interface AddEntryResult {
  merged: boolean;
  entry: AddEntryOut;
  mergeSummary: MergeSummary | null;
}

export interface CabinetEntryOut {
  id: string;
  name: string;
  strength: string | null;
  pharmaceuticalForm: string | null;
  capacity: number | null;
  capacityUnit: string | null;
  isTabletBased: boolean;
  packageCount: number;
  partialTabletCount: number | null;
  expiryDate: string;
  totalTablets: number | null;
  status: string;
  activeIngredient: string | null;
  routeOfAdministration: string | null;
  leafletUrl: string | null;
  specificationUrl: string | null;
  isImportant: boolean;
  belowMinimum: boolean;
  isUsed: boolean;
  dosageTimes: number | null;
  dosagePeriod: "day" | "week" | null;
  dosageAmount: number | null;
  dosageStartDate: string | null;
  dosageEndDate: string | null;
  daysOfSupply: number | null;
  daysUntilEnd: number | null;
  isSufficient: boolean | null;
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

export interface UsageFieldsPayload {
  isUsed: boolean;
  dosageTimes?: number | null;
  dosagePeriod?: "day" | "week" | null;
  dosageAmount?: number | null;
  dosageStartDate?: string | null;
  dosageEndDate?: string | null;
}

export interface AddEntryPayload {
  medicationRegistryId: string;
  packageCount: number;
  expiryDate: string;
  partialTabletCount?: number | null;
  isImportant?: boolean;
  usage?: UsageFieldsPayload | null;
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
  pageSize?: 20 | 50 | 100;
  category?: "important" | "used";
  belowMinimum?: boolean;
  sufficiency?: "insufficient" | "sufficient";
}

export interface CabinetPageOut {
  items: CabinetEntryOut[];
  total: number;
  page: number;
  pageSize: number;
}

export function listEntries(
  params?: CabinetListParams,
): Promise<CabinetPageOut> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.search) searchParams.set("search", params.search);
  if (params?.order) searchParams.set("order", params.order);
  if (params?.page != null) searchParams.set("page", String(params.page));
  if (params?.pageSize != null)
    searchParams.set("pageSize", String(params.pageSize));
  if (params?.category) searchParams.set("category", params.category);
  if (params?.belowMinimum) searchParams.set("belowMinimum", "true");
  if (params?.sufficiency) searchParams.set("sufficiency", params.sufficiency);
  const qs = searchParams.toString();
  return apiJson<CabinetPageOut>(`/cabinet/entries${qs ? `?${qs}` : ""}`);
}

export function toggleImportant(
  id: string,
  isImportant: boolean,
): Promise<CabinetEntryOut> {
  return apiJson<CabinetEntryOut>(`/cabinet/entries/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ isImportant }),
  });
}

export function setUsage(
  id: string,
  payload: UsageFieldsPayload,
): Promise<CabinetEntryOut> {
  return apiJson<CabinetEntryOut>(`/cabinet/entries/${id}/usage`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface UpdateQuantityPayload {
  packageCount: number;
  partialTabletCount?: number | null;
}

export function updateQuantity(
  id: string,
  payload: UpdateQuantityPayload,
): Promise<CabinetEntryOut> {
  return apiJson<CabinetEntryOut>(`/cabinet/entries/${id}/quantity`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteEntry(id: string): Promise<void> {
  const res = await apiFetch(`/cabinet/entries/${id}`, { method: "DELETE" });
  if (!res.ok) throw res;
}
