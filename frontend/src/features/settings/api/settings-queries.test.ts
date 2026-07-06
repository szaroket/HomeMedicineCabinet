import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useDeleteAccount } from "@/features/settings/api/settings-queries";

const TOKEN_KEY = "auth_token";

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
  return { queryClient, wrapper };
}

describe("useDeleteAccount", () => {
  beforeEach(() => {
    localStorage.setItem(TOKEN_KEY, "test-token");
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("tears down the token and clears the cache on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    const { queryClient, wrapper } = makeWrapper();
    const clearSpy = vi.spyOn(queryClient, "clear");
    const { result } = renderHook(() => useDeleteAccount(), { wrapper });

    await result.current.mutateAsync();

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(clearSpy).toHaveBeenCalledTimes(1);
  });

  it("tears down the token and clears the cache on a 502 (partial deletion — local data already gone)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 502 }));
    const { queryClient, wrapper } = makeWrapper();
    const clearSpy = vi.spyOn(queryClient, "clear");
    const { result } = renderHook(() => useDeleteAccount(), { wrapper });

    await expect(result.current.mutateAsync()).rejects.toBeInstanceOf(Response);

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(clearSpy).toHaveBeenCalledTimes(1);
  });

  it("keeps the token and cache intact on a 503 (nothing was deleted)", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 503 }));
    const { queryClient, wrapper } = makeWrapper();
    const clearSpy = vi.spyOn(queryClient, "clear");
    const { result } = renderHook(() => useDeleteAccount(), { wrapper });

    await expect(result.current.mutateAsync()).rejects.toBeInstanceOf(Response);

    expect(localStorage.getItem(TOKEN_KEY)).toBe("test-token");
    expect(clearSpy).not.toHaveBeenCalled();
  });
});
