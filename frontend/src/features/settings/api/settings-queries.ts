import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getPreferences,
  updatePreferences,
} from "@/features/settings/api/settings-api";

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
    mutationFn: (payload: { min_package_count: number }) =>
      updatePreferences(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.preferences() });
    },
  });
}
