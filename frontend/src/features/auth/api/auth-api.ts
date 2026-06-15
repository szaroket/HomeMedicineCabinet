import { apiJson, apiFetch } from "@/lib/api-client";
import type {
  LoginValues,
  RegisterValues,
} from "@/features/auth/schemas/auth-schemas";

export interface AuthUser {
  id: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export function register(data: RegisterValues): Promise<AuthResponse> {
  return apiJson<AuthResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function login(data: LoginValues): Promise<AuthResponse> {
  return apiJson<AuthResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<AuthUser> {
  return apiJson<AuthUser>("/auth/me");
}
