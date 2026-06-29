import { z } from "zod";

/** Cross-field dosage fields shared by the add and usage forms. */
interface DosageRuleFields {
  is_used?: boolean;
  is_tablet_based?: boolean | null;
  dosage_times?: number | null;
  dosage_period?: "day" | "week" | null;
  dosage_amount?: number | null;
  dosage_start_date?: string | null;
  dosage_end_date?: string | null;
}

/**
 * Shared superRefine body for the dosage cross-field rules. Used by both
 * addEntrySchema and usageSchema so the validation has a single source of truth.
 */
function refineDosageRules(data: DosageRuleFields, ctx: z.RefinementCtx): void {
  if (!data.is_used) return;

  if (!data.dosage_start_date) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["dosage_start_date"],
      message: "Podaj datę rozpoczęcia",
    });
  }

  if (data.is_tablet_based) {
    if (!data.dosage_times || data.dosage_times < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosage_times"],
        message: "Podaj liczbę dawek dziennych (min. 1)",
      });
    }
    if (!data.dosage_period) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosage_period"],
        message: "Wybierz okres dawkowania",
      });
    }
    if (!data.dosage_amount || data.dosage_amount < 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosage_amount"],
        message: "Podaj liczbę tabletek na dawkę (min. 1)",
      });
    }
  }

  if (data.dosage_start_date && data.dosage_end_date) {
    if (data.dosage_end_date < data.dosage_start_date) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["dosage_end_date"],
        message: "Data zakończenia musi być po dacie rozpoczęcia",
      });
    }
  }
}

export const addEntrySchema = z
  .object({
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
    is_important: z.boolean().optional(),
    is_tablet_based: z.boolean().optional(),
    is_used: z.boolean().optional(),
    dosage_times: z.number().int().min(1).max(24).nullable().optional(),
    dosage_period: z.enum(["day", "week"]).nullable().optional(),
    dosage_amount: z.number().int().min(1).max(100).nullable().optional(),
    dosage_start_date: z.string().nullable().optional(),
    dosage_end_date: z.string().nullable().optional(),
  })
  .superRefine(refineDosageRules);

export type AddEntryValues = z.infer<typeof addEntrySchema>;

export const usageSchema = z
  .object({
    is_used: z.boolean(),
    is_tablet_based: z.boolean().optional(),
    dosage_times: z.number().int().min(1).max(24).nullable().optional(),
    dosage_period: z.enum(["day", "week"]).nullable().optional(),
    dosage_amount: z.number().int().min(1).max(100).nullable().optional(),
    dosage_start_date: z.string().nullable().optional(),
    dosage_end_date: z.string().nullable().optional(),
  })
  .superRefine(refineDosageRules);

export type UsageValues = z.infer<typeof usageSchema>;
