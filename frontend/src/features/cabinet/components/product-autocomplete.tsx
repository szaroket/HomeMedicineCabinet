import { useState } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import { useProductSearch } from "@/features/cabinet/api/cabinet-queries";
import type { ProductOut } from "@/features/cabinet/api/cabinet-api";

interface Props {
  onSelect: (product: ProductOut) => void;
  onClear: () => void;
  selected: ProductOut | null;
}

function productLabel(product: ProductOut): string {
  return [
    product.name,
    product.strength,
    product.pharmaceutical_form ? `· ${product.pharmaceutical_form}` : null,
  ]
    .filter(Boolean)
    .join(" ");
}

export function ProductAutocomplete({ onSelect, onClear, selected }: Props) {
  const [query, setQuery] = useState(selected ? productLabel(selected) : "");
  const [open, setOpen] = useState(false);
  const debouncedQ = useDebounce(query, 250);
  const { data: products } = useProductSearch(debouncedQ);

  function handleSelect(product: ProductOut) {
    setQuery(productLabel(product));
    setOpen(false);
    onSelect(product);
  }

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const value = event.target.value;
    setQuery(value);
    setOpen(true);
    // Editing the text invalidates the current selection so the form can't
    // submit a variant that no longer matches the visible name.
    if (selected !== null && value !== selected.name) {
      onClear();
    }
  }

  return (
    <div className="relative flex flex-col gap-1">
      <label className="text-sm font-medium text-blue-400">Nazwa leku</label>
      <input
        type="text"
        value={query}
        onChange={handleChange}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="np. Aspiryna"
        className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      {open && products && products.length > 0 && (
        <ul
          className="absolute top-full z-10 mt-1 w-full overflow-y-auto rounded border border-slate-600 bg-slate-800 shadow-lg"
          style={{ maxHeight: "16rem" }}
        >
          {products.map((product) => (
            <li
              key={`${product.name}|${product.strength}|${product.pharmaceutical_form}`}
              onMouseDown={() => handleSelect(product)}
              className="cursor-pointer px-3 py-2 text-sm text-white hover:bg-slate-700"
            >
              {productLabel(product)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
