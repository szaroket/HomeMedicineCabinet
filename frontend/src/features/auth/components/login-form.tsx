import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { loginSchema } from "@/features/auth/schemas/auth-schemas";
import { useLogin } from "@/features/auth/api/auth-queries";
import { useNavigate } from "react-router-dom";
import type { LoginValues } from "@/features/auth/schemas/auth-schemas";

export function LoginForm() {
  const navigate = useNavigate();
  const { mutate, isPending } = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  function onSubmit(values: LoginValues) {
    setServerError(null);
    mutate(values, {
      onSuccess: () => navigate("/"),
      onError: () =>
        setServerError("Nieprawidłowy e-mail lub hasło. Spróbuj ponownie."),
    });
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="email" className="text-sm font-medium text-slate-300">
          Adres e-mail
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          {...register("email")}
        />
        {errors.email && (
          <p className="text-xs text-red-400">{errors.email.message}</p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="password"
          className="text-sm font-medium text-slate-300"
        >
          Hasło
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          {...register("password")}
        />
        {errors.password && (
          <p className="text-xs text-red-400">{errors.password.message}</p>
        )}
      </div>

      {serverError && <p className="text-sm text-red-400">{serverError}</p>}

      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {isPending ? "Logowanie…" : "Zaloguj się"}
      </button>
    </form>
  );
}
