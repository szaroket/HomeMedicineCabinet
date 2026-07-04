# Follow-ups from impl-review

## App-wide cabinet mutation error surfacing (from F5)

**Source**: impl-review F5 — "No user-visible error on a failed stepper/delete mutation".

The impl-review fixed only the higher-stakes **delete** path (red `error` slot on
`ConfirmDialog`, wired via `deleteEntry` `onError`). The broader gap remains:

- `useUpdateQuantity` failures (increment / decrement / partial-tablet edit) are
  still swallowed — the count silently doesn't move and the buttons re-enable.
- Sibling mutations `useToggleImportant` / `useSetUsage` have the same gap; this
  is a pre-existing, app-wide pattern, not something this slice introduced.

**Recommended fix**: introduce a shared toast / notification layer (no such infra
exists today) and route `onError` from every cabinet mutation through it, rather
than sprinkling per-entry error strings. Doing it per-component now would create
throwaway code a toast layer would later remove.

**Scope**: cross-cutting, out of the manage-cabinet-entry slice. Prioritize
alongside any future error-handling / notifications work.
