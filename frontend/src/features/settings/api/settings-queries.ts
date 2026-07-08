import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getPreferences,
  updatePreferences,
  deleteAccount,
  type UpdatePreferencesPayload,
} from "@/features/settings/api/settings-api";
import { clearStoredToken } from "@/features/auth/store";
import { notificationKeys } from "@/features/notifications/api/notifications-queries";
import { AuthError } from "@/lib/errors";

export const settingsKeys = {
  preferences: () => ["settings", "preferences"] as const,
};

export function usePreferences() {
  return useQuery({
    queryKey: settingsKeys.preferences(),
    queryFn: getPreferences,
  });
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdatePreferencesPayload) =>
      updatePreferences(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.preferences() });
      // Thresholds govern which alerts fire, so a save can change the active
      // notification set — mirror the cabinet mutation cross-feature
      // invalidation (Phase 6 §2) to keep the bell fresh.
      queryClient.invalidateQueries({ queryKey: notificationKeys.all() });
    },
  });
}

// Deletion is a Supabase-side (non-DB) failure that lands *after* the local
// commit — local data is already gone, so the session is torn down on both
// success and this 5xx. A 503 (local delete failed) leaves everything intact,
// so it does not tear down.
//
// Navigation to /account-deleted is a hard browser redirect from the calling
// component (see delete-account-section.tsx), not a router `navigate()` — and
// teardown here uses `clearStoredToken()` rather than `clearSession()` for the
// same reason: flipping React auth state would re-render ProtectedLayout with
// a null token and flash its own client-side `<Navigate to="/login" />`
// before the hard redirect takes over. Since the whole app remounts on the
// hard navigation anyway, clearing the stored token is sufficient — there is
// no stale React state to clean up.
export function useDeleteAccount() {
  const queryClient = useQueryClient();

  return useMutation<void, Response | AuthError>({
    mutationFn: deleteAccount,
    onSuccess: () => {
      clearStoredToken();
      queryClient.clear();
    },
    onError: (error) => {
      if (error instanceof Response && error.status === 502) {
        clearStoredToken();
        queryClient.clear();
      }
    },
  });
}
