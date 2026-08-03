import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { jsonResponse } from "@/test/api-test-utils";
import type { NotificationItem } from "@/features/notifications/api/notifications-api";

// Echoes the incoming query string so tests can assert exactly where a
// notification row navigated to (name search + trigger-specific filter).
function CabinetEcho() {
  const [searchParams] = useSearchParams();
  return (
    <>
      <div>Cabinet page</div>
      <div>params: {searchParams.toString()}</div>
    </>
  );
}

function renderBell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/" element={<NotificationBell />} />
          <Route path="/cabinet" element={<CabinetEcho />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function makeItem(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    triggerType: "expiry",
    cabinetEntryId: "entry-1",
    medicationName: "Apap",
    daysRemaining: 5,
    ...overrides,
  };
}

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("hides the badge when there are no active notifications", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ items: [] }));
    renderBell();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it("shows 9+ when the active count exceeds nine", async () => {
    const items = Array.from({ length: 10 }, (_, index) =>
      makeItem({ cabinetEntryId: `entry-${index}` }),
    );
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ items }));
    renderBell();

    expect(await screen.findByText("9+")).toBeInTheDocument();
  });

  it("opens the panel with rows and Polish copy per trigger type, and dismiss invokes the mutation", async () => {
    const items = [
      makeItem({
        triggerType: "expiry",
        cabinetEntryId: "entry-1",
        medicationName: "Apap",
        daysRemaining: 5,
      }),
      makeItem({
        triggerType: "below_minimum",
        cabinetEntryId: "entry-2",
        medicationName: "Ibuprom",
        daysRemaining: null,
      }),
      makeItem({
        triggerType: "run_out",
        cabinetEntryId: "entry-3",
        medicationName: "Amoksiklav",
        daysRemaining: 2,
      }),
    ];
    vi.mocked(fetch).mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/notifications/dismiss")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      void init;
      return Promise.resolve(jsonResponse({ items }));
    });

    const user = userEvent.setup();
    renderBell();

    await user.click(
      await screen.findByRole("button", { name: "Powiadomienia" }),
    );

    expect(
      await screen.findByText("Termin ważności kończy się za 5 dni"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Liczba opakowań poniżej minimalnej wartości"),
    ).toBeInTheDocument();
    expect(screen.getByText("Zabraknie za 2 dni")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Odrzuć powiadomienie: Apap" }),
    );

    await waitFor(() => {
      const dismissCall = vi
        .mocked(fetch)
        .mock.calls.find(([url]) =>
          String(url).includes("/notifications/dismiss"),
        );
      expect(dismissCall).toBeDefined();
      expect(dismissCall?.[1]?.method).toBe("POST");
    });
  });

  it("caps the list height and lets it scroll when there are many notifications", async () => {
    const items = Array.from({ length: 15 }, (_, index) =>
      makeItem({
        cabinetEntryId: `entry-${index}`,
        medicationName: `Lek ${index}`,
      }),
    );
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ items }));

    const user = userEvent.setup();
    renderBell();

    await user.click(
      await screen.findByRole("button", { name: "Powiadomienia" }),
    );

    const list = await screen.findByRole("list");
    expect(list).toHaveClass("max-h-[70vh]");
    expect(list).toHaveClass("overflow-y-auto");
  });

  it("navigates to the cabinet filtered by medication name when a row is clicked, and closes the panel", async () => {
    const items = [
      makeItem({ cabinetEntryId: "entry-1", medicationName: "Apap" }),
    ];
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ items }));

    const user = userEvent.setup();
    renderBell();

    await user.click(
      await screen.findByRole("button", { name: "Powiadomienia" }),
    );

    await user.click(
      await screen.findByRole("button", { name: "Pokaż w apteczce: Apap" }),
    );

    expect(await screen.findByText("Cabinet page")).toBeInTheDocument();
    expect(
      screen.getByText("params: search=Apap&status=expiring"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("dialog", { name: "Powiadomienia" }),
    ).not.toBeInTheDocument();
  });

  it.each([
    {
      name: "expiry still ahead → expiring status",
      item: {
        triggerType: "expiry" as const,
        medicationName: "Apap",
        daysRemaining: 5,
      },
      expected: "search=Apap&status=expiring",
    },
    {
      name: "expiry already past → expired status",
      item: {
        triggerType: "expiry" as const,
        medicationName: "Apap",
        daysRemaining: -3,
      },
      expected: "search=Apap&status=expired",
    },
    {
      name: "below_minimum → below_minimum flag",
      item: {
        triggerType: "below_minimum" as const,
        medicationName: "Ibuprom",
        daysRemaining: null,
      },
      expected: "search=Ibuprom&below_minimum=true",
    },
    {
      name: "run_out → insufficient sufficiency",
      item: {
        triggerType: "run_out" as const,
        medicationName: "Amoksiklav",
        daysRemaining: 2,
      },
      expected: "search=Amoksiklav&sufficiency=insufficient",
    },
  ])(
    "navigates to the cabinet with a trigger-specific filter ($name)",
    async ({ item, expected }) => {
      vi.mocked(fetch).mockResolvedValue(
        jsonResponse({ items: [makeItem(item)] }),
      );

      const user = userEvent.setup();
      renderBell();

      await user.click(
        await screen.findByRole("button", { name: "Powiadomienia" }),
      );
      await user.click(
        await screen.findByRole("button", {
          name: `Pokaż w apteczce: ${item.medicationName}`,
        }),
      );

      expect(
        await screen.findByText(`params: ${expected}`),
      ).toBeInTheDocument();
    },
  );

  it("does not navigate when the dismiss button on a row is clicked", async () => {
    const items = [
      makeItem({ cabinetEntryId: "entry-1", medicationName: "Apap" }),
    ];
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/notifications/dismiss")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse({ items }));
    });

    const user = userEvent.setup();
    renderBell();

    await user.click(
      await screen.findByRole("button", { name: "Powiadomienia" }),
    );

    await user.click(
      screen.getByRole("button", { name: "Odrzuć powiadomienie: Apap" }),
    );

    await waitFor(() => {
      const dismissCall = vi
        .mocked(fetch)
        .mock.calls.find(([url]) =>
          String(url).includes("/notifications/dismiss"),
        );
      expect(dismissCall).toBeDefined();
    });
    expect(screen.queryByText("Cabinet page")).not.toBeInTheDocument();
  });

  it("dismiss all invokes the mutation once per active notification", async () => {
    const items = [
      makeItem({ cabinetEntryId: "entry-1", medicationName: "Apap" }),
      makeItem({ cabinetEntryId: "entry-2", medicationName: "Ibuprom" }),
    ];
    vi.mocked(fetch).mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/notifications/dismiss")) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse({ items }));
    });

    const user = userEvent.setup();
    renderBell();

    await user.click(
      await screen.findByRole("button", { name: "Powiadomienia" }),
    );
    await user.click(
      await screen.findByRole("button", { name: "Odrzuć wszystkie" }),
    );

    await waitFor(() => {
      const dismissCalls = vi
        .mocked(fetch)
        .mock.calls.filter(([url]) =>
          String(url).includes("/notifications/dismiss"),
        );
      expect(dismissCalls).toHaveLength(2);
    });
  });
});
