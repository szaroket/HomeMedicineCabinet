import { z } from "zod";

export const updatePreferencesSchema = z.object({
  min_package_count: z
    .number()
    .int("Minimalna liczba opakowań musi być liczbą całkowitą.")
    .min(1, "Minimalna liczba opakowań wynosi 1.")
    .max(10, "Maksymalna liczba opakowań wynosi 10."),
});

export type UpdatePreferencesFormValues = z.infer<
  typeof updatePreferencesSchema
>;
