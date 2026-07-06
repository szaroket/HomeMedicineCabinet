import { useEffect } from "react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/features/auth/store";
import { DeleteAccountSection } from "@/features/settings/components/delete-account-section";

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

function renderSection(email = "user@example.com") {
  const queryClient = new QueryClient();
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SignedInAs email={email}>
            <DeleteAccountSection />
          </SignedInAs>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("DeleteAccountSection", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("disables the confirm button until the typed value matches the account email, then triggers the delete mutation", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
    const user = userEvent.setup();
    renderSection("user@example.com");

    await user.click(screen.getByRole("button", { name: "Usuń konto" }));

    const confirmButton = screen.getByRole("button", {
      name: "Usuń konto trwale",
    });
    expect(confirmButton).toBeDisabled();

    const input = screen.getByLabelText("Adres e-mail");
    await user.type(input, "wrong@example.com");
    expect(confirmButton).toBeDisabled();

    await user.clear(input);
    await user.type(input, "user@example.com");
    expect(confirmButton).toBeEnabled();

    await user.click(confirmButton);

    expect(fetch).toHaveBeenCalledTimes(1);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.method).toBe("DELETE");
  });
});
