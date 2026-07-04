import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPreferences,
  updatePreferences,
} from "@/features/settings/api/settings-api";
import { callInfo, jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("getPreferences", () => {
  it("GETs /users/preferences and returns the parsed body", async () => {
    const preferences = {
      expiry_threshold_days: 30,
      close_to_finish_threshold_days: 7,
      min_package_count: 1,
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(preferences));

    await expect(getPreferences()).resolves.toEqual(preferences);

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/users/preferences");
  });
});

describe("updatePreferences", () => {
  it("PATCHes /users/preferences with a JSON body", async () => {
    const preferences = {
      expiry_threshold_days: 30,
      close_to_finish_threshold_days: 7,
      min_package_count: 2,
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(preferences));
    const payload = { min_package_count: 2 };

    await expect(updatePreferences(payload)).resolves.toEqual(preferences);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/users/preferences");
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});
