import { afterEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AccountDeletedPage } from "@/features/auth/components/account-deleted-page";
import { AuthProvider } from "@/features/auth/store";

// AuthProvider seeds its token from localStorage on init, so seeding the key
// before render decides whether the guard sees an authenticated visitor.
function renderPage(initialEntries: string[] = ["/account-deleted"]) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/account-deleted" element={<AccountDeletedPage />} />
          <Route path="/" element={<div>Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("AccountDeletedPage", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("renders the full-deletion message and a Powrót link to /login by default", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Konto zostało usunięte" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Twoje konto oraz wszystkie powiązane dane zostały trwale usunięte.",
      ),
    ).toBeVisible();

    const backLink = screen.getByRole("link", { name: "Powrót" });
    expect(backLink).toHaveAttribute("href", "/login");
  });

  it("renders the partial-deletion message when the partial query param is set", () => {
    renderPage(["/account-deleted?partial=1"]);

    expect(
      screen.getByText(
        "Konto zostało częściowo usunięte — zaloguj się ponownie, aby dokończyć.",
      ),
    ).toBeVisible();
  });

  it("redirects an authenticated visitor to the dashboard instead of showing the message", () => {
    localStorage.setItem("auth_token", "test-token");

    renderPage();

    expect(screen.getByText("Dashboard")).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Konto zostało usunięte" }),
    ).not.toBeInTheDocument();
  });
});
