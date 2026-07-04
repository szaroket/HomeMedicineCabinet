import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, apiJson, refreshOnce } from "@/lib/api-client";
import { AuthError } from "@/lib/errors";
import { callInfo, jsonResponse } from "@/test/api-test-utils";

const TOKEN_KEY = "auth_token";

function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("attaches Authorization header when a token is stored", async () => {
    setToken("token-123");
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    await apiFetch("/cabinet/entries");

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries");
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      "Bearer token-123",
    );
  });

  it("omits Authorization header when no token is stored", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    await apiFetch("/cabinet/entries");

    const { init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("refreshes and retries once on a non-/auth/ 401, using the new token", async () => {
    setToken("old-token");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-token" }))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const res = await apiFetch("/cabinet/entries");

    expect(fetch).toHaveBeenCalledTimes(3);
    const retryCall = callInfo(vi.mocked(fetch).mock.calls[2]);
    expect(retryCall.path).toBe("/cabinet/entries");
    expect(new Headers(retryCall.init?.headers).get("Authorization")).toBe(
      "Bearer new-token",
    );
    expect(await res.json()).toEqual({ ok: true });
  });

  it("does not refresh on a 401 for a /auth/-prefixed path", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}, { status: 401 }));

    const res = await apiFetch("/auth/me");

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(res.status).toBe(401);
  });

  it("throws AuthError when refresh returns null", async () => {
    setToken("old-token");
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }));

    await expect(apiFetch("/cabinet/entries")).rejects.toBeInstanceOf(
      AuthError,
    );
  });
});

describe("apiJson", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returns parsed JSON on success", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ hello: "world" }));

    const result = await apiJson<{ hello: string }>("/settings/preferences");

    expect(result).toEqual({ hello: "world" });
  });

  it("throws the raw Response when !res.ok", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}, { status: 500 }));

    await expect(apiJson("/settings/preferences")).rejects.toBeInstanceOf(
      Response,
    );
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}, { status: 500 }));
    try {
      await apiJson("/settings/preferences");
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(Response);
      expect((err as Response).status).toBe(500);
    }
  });
});

describe("refreshOnce", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("collapses concurrent calls onto one refresh, then issues a fresh fetch afterward", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "t1" }));

    const [first, second] = await Promise.all([refreshOnce(), refreshOnce()]);

    expect(first).toBe("t1");
    expect(second).toBe("t1");
    expect(fetch).toHaveBeenCalledTimes(1);

    vi.mocked(fetch).mockResolvedValue(jsonResponse({ access_token: "t2" }));
    const third = await refreshOnce();

    expect(third).toBe("t2");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
