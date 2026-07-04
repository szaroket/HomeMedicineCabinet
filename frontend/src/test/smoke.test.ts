import { describe, expect, it } from "vitest";
import { AuthError } from "@/lib/errors";

describe("vitest runner smoke test", () => {
  it("resolves the @/ alias and runs basic assertions", () => {
    const error = new AuthError();
    expect(error).toBeInstanceOf(AuthError);
    expect(error.message).toBe("Authentication required.");
  });

  it("resolves jest-dom matchers against a jsdom element", () => {
    const element = document.createElement("div");
    element.textContent = "hello";
    document.body.appendChild(element);

    expect(element).toBeInTheDocument();
    expect(element).toHaveTextContent("hello");
  });
});
