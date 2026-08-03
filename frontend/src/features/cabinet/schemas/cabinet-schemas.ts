import { z } from "zod";

/** Cross-field dosage fields shared by the add and usage forms. */
interface DosageRuleFields {
  isUsed?: boolean;
  isTabletBased?: boolean | null;
  dosageTimes?: number | null;
  dosagePeriod?: "day" | "week" | null;
  dosageAmount?: number | null;
  dosageStartDate?: string | null;
  dosageEndDate?: string | null;
}

/**
 * Shared superRefine body for the dosage cross-field rules. Used by both
 * addEntrySchema and usageSchema so the validation has a single source of truth.
 */
function refineDosageRules(data: DosageRuleFields, ctx: z.RefinementCtx): void {
  if (!data.isUsed) return;

  if (!data.dosageStartDate) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["dosageStartDate"],
      message: "Podaj datę rozpoczęcia",
    });
  }

  if (data.isTabletBased) {
    if (!data.dosageTimes || data.dosageTimes < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosageTimes"],
        message: "Podaj liczbę dawek dziennych (min. 1)",
      });
    }
    if (!data.dosagePeriod) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosagePeriod"],
        message: "Wybierz okres dawkowania",
      });
    }
    if (!data.dosageAmount || data.dosageAmount < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosageAmount"],
        message: "Podaj liczbę tabletek na dawkę (min. 1)",
      });
    }
  }

  if (data.dosageStartDate && data.dosageEndDate) {
    if (data.dosageEndDate < data.dosageStartDate) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosageEndDate"],
        message: "Data zakończenia musi być po dacie rozpoczęcia",
      });
    }
  }
}

export const addEntrySchema = z
  .object({
    medicationRegistryId: z.string().uuid("Wybierz wariant leku"),
    packageCount: z
      .number()
      .int("Podaj liczbę całkowitą")
      .min(1, "Minimalna liczba opakowań to 1"),
    expiryDate: z.string().min(1, "Podaj termin ważności"),
    partialTabletCount: z
      .number()
      .int("Podaj liczbę całkowitą")
      .min(1, "Minimalna liczba tabletek to 1")
      .nullable()
      .optional(),
    isImportant: z.boolean().optional(),
    isTabletBased: z.boolean().optional(),
    isUsed: z.boolean().optional(),
    dosageTimes: z.number().int().min(1).max(24).nullable().optional(),
    dosagePeriod: z.enum(["day", "week"]).nullable().optional(),
    dosageAmount: z.number().int().min(1).max(100).nullable().optional(),
    dosageStartDate: z.string().nullable().optional(),
    dosageEndDate: z.string().nullable().optional(),
  })
  .superRefine(refineDosageRules);

export type AddEntryValues = z.infer<typeof addEntrySchema>;

export const usageSchema = z
  .object({
    isUsed: z.boolean(),
    isTabletBased: z.boolean().optional(),
    dosageTimes: z.number().int().min(1).max(24).nullable().optional(),
    dosagePeriod: z.enum(["day", "week"]).nullable().optional(),
    dosageAmount: z.number().int().min(1).max(100).nullable().optional(),
    dosageStartDate: z.string().nullable().optional(),
    dosageEndDate: z.string().nullable().optional(),
  })
  .superRefine(refineDosageRules);

export type UsageValues = z.infer<typeof usageSchema>;
