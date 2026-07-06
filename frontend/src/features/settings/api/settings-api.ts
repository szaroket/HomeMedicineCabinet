import { apiJson, apiFetch } from "@/lib/api-client";

export interface UserPreferences {
  expiry_threshold_days: number;
  close_to_finish_threshold_days: number;
  min_package_count: number;
}

export function getPreferences(): Promise<UserPreferences> {
  return apiJson<UserPreferences>("/users/preferences");
}

export interface UpdatePreferencesPayload {
  min_package_count: number;
}

export function updatePreferences(
  payload: UpdatePreferencesPayload,
): Promise<UserPreferences> {
  return apiJson<UserPreferences>("/users/preferences", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAccount(): Promise<void> {
  const res = await apiFetch("/users/me", { method: "DELETE" });
  if (!res.ok) throw res;
}
