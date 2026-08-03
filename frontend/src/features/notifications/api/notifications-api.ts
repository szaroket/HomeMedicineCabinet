import { apiFetch, apiJson } from "@/lib/api-client";

export type TriggerType = "expiry" | "below_minimum" | "run_out";

export interface NotificationItem {
  triggerType: TriggerType;
  cabinetEntryId: string;
  medicationName: string;
  daysRemaining: number | null;
}

export interface NotificationListOut {
  items: NotificationItem[];
}

export function getNotifications(): Promise<NotificationListOut> {
  return apiJson<NotificationListOut>("/notifications/");
}

export interface DismissNotificationPayload {
  cabinetEntryId: string;
  triggerType: TriggerType;
}

export async function dismissNotification(
  payload: DismissNotificationPayload,
): Promise<void> {
  const res = await apiFetch("/notifications/dismiss", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw res;
}
