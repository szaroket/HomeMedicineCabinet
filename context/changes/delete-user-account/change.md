---
change_id: delete-user-account
title: Delete user account
status: implemented
created: 2026-07-04
updated: 2026-07-06
archived_at: null
---

## Notes

<!-- Free-form notes for this change: links, ad-hoc context, decisions that don't belong in research/frame/plan. -->

- **Phase 3 adaptation**: plan §3/§Testing Strategy described redirecting to
  `/login` with a Polish notice. As built, success and the partial-deletion
  (502) case instead redirect to a dedicated `/account-deleted` page (mirrors
  `NotFoundPage`, with a "Powrót" link back to `/login`), via a **hard**
  `window.location.href` redirect rather than router `navigate()`, and using a
  new `clearStoredToken()` (plain `localStorage.removeItem`, no React state
  change) instead of `clearSession()`. Both changes exist because
  `ProtectedLayout` issues its own unstated `<Navigate to="/login" replace />`
  the instant the token flips to null — a client-side `navigate()` combined
  with `clearSession()`'s state update raced against that redirect and lost,
  stranding the user on `/login` (sometimes after a visible flash). The hard
  redirect + storage-only token clear sidesteps the race entirely.
