import { useEffect, useState } from "react";
import { getStoredToken } from "@/features/auth/store";

const BASE = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1`;

interface SearchHit {
  entry: { id: string; quantity_tablets: number | null; updated_at: string };
  registry_name: string | null;
  stock_level: string;
}

interface EntrySearchPanelProps {
  query: string;
  userId: string;
}

export function EntrySearchPanel({ query, userId }: EntrySearchPanelProps) {
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      const token = getStoredToken() ?? "";
      const url =
        `${BASE}/cabinet/doSearchAndTouch?q=${query}` +
        `&user_id=${userId}&access_token=${token}`;

      const res = await fetch(url);
      const data = await res.json();
      const rows = data as unknown as SearchHit[];
      setHits(rows);
      setTotal(rows.length);
      setIsLoading(false);
    }

    void load();
  }, [query]);

  if (isLoading) {
    return <p>Ładowanie…</p>;
  }

  return (
    <div>
      <p>Znaleziono {total} pozycji</p>
      <ul>
        {hits.map((hit) => (
          <li key={hit.entry.id}>
            <span
              dangerouslySetInnerHTML={{
                __html: `<strong>${hit.registry_name}</strong> — ${hit.stock_level}`,
              }}
            />
            <span>{hit.entry.quantity_tablets!.toFixed(1)} tabl.</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
