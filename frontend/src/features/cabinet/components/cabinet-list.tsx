import { useState } from "react";
import { useCabinetEntries } from "@/features/cabinet/api/cabinet-queries";
import type { CabinetEntryOut } from "@/features/cabinet/api/cabinet-api";

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-4 w-4 shrink-0 text-slate-400"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      {expanded ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      )}
    </svg>
  );
}

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  valid: { label: "Ważny", className: "text-green-400" },
  expiring: { label: "Bliski termin", className: "text-orange-400" },
  expired: { label: "Przeterminowany", className: "text-red-400" },
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function EntryRow({ e }: { e: CabinetEntryOut }) {
  const [expanded, setExpanded] = useState(false);
  const statusInfo = STATUS_LABEL[e.status] ?? {
    label: e.status,
    className: "text-slate-400",
  };

  return (
    <>
      <tr
        className="border-b border-slate-700 last:border-0 hover:bg-slate-800/50 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-3">
          <span className="inline-flex items-center gap-1">
            <ChevronIcon expanded={expanded} />
            {e.name}
          </span>
        </td>
        <td className="px-4 py-3">{e.package_count}</td>
        <td className="px-4 py-3">
          {e.total_tablets != null ? e.total_tablets : "—"}
        </td>
        <td className="px-4 py-3">{formatDate(e.expiry_date)}</td>
        <td className={`px-4 py-3 font-medium ${statusInfo.className}`}>
          {statusInfo.label}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-700 last:border-0 bg-slate-800/30">
          <td colSpan={5} className="px-6 py-3">
            <dl className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="text-slate-400">Dawka:</dt>
                <dd className="text-white">{e.strength ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Postać:</dt>
                <dd className="text-white">{e.pharmaceutical_form ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Droga podania:</dt>
                <dd className="text-white">
                  {e.route_of_administration ?? "—"}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Ulotka:</dt>
                <dd>
                  {e.leaflet_url ? (
                    <a
                      href={e.leaflet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      Otwórz
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="text-slate-400">Charakterystyka:</dt>
                <dd>
                  {e.specification_url ? (
                    <a
                      href={e.specification_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                      onClick={(ev) => ev.stopPropagation()}
                    >
                      Otwórz
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}

export function CabinetList() {
  const { data: entries, isLoading, isError } = useCabinetEntries();

  if (isLoading) {
    return <p className="text-sm text-slate-400">Ładowanie…</p>;
  }

  if (isError) {
    return <p className="text-sm text-red-400">Błąd ładowania danych.</p>;
  }

  if (!entries || entries.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        Apteczka jest pusta. Dodaj pierwszy lek.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-slate-700">
      <table className="w-full text-sm text-white">
        <thead className="border-b border-slate-700 bg-slate-800">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Nazwa
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Opak.
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Sztuki
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Ważność
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <EntryRow key={e.id} e={e} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
