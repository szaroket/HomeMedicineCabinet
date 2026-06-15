---
change_id: add-medication-from-registry
title: Add medication from Polish registry with autocomplete and dedup
status: impl_reviewed
created: 2026-06-09
updated: 2026-06-15
last_review: reviews/impl-review-phase-7.md
archived_at: null
---

## Notes

Sourced from roadmap S-01. User can type a medication name, select from the autocomplete dropdown sourced from the Polish registry, choose tablet count, enter package count (≥ 1), and set an expiry date; the entry appears in their cabinet with the correct status classification (valid / expiring soon / expired); adding the same drug + tablet count + expiry date a second time merges the entries per the deduplication and normalisation rule (FR-010).
