import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  searchProducts,
  listVariants,
  addEntry,
  listEntries,
} from "@/features/cabinet/api/cabinet-api";
import type {
  ProductOut,
  AddEntryPayload,
  CabinetListParams,
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
  });
}

export function useAddEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddEntryPayload) => addEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entriesAll() });
    },
  });
}
