import type { AddEntryResult } from "@/features/cabinet/api/cabinet-api";

interface Props {
  result: AddEntryResult;
  onAddAnother: () => void;
  onNavigate: () => void;
}

export function AddResultDialog({ result, onAddAnother, onNavigate }: Props) {
  const { merged, merge_summary } = result;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-sm rounded-lg border border-slate-600 bg-slate-800 p-6 shadow-xl">
        <h2 className="mb-3 text-lg font-semibold text-white">
          {merged ? "Połączono z istniejącym wpisem" : "Dodano lek"}
        </h2>

        {merged && merge_summary && (
          <div className="mb-4 rounded bg-slate-700 p-3 text-sm text-slate-300">
            {merge_summary.previous_total_tablets != null ? (
              <>
                <p>
                  Przed:{" "}
                  <span className="text-white">
                    {merge_summary.previous_package_count} opak.
                    {merge_summary.previous_partial_tablet_count != null
                      ? ` + ${merge_summary.previous_partial_tablet_count} szt.`
                      : ""}{" "}
                    ({merge_summary.previous_total_tablets} szt. łącznie)
                  </span>
                </p>
                <p>
                  Po:{" "}
                  <span className="text-white">
                    {result.entry.package_count} opak.
                    {result.entry.partial_tablet_count != null
                      ? ` + ${result.entry.partial_tablet_count} szt.`
                      : ""}{" "}
                    ({merge_summary.new_total_tablets} szt. łącznie)
                  </span>
                </p>
              </>
            ) : (
              <>
                <p>
                  Przed:{" "}
                  <span className="text-white">
                    {merge_summary.previous_package_count} opak.
                  </span>
                </p>
                <p>
                  Po:{" "}
                  <span className="text-white">
                    {result.entry.package_count} opak.
                  </span>
                </p>
              </>
            )}
          </div>
        )}

        <p className="mb-5 text-sm text-slate-300">
          Czy chcesz dodać kolejny lek?
        </p>

        <div className="flex gap-3">
          <button
            onClick={onAddAnother}
            className="flex-1 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            Tak
          </button>
          <button
            onClick={onNavigate}
            className="flex-1 rounded border border-slate-500 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700"
          >
            Nie
          </button>
        </div>
      </div>
    </div>
  );
}
