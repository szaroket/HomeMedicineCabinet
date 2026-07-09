import { useEffect } from "react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { AuthProvider, useAuth } from "@/features/auth/store";
import { CabinetPage } from "@/features/cabinet/components/cabinet-page";
import { jsonResponse } from "@/test/api-test-utils";

// Seeds an authenticated session so AppLayout (rendered by CabinetPage) can
// mount its LogoutButton, which reads `useAuth`.
function SignedIn({ children }: { children: ReactNode }) {
  const { setSession } = useAuth();
  useEffect(() => {
    setSession("test-token", { id: "user-1", email: "user@example.com" });
  }, [setSession]);
  return <>{children}</>;
}

// Surfaces the live query string so a test can assert what the URL holds at
// any point (in particular, that an externally-navigated `search` param is
// never transiently dropped by the debounce-sync effect).
function LocationProbe() {
  const location = useLocation();
  return <div>location-search: {location.search}</div>;
}

// Stands in for a notification-row click: navigates the already-mounted
// cabinet into `?search=…` from outside the page.
function ExternalNav({ to }: { to: string }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(to)}>
      external-nav
    </button>
  );
}

function renderCabinet() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/cabinet"]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SignedIn>
            <ExternalNav to="/cabinet?search=Apap" />
            <LocationProbe />
            <Routes>
              <Route path="/cabinet" element={<CabinetPage />} />
            </Routes>
          </SignedIn>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CabinetPage — external search navigation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/notifications")) {
          return Promise.resolve(jsonResponse({ items: [] }));
        }
        return Promise.resolve(
          jsonResponse({ items: [], total: 0, page: 1, page_size: 20 }),
        );
      }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  // Regression guard for the debounce race fixed by the `pendingSearch` guard
  // (cabinet-page.tsx:88-99): when a notification row navigates the mounted
  // cabinet to `?search=Apap`, `debouncedSearch` lags one render behind, so
  // without the guard the sync effect would briefly delete the just-navigated
  // `search` param and only restore it ~400ms later.
  it("keeps an externally-navigated search param through the debounce window", () => {
    renderCabinet();

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "external-nav" }));
    });

    // Immediately after the navigation flush: the param must still be there —
    // without the guard the sync effect deletes it on this very render.
    expect(screen.getByText(/location-search:/)).toHaveTextContent(
      "search=Apap",
    );

    // And it must survive past the debounce window, not reappear after a flicker.
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(screen.getByText(/location-search:/)).toHaveTextContent(
      "search=Apap",
    );
  });
});
