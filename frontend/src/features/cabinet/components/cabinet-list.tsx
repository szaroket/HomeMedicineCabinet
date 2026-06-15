import { useCabinetEntries } from "@/features/cabinet/api/cabinet-queries";

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
              Dawka
            </th>
            <th className="px-4 py-3 text-left font-medium text-blue-400">
              Postać
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
          {entries.map((e) => {
            const statusInfo = STATUS_LABEL[e.status] ?? {
              label: e.status,
              className: "text-slate-400",
            };
            return (
              <tr
                key={e.id}
                className="border-b border-slate-700 last:border-0 hover:bg-slate-800/50"
              >
                <td className="px-4 py-3">{e.name}</td>
                <td className="px-4 py-3">{e.strength ?? "—"}</td>
                <td className="px-4 py-3">{e.pharmaceutical_form ?? "—"}</td>
                <td className="px-4 py-3">{e.package_count}</td>
                <td className="px-4 py-3">
                  {e.total_tablets != null ? e.total_tablets : "—"}
                </td>
                <td className="px-4 py-3">{formatDate(e.expiry_date)}</td>
                <td className={`px-4 py-3 font-medium ${statusInfo.className}`}>
                  {statusInfo.label}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
