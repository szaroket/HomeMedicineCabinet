import { describe, expect, it } from "vitest";
import {
  registerFormSchema,
  registerSchema,
} from "@/features/auth/schemas/auth-schemas";

describe("registerFormSchema", () => {
  it("rejects a mismatched confirm password", () => {
    const result = registerFormSchema.safeParse({
      email: "user@example.com",
      password: "password123",
      confirmPassword: "different123",
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      const confirmError = result.error.issues.find(
        (issue) => issue.path.join(".") === "confirmPassword",
      );
      expect(confirmError?.message).toBe("Hasła muszą być takie same");
    }
  });

  it("accepts a matching confirm password", () => {
    const result = registerFormSchema.safeParse({
      email: "user@example.com",
      password: "password123",
      confirmPassword: "password123",
    });

    expect(result.success).toBe(true);
  });
});

describe("registerSchema strip", () => {
  it("drops confirmPassword when parsing form-shaped values", () => {
    const parsed = registerSchema.parse({
      email: "user@example.com",
      password: "password123",
      confirmPassword: "password123",
    });

    expect(parsed).toEqual({
      email: "user@example.com",
      password: "password123",
    });
    expect(parsed).not.toHaveProperty("confirmPassword");
  });
});
