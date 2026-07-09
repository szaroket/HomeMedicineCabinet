import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getNotifications,
  dismissNotification,
} from "@/features/notifications/api/notifications-api";
import type {
  DismissNotificationPayload,
  NotificationItem,
} from "@/features/notifications/api/notifications-api";

export const notificationKeys = {
  all: () => ["notifications"] as const,
};

export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.all(),
    queryFn: getNotifications,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useDismissNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DismissNotificationPayload) =>
      dismissNotification(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all() });
    },
  });
}

export function useDismissAllNotifications() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: NotificationItem[]) =>
      Promise.allSettled(
        items.map((item) =>
          dismissNotification({
            cabinet_entry_id: item.cabinet_entry_id,
            trigger_type: item.trigger_type,
          }),
        ),
      ),
    // Re-sync regardless of partial failure: any dismissals that failed simply
    // reappear after invalidation, so the panel never shows a stale set.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all() });
    },
  });
}
