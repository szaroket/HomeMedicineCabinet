import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppSidebar } from "@/app/components/app-sidebar";

describe("AppSidebar", () => {
  it("renders a Panel główny link to /dashboard and marks it active only on the exact route", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <AppSidebar isOpen={false} onClose={() => {}} />
      </MemoryRouter>,
    );

    const dashboardLink = screen.getByRole("link", { name: "Panel główny" });
    expect(dashboardLink).toHaveAttribute("href", "/dashboard");
    expect(dashboardLink).toHaveAttribute("aria-current", "page");
  });

  it("does not mark Panel główny active on another route", () => {
    render(
      <MemoryRouter initialEntries={["/cabinet"]}>
        <AppSidebar isOpen={false} onClose={() => {}} />
      </MemoryRouter>,
    );

    const dashboardLink = screen.getByRole("link", { name: "Panel główny" });
    expect(dashboardLink).not.toHaveAttribute("aria-current", "page");
  });
});
