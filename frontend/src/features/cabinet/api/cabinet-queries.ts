import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  searchProducts,
  listVariants,
  addEntry,
  listEntries,
  toggleImportant,
  setUsage,
  deleteEntry,
  updateQuantity,
} from "@/features/cabinet/api/cabinet-api";
import type {
  ProductOut,
  AddEntryPayload,
  CabinetListParams,
  UsageFieldsPayload,
  UpdateQuantityPayload,
} from "@/features/cabinet/api/cabinet-api";

export const cabinetKeys = {
  products: (search: string) => ["cabinet", "products", search] as const,
  variants: (name: string, strength: string | null, form: string | null) =>
    ["cabinet", "variants", name, strength, form] as const,
  entriesAll: () => ["cabinet", "entries"] as const,
  entries: (params: CabinetListParams) =>
    ["cabinet", "entries", params] as const,
};

export function useProductSearch(debouncedSearch: string) {
  return useQuery({
    queryKey: cabinetKeys.products(debouncedSearch),
    queryFn: () => searchProducts(debouncedSearch),
    enabled: debouncedSearch.length >= 2,
  });
}

export function useVariants(product: ProductOut | null) {
  return useQuery({
    queryKey: cabinetKeys.variants(
      product?.name ?? "",
      product?.strength ?? null,
      product?.pharmaceutical_form ?? null,
    ),
    queryFn: () =>
      listVariants(
        product!.name,
        product!.strength,
        product!.pharmaceutical_form,
      ),
    enabled: product != null,
  });
}

export function useCabinetEntries(params: CabinetListParams) {
  return useQuery({
    queryKey: cabinetKeys.entries(params),
    queryFn: () => listEntries(params),
    placeholderData: keepPreviousData,
  });
}

// Dashboard depends on cabinet, so this literal key must stay in sync by hand
// with dashboardKeys.summary() (dashboard-queries.ts), the source of truth for it.
const DASHBOARD_SUMMARY_KEY = ["cabinet", "summary"] as const;

export function useAddEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddEntryPayload) => addEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY });
    },
  });
}

export function useToggleImportant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_important }: { id: string; is_important: boolean }) =>
      toggleImportant(id, is_important),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY });
    },
  });
}

export function useSetUsage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: UsageFieldsPayload;
    }) => setUsage(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY });
    },
  });
}

export function useDeleteEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: string }) => deleteEntry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY });
    },
  });
}

export function useUpdateQuantity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: UpdateQuantityPayload;
    }) => updateQuantity(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
      queryClient.invalidateQueries({ queryKey: DASHBOARD_SUMMARY_KEY });
    },
  });
}
