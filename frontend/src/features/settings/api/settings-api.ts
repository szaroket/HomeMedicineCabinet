import { apiJson, apiFetch } from "@/lib/api-client";

export interface UserPreferences {
  expiryThresholdDays: number;
  closeToFinishThresholdDays: number;
  minPackageCount: number;
}

export function getPreferences(): Promise<UserPreferences> {
  return apiJson<UserPreferences>("/users/preferences");
}

export interface UpdatePreferencesPayload {
  expiryThresholdDays: number;
  closeToFinishThresholdDays: number;
  minPackageCount: number;
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
