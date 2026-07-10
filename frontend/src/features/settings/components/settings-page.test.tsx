import { useEffect } from "react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/features/auth/store";
import { SettingsPage } from "@/features/settings/components/settings-page";
import { stripBase, jsonResponse } from "@/test/api-test-utils";

function SignedInAs({
  email,
  children,
}: {
  email: string;
  children: ReactNode;
}) {
  const { setSession } = useAuth();
  useEffect(() => {
    setSession("test-token", { id: "user-1", email });
  }, [setSession, email]);
  return <>{children}</>;
}

const preferences = {
  expiry_threshold_days: 30,
  close_to_finish_threshold_days: 7,
  min_package_count: 1,
};

function mockFetchRouting() {
  vi.mocked(fetch).mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = stripBase(url);
    if (path === "/notifications" || path === "/notifications/") {
      return Promise.resolve(jsonResponse({ items: [] }));
    }
    if (path === "/users/preferences" && (!init || init.method === undefined)) {
      return Promise.resolve(jsonResponse(preferences));
    }
    if (path === "/users/preferences" && init?.method === "PATCH") {
      const body = JSON.parse(init.body as string);
      return Promise.resolve(jsonResponse({ ...preferences, ...body }));
    }
    return Promise.resolve(jsonResponse({}));
  });
}

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SignedInAs email="user@example.com">
            <SettingsPage />
          </SignedInAs>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("SettingsPage thresholds", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    mockFetchRouting();
  });

  it("seeds all three preference values from the server", async () => {
    renderPage();

    expect(await screen.findByDisplayValue("30")).toBeInTheDocument();
    expect(screen.getByDisplayValue("7")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1")).toBeInTheDocument();
  });

  it("rejects out-of-range thresholds with Polish messages", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByDisplayValue("30");

    const expiryInput = screen.getByLabelText("Próg ważności (dni)");
    await user.clear(expiryInput);
    await user.type(expiryInput, "5");

    const closeToFinishInput = screen.getByLabelText(
      "Próg kończącego się zapasu (dni)",
    );
    await user.clear(closeToFinishInput);
    await user.type(closeToFinishInput, "0");

    await user.click(screen.getByRole("button", { name: "Zapisz" }));

    expect(
      await screen.findByText("Minimalny próg ważności wynosi 7 dni."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Minimalny próg kończącego się zapasu wynosi 1 dzień."),
    ).toBeInTheDocument();
  });

  it("submits the full payload on save", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByDisplayValue("30");

    await user.click(screen.getByRole("button", { name: "Zapisz" }));

    await waitFor(() => {
      const patchCall = vi
        .mocked(fetch)
        .mock.calls.find(
          (call) => (call[1] as RequestInit | undefined)?.method === "PATCH",
        );
      expect(patchCall).toBeDefined();
      const body = JSON.parse((patchCall?.[1] as RequestInit).body as string);
      expect(body).toEqual(preferences);
    });
  });
});
