import { useVariants } from "@/features/cabinet/api/cabinet-queries";
import type {
  ProductOut,
  VariantOut,
} from "@/features/cabinet/api/cabinet-api";

interface Props {
  product: ProductOut | null;
  selectedId: string;
  onChange: (variant: VariantOut) => void;
}

export function VariantSelect({ product, selectedId, onChange }: Props) {
  const { data: variants, isLoading } = useVariants(product);

  if (!product) return null;

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="variant-select"
        className="text-sm font-medium text-blue-400"
      >
        Rozmiar opakowania
      </label>
      <select
        id="variant-select"
        value={selectedId}
        onChange={(e) => {
          const v = variants?.find((x) => x.id === e.target.value);
          if (v) onChange(v);
        }}
        className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="">
          {isLoading ? "Ładowanie…" : "Wybierz rozmiar opakowania"}
        </option>
        {variants?.map((v) => (
          <option key={v.id} value={v.id}>
            {v.capacity != null
              ? `${v.capacity} ${v.capacity_unit ?? "szt."}`
              : (v.capacity_unit ?? "—")}
          </option>
        ))}
      </select>
    </div>
  );
}
