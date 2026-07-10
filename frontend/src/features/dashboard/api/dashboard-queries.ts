import { useQuery } from "@tanstack/react-query";
import { getCabinetSummary } from "@/features/dashboard/api/dashboard-api";

export const dashboardKeys = {
  summary: () => ["cabinet", "summary"] as const,
};

export function useCabinetSummary() {
  return useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: () => getCabinetSummary(),
  });
}
