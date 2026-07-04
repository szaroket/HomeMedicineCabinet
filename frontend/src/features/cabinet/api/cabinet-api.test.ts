import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  addEntry,
  deleteEntry,
  listEntries,
  listVariants,
  searchProducts,
  setUsage,
  toggleImportant,
  updateQuantity,
} from "@/features/cabinet/api/cabinet-api";
import { callInfo, jsonResponse } from "@/test/api-test-utils";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("searchProducts", () => {
  it("encodes the search term in the query string", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([]));

    await searchProducts("aspirin & co");

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe(
      `/medicines/products?search=${encodeURIComponent("aspirin & co")}`,
    );
  });

  it("returns the parsed body", async () => {
    const products = [
      {
        name: "Aspirin",
        strength: null,
        pharmaceutical_form: null,
        active_ingredient: null,
      },
    ];
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(products));

    await expect(searchProducts("aspirin")).resolves.toEqual(products);
  });
});

describe("listVariants", () => {
  it("includes strength and form only when non-null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([]));

    await listVariants("Aspirin", "500mg", "tablet");

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe(
      "/medicines/variants?name=Aspirin&strength=500mg&form=tablet",
    );
  });

  it("omits strength and form when null", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse([]));

    await listVariants("Aspirin", null, null);

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/medicines/variants?name=Aspirin");
  });
});

describe("listEntries", () => {
  it("omits the query string when no params are set", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    );

    await listEntries();

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries");
  });

  it("includes each optional param only when set", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    );

    await listEntries({ status: "valid", page: 2 });

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries?status=valid&page=2");
  });

  it("serializes below_minimum as the literal string true when truthy", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    );

    await listEntries({ below_minimum: true });

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries?below_minimum=true");
  });

  it("omits below_minimum when false", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    );

    await listEntries({ below_minimum: false });

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries");
  });

  it("includes all optional params together in order", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
    );

    await listEntries({
      status: "expiring",
      search: "aspirin",
      order: "desc",
      page: 2,
      page_size: 50,
      category: "important",
      below_minimum: true,
      sufficiency: "insufficient",
    });

    const { path } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe(
      "/cabinet/entries?status=expiring&search=aspirin&order=desc&page=2&page_size=50&category=important&below_minimum=true&sufficiency=insufficient",
    );
  });
});

describe("addEntry", () => {
  it("POSTs a JSON body to /cabinet/entries", async () => {
    const result = {
      merged: false,
      entry: {},
      merge_summary: null,
    };
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(result));
    const payload = {
      medication_registry_id: "reg-1",
      package_count: 2,
      expiry_date: "2027-01-01",
    };

    await addEntry(payload);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});

describe("toggleImportant", () => {
  it("PATCHes the entry with the is_important flag", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    await toggleImportant("entry-1", true);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries/entry-1");
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify({ is_important: true }));
  });
});

describe("setUsage", () => {
  it("PATCHes /cabinet/entries/:id/usage", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));
    const payload = { is_used: true, dosage_times: 2 };

    await setUsage("entry-1", payload);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries/entry-1/usage");
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});

describe("updateQuantity", () => {
  it("PATCHes /cabinet/entries/:id/quantity", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));
    const payload = { package_count: 3 };

    await updateQuantity("entry-1", payload);

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries/entry-1/quantity");
    expect(init?.method).toBe("PATCH");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(init?.body).toBe(JSON.stringify(payload));
  });
});

describe("deleteEntry", () => {
  it("DELETEs the entry and resolves on ok", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}));

    await expect(deleteEntry("entry-1")).resolves.toBeUndefined();

    const { path, init } = callInfo(vi.mocked(fetch).mock.calls[0]);
    expect(path).toBe("/cabinet/entries/entry-1");
    expect(init?.method).toBe("DELETE");
  });

  it("throws the raw Response on !ok", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({}, { status: 404 }));

    await expect(deleteEntry("entry-1")).rejects.toBeInstanceOf(Response);
  });
});
