import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { SUMMARY_CARDS } from "@/features/dashboard/components/summary-cards.config";
import type { CabinetSummaryOut } from "@/features/dashboard/api/dashboard-api";
import { AuthProvider } from "@/features/auth/store";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <DashboardPage />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("shows a loading skeleton while the summary is fetching", () => {
    vi.mocked(fetch).mockReturnValueOnce(new Promise(() => {}));
    renderPage();

    expect(
      screen.getByRole("status", { name: "Ładowanie panelu głównego" }),
    ).toBeInTheDocument();
  });

  it("shows a Polish error message with a retry button on failure", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );
    renderPage();

    expect(
      await screen.findByText("Nie udało się wczytać podsumowania apteczki."),
    ).toBeInTheDocument();

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          total: 1,
          valid: 1,
          expiring: 0,
          expired: 0,
          out_of_stock: 0,
        }),
        { status: 200 },
      ),
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  });

  it("shows the add-CTA empty state instead of five zeros when the cabinet is empty", async () => {
    const empty: CabinetSummaryOut = {
      total: 0,
      valid: 0,
      expiring: 0,
      expired: 0,
      out_of_stock: 0,
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(empty), { status: 200 }),
    );
    renderPage();

    expect(
      await screen.findByRole("link", { name: "Dodaj pierwszy lek" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Łącznie leków")).not.toBeInTheDocument();
  });

  it("renders five cards with counts and correctly pre-filtered links when populated", async () => {
    const summary: CabinetSummaryOut = {
      total: 10,
      valid: 6,
      expiring: 2,
      expired: 1,
      out_of_stock: 1,
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(summary), { status: 200 }),
    );
    renderPage();

    for (const card of SUMMARY_CARDS) {
      const link = await screen.findByRole("link", {
        name: new RegExp(`${summary[card.key]}.*${card.label}`, "s"),
      });
      expect(link).toHaveAttribute("href", card.to);
    }
  });
});
