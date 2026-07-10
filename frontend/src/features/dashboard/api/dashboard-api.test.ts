import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCabinetSummary } from "@/features/dashboard/api/dashboard-api";
import { callInfo, jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("getCabinetSummary", () => {
  it("calls /cabinet/summary", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        total: 0,
        valid: 0,
        expiring: 0,
        expired: 0,
        out_of_stock: 0,
      }),
    );

    await getCabinetSummary();

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/summary");
  });

  it("returns the parsed body", async () => {
    const summary = {
      total: 10,
      valid: 6,
      expiring: 2,
      expired: 2,
      out_of_stock: 1,
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(summary));

    await expect(getCabinetSummary()).resolves.toEqual(summary);
  });
});
