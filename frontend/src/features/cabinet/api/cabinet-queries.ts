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
} from "@/features/cabinet/api/cabinet-api";

export const cabinetKeys = {
  products: (q: string) => ["cabinet", "products", q] as const,
  variants: (name: string, strength: string | null, form: string | null) =>
    ["cabinet", "variants", name, strength, form] as const,
  entries: () => ["cabinet", "entries"] as const,
};

export function useProductSearch(debouncedQ: string) {
  return useQuery({
    queryKey: cabinetKeys.products(debouncedQ),
    queryFn: () => searchProducts(debouncedQ),
    enabled: debouncedQ.length >= 2,
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

export function useCabinetEntries() {
  return useQuery({
    queryKey: cabinetKeys.entries(),
    queryFn: listEntries,
  });
}

export function useAddEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddEntryPayload) => addEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cabinetKeys.entries() });
    },
  });
}
