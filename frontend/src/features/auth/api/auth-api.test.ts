import { beforeEach, describe, expect, it, vi } from "vitest";
import { getMe, login, logout, register } from "@/features/auth/api/auth-api";
import { callInfo, jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("register", () => {
  it("POSTs to /auth/register with a JSON body and returns the response", async () => {
    const response = {
      access_token: "token",
      token_type: "bearer",
      user: { id: "u1", email: "a@b.com" },
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(response));
    const payload = { email: "a@b.com", password: "secret123" };

    await expect(register(payload)).resolves.toEqual(response);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/auth/register");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});

describe("login", () => {
  it("POSTs to /auth/login with a JSON body and returns the response", async () => {
    const response = {
      access_token: "token",
      token_type: "bearer",
      user: { id: "u1", email: "a@b.com" },
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(response));
    const payload = { email: "a@b.com", password: "secret123" };

    await expect(login(payload)).resolves.toEqual(response);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/auth/login");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});

describe("logout", () => {
  it("POSTs to /auth/logout and does not throw on ok", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    await expect(logout()).resolves.toBeUndefined();

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/auth/logout");
    expect(init?.method).toBe("POST");
  });
});

describe("getMe", () => {
  it("GETs /auth/me and returns the user", async () => {
    const user = { id: "u1", email: "a@b.com" };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(user));

    await expect(getMe()).resolves.toEqual(user);

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/auth/me");
  });
});
