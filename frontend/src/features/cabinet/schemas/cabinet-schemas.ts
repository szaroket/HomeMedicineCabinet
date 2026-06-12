import { z } from "zod";

export const addEntrySchema = z.object({
  medication_registry_id: z.string().uuid("Wybierz wariant leku"),
  package_count: z
    .number()
    .int("Podaj liczbę całkowitą")
    .min(1, "Minimalna liczba opakowań to 1"),
  expiry_date: z.string().min(1, "Podaj termin ważności"),
  partial_tablet_count: z
    .number()
    .int("Podaj liczbę całkowitą")
    .min(1, "Minimalna liczba tabletek to 1")
    .nullable()
    .optional(),
});

export type AddEntryValues = z.infer<typeof addEntrySchema>;
