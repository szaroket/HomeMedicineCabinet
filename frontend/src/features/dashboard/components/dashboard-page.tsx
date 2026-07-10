import { AppLayout } from "@/app/components/app-layout";
import { useCabinetSummary } from "@/features/dashboard/api/dashboard-queries";
import { SummaryCard } from "@/features/dashboard/components/summary-card";
import { DashboardSkeleton } from "@/features/dashboard/components/dashboard-skeleton";
import { DashboardEmpty } from "@/features/dashboard/components/dashboard-empty";
import { SUMMARY_CARDS } from "@/features/dashboard/components/summary-cards.config";

export function DashboardPage() {
  const { data, isLoading, isError, refetch } = useCabinetSummary();

  return (
    <AppLayout>
      <div className="flex h-full flex-col overflow-y-auto">
        <div className="mb-6 text-center">
          <h2 className="text-xl font-semibold text-white">Panel główny</h2>
        </div>

        {isLoading && <DashboardSkeleton />}

        {!isLoading && isError && (
          <div className="flex flex-col items-center justify-center gap-3">
            <p className="text-sm text-red-400">
              Nie udało się wczytać podsumowania apteczki.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Spróbuj ponownie
            </button>
          </div>
        )}

        {!isLoading && !isError && data && data.total === 0 && (
          <DashboardEmpty />
        )}

        {!isLoading && !isError && data && data.total > 0 && (
          <div className="mx-auto grid w-full max-w-6xl grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
            {SUMMARY_CARDS.map((card) => (
              <SummaryCard
                key={card.key}
                label={card.label}
                count={data[card.key]}
                to={card.to}
                accent={card.accent}
              />
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
