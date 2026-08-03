import { z } from "zod";

export const updatePreferencesSchema = z.object({
  expiryThresholdDays: z
    .number({ error: "Podaj liczbę dni." })
    .int("Próg ważności musi być liczbą całkowitą.")
    .min(7, "Minimalny próg ważności wynosi 7 dni.")
    .max(90, "Maksymalny próg ważności wynosi 90 dni."),
  closeToFinishThresholdDays: z
    .number({ error: "Podaj liczbę dni." })
    .int("Próg kończącego się zapasu musi być liczbą całkowitą.")
    .min(1, "Minimalny próg kończącego się zapasu wynosi 1 dzień."),
  minPackageCount: z
    .number({ error: "Podaj liczbę opakowań." })
    .int("Minimalna liczba opakowań musi być liczbą całkowitą.")
    .min(1, "Minimalna liczba opakowań wynosi 1.")
    .max(10, "Maksymalna liczba opakowań wynosi 10."),
});

export type UpdatePreferencesFormValues = z.infer<
  typeof updatePreferencesSchema
>;
