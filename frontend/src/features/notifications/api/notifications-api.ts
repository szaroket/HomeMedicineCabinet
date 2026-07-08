import { apiFetch, apiJson } from "@/lib/api-client";

export type TriggerType = "expiry" | "below_minimum" | "run_out";

export interface NotificationItem {
  trigger_type: TriggerType;
  cabinet_entry_id: string;
  medication_name: string;
  days_remaining: number | null;
}

export interface NotificationListOut {
  items: NotificationItem[];
}

export function getNotifications(): Promise<NotificationListOut> {
  return apiJson<NotificationListOut>("/notifications");
}

export interface DismissNotificationPayload {
  cabinet_entry_id: string;
  trigger_type: TriggerType;
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
