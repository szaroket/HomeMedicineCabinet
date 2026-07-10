import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCabinetSummary } from "@/features/dashboard/api/dashboard-queries";
import { jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useCabinetSummary", () => {
  it("returns data on success", async () => {
    const summary = {
      total: 10,
      valid: 6,
      expiring: 2,
      expired: 2,
      out_of_stock: 1,
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(summary));

    const { result } = renderHook(() => useCabinetSummary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(summary);
  });

  it("surfaces error state on failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "error" }, { status: 500 }),
    );

    const { result } = renderHook(() => useCabinetSummary(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
