import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AccountDeletedPage } from "@/features/auth/components/account-deleted-page";

describe("AccountDeletedPage", () => {
  it("renders the full-deletion message and a Powrót link to /login by default", () => {
    render(
      <MemoryRouter>
        <AccountDeletedPage />
      </MemoryRouter>,
    );

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
    render(
      <MemoryRouter initialEntries={["/account-deleted?partial=1"]}>
        <AccountDeletedPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByText(
        "Konto zostało częściowo usunięte — zaloguj się ponownie, aby dokończyć.",
      ),
    ).toBeVisible();
  });
});
