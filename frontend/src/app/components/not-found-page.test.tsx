import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { NotFoundPage } from "@/app/components/not-found-page";

describe("NotFoundPage", () => {
  it("renders the Polish not-found heading and a link back to the home page", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Nie znaleziono strony" }),
    ).toBeVisible();

    const homeLink = screen.getByRole("link", {
      name: "Wróć do strony głównej",
    });
    expect(homeLink).toHaveAttribute("href", "/");
  });
});
