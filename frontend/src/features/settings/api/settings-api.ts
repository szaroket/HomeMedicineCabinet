import { apiJson } from "@/lib/api-client";

export interface UserPreferences {
  expiry_threshold_days: number;
  close_to_finish_threshold_days: number;
  min_package_count: number;
}

export function getPreferences(): Promise<UserPreferences> {
  return apiJson<UserPreferences>("/users/preferences");
}

export function updatePreferences(payload: {
  min_package_count: number;
}): Promise<UserPreferences> {
  return apiJson<UserPreferences>("/users/preferences", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
