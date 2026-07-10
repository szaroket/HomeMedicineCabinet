import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { WelcomePage } from "@/features/landing/components/welcome-page";

function renderWelcomePage() {
  render(
    <MemoryRouter>
      <WelcomePage />
    </MemoryRouter>,
  );
}

describe("WelcomePage", () => {
  it("renders the app headline", () => {
    renderWelcomePage();

    expect(
      screen.getByRole("heading", { name: "Apteczka domowa" }),
    ).toBeVisible();
  });

  it("renders a link to register", () => {
    renderWelcomePage();

    expect(
      screen.getByRole("link", { name: "Zarejestruj się" }),
    ).toHaveAttribute("href", "/register");
  });

  it("renders a link to log in", () => {
    renderWelcomePage();

    expect(screen.getByRole("link", { name: "Zaloguj się" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it.each([
    "Czyste dane z rejestru",
    "Przypomnienia o terminach i zapasach",
    "Śledzenie dawkowania",
    "Panel w jednym miejscu",
  ])("renders the highlight heading %s", (title) => {
    renderWelcomePage();

    expect(screen.getByRole("heading", { name: title })).toBeVisible();
  });
});
