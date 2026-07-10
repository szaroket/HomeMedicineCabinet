import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  registerSchema,
  registerFormSchema,
} from "@/features/auth/schemas/auth-schemas";
import { useRegister } from "@/features/auth/api/auth-queries";
import { useNavigate } from "react-router-dom";
import type { RegisterFormValues } from "@/features/auth/schemas/auth-schemas";

export function RegisterForm() {
  const navigate = useNavigate();
  const { mutate, isPending } = useRegister();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerFormSchema),
  });

  function onSubmit(values: RegisterFormValues) {
    setServerError(null);
    mutate(registerSchema.parse(values), {
      onSuccess: () => navigate("/dashboard"),
      onError: (err) => {
        const status = err instanceof Response ? err.status : null;
        setServerError(
          status === 409
            ? "Konto z tym adresem e-mail już istnieje. Zaloguj się lub użyj innego adresu."
            : "Rejestracja nie powiodła się. Sprawdź dane i spróbuj ponownie.",
        );
      },
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
          autoComplete="new-password"
          className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          {...register("password")}
        />
        {errors.password && (
          <p className="text-xs text-red-400">{errors.password.message}</p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="confirmPassword"
          className="text-sm font-medium text-slate-300"
        >
          Powtórz hasło
        </label>
        <input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          className="rounded border border-slate-600 bg-slate-700 px-3 py-2 text-sm text-white placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          {...register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p className="text-xs text-red-400">
            {errors.confirmPassword.message}
          </p>
        )}
      </div>

      {serverError && <p className="text-sm text-red-400">{serverError}</p>}

      <button
        type="submit"
        disabled={isPending || !!errors.confirmPassword}
        className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600"
      >
        {isPending ? "Rejestracja…" : "Zarejestruj się"}
      </button>
    </form>
  );
}
