import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { jsonResponse } from "@/test/api-test-utils";
import type { NotificationItem } from "@/features/notifications/api/notifications-api";

function renderBell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationBell />
    </QueryClientProvider>,
  );
}

function makeItem(overrides: Partial<NotificationItem> = {}): NotificationItem {
  return {
    trigger_type: "expiry",
    cabinet_entry_id: "entry-1",
    medication_name: "Apap",
    days_remaining: 5,
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
      makeItem({ cabinet_entry_id: `entry-${index}` }),
    );
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ items }));
    renderBell();

    expect(await screen.findByText("9+")).toBeInTheDocument();
  });

  it("opens the panel with rows and Polish copy per trigger type, and dismiss invokes the mutation", async () => {
    const items = [
      makeItem({
        trigger_type: "expiry",
        cabinet_entry_id: "entry-1",
        medication_name: "Apap",
        days_remaining: 5,
      }),
      makeItem({
        trigger_type: "below_minimum",
        cabinet_entry_id: "entry-2",
        medication_name: "Ibuprom",
        days_remaining: null,
      }),
      makeItem({
        trigger_type: "run_out",
        cabinet_entry_id: "entry-3",
        medication_name: "Amoksiklav",
        days_remaining: 2,
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

  it("dismiss all invokes the mutation once per active notification", async () => {
    const items = [
      makeItem({ cabinet_entry_id: "entry-1", medication_name: "Apap" }),
      makeItem({ cabinet_entry_id: "entry-2", medication_name: "Ibuprom" }),
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
