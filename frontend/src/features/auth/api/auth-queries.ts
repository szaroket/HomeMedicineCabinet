import { useMutation, useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/store";
import { login, register, logout, getMe } from "@/features/auth/api/auth-api";
import type {
  LoginValues,
  RegisterValues,
} from "@/features/auth/schemas/auth-schemas";

export const authKeys = {
  me: () => ["auth", "me"] as const,
};

export function useLogin() {
  const { setSession } = useAuth();
  return useMutation({
    mutationFn: (data: LoginValues) => login(data),
    onSuccess: (res) => setSession(res.access_token, res.user),
  });
}

export function useRegister() {
  const { setSession } = useAuth();
  return useMutation({
    mutationFn: (data: RegisterValues) => register(data),
    onSuccess: (res) => setSession(res.access_token, res.user),
  });
}

export function useLogout() {
  const { clearSession } = useAuth();
  return useMutation({
    mutationFn: logout,
    onSettled: () => clearSession(),
  });
}

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: authKeys.me(),
    queryFn: getMe,
    enabled,
    retry: false,
  });
}
