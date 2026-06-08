import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(1, "Hasło jest wymagane"),
});

export const registerSchema = z.object({
  email: z.string().email("Podaj poprawny adres e-mail"),
  password: z.string().min(8, "Hasło musi mieć co najmniej 8 znaków"),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;
