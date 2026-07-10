import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAddEntry } from "@/features/cabinet/api/cabinet-queries";
import { dashboardKeys } from "@/features/dashboard/api/dashboard-queries";
import { jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("cabinet mutations → dashboard summary invalidation", () => {
  it("invalidates the dashboard summary key on a successful mutation", async () => {
    // Guards the hand-synced literal in cabinet-queries against drifting from
    // dashboardKeys.summary() (the source of truth). If the two ever diverge,
    // the mutation stops refreshing the dashboard counts and this test fails.
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ id: "entry-1" }, { status: 201 }),
    );

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    function Wrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      );
    }

    const { result } = renderHook(() => useAddEntry(), { wrapper: Wrapper });

    result.current.mutate({
      medication_registry_id: "reg-1",
      package_count: 1,
      expiry_date: "2030-01-01",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: dashboardKeys.summary(),
    });
  });
});
