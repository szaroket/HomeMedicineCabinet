import { useState } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import { useProductSearch } from "@/features/cabinet/api/cabinet-queries";
import type { ProductOut } from "@/features/cabinet/api/cabinet-api";

interface Props {
  onSelect: (product: ProductOut) => void;
  selected: ProductOut | null;
}

export function ProductAutocomplete({ onSelect, selected }: Props) {
  const [query, setQuery] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const debouncedQ = useDebounce(query, 250);
  const { data: products } = useProductSearch(debouncedQ);

  function handleSelect(p: ProductOut) {
    setQuery(p.name);
    setOpen(false);
    onSelect(p);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);
    setOpen(true);
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
        <ul className="absolute top-full z-10 mt-1 w-full rounded border border-slate-600 bg-slate-800 shadow-lg">
          {products.map((p, i) => (
            <li
              key={i}
              onMouseDown={() => handleSelect(p)}
              className="cursor-pointer px-3 py-2 text-sm text-white hover:bg-slate-700"
            >
              {p.name}
              {p.strength ? ` ${p.strength}` : ""}
              {p.pharmaceutical_form ? ` · ${p.pharmaceutical_form}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
