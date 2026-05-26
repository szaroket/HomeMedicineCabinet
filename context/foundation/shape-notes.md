---
project: Home Medicine Cabinet
context_type: greenfield
updated: 2026-05-26
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  frs_drafted: 12
  quality_check_status: accepted
timeline_budget:
  mvp_weeks: 2
  hard_deadline: "2026-07-05"
  hard_deadline_fallback: "2026-08-10"
  after_hours_only: true
product_type: web-app
target_scale:
  users: small
---

## Vision & Problem Statement

A single adult managing their own medications cannot reliably track what is in their home medicine cabinet — what they have, how many packages remain, and when things expire. The pain is sharpest at the pharmacy: standing in the aisle, unsure whether they already have a medication at home. The cost today is duplicate purchases and discovering expired medications too late.

Existing apps fail because they rely on free-text entry, which produces inconsistent, typo-ridden records that erode trust in the data. A medication cabinet app backed by the Polish-approved medications registry solves the data quality problem at the root.

## User & Persona

**Primary persona**: A single adult managing their own medications. Not a medical professional. Uses a web browser on both desktop and mobile. Wants a fast answer to "do I have this?" before or during a pharmacy visit.

## Access Control

- Registration: email address + password
- Authentication: login / logout
- Role model: flat single-role (all registered accounts are equal users)
- No admin UI in MVP

## Success Criteria

### Primary
- User can find any medication in the Polish-approved registry and add it to their cabinet (with tablet count, package count, and expiry date) in a single flow
- User receives an email notification before a configured medication expires, based on their threshold setting

### Secondary
- User returns to check their cabinet at least once a week without an external prompt (signals genuine habit formation)

### Guardrails
- Search and autocomplete return correct medication matches ≥ 95% of the time — wrong suggestions corrupt cabinet data
- One user's cabinet data is never visible to another user

## Functional Requirements

### Authentication
- FR-001: User can register with an email address and password. Priority: must-have
  > Socrates: Counter-argument considered: "skip registration; store data locally." Resolution: kept — data must persist across devices and browsers; local storage is too fragile.

- FR-002: User can log in and log out. Priority: must-have
  > Socrates: Counter-argument considered: "logout is rarely used in personal apps." Resolution: kept — logout is a basic security requirement inseparable from any auth system.

### Adding Medications
- FR-003: User can add a medication by typing a name, selecting from an autocomplete dropdown sourced from the Polish-approved medications list, selecting tablet count (from official dataset), entering number of packages, and setting an expiry date. Priority: must-have
  > Socrates: Counter-argument considered: "official dataset may be stale or missing newly approved drugs." Resolution: kept — constraining to the approved list is the core differentiator; data quality is the product. Manual fallback deferred to v2.

- FR-010: When adding a medication, if an entry with the same drug + tablet count + expiry date already exists, the system increments its package count instead of creating a duplicate. Priority: must-have
  > Socrates: Counter-argument considered: "silently merging could hide a different expiry batch." Resolution: updated — deduplication key is drug + tablet count + expiry date (three-field match); differing expiry date creates a new entry.

### Cabinet Management
- FR-004: User can view their cabinet as a list with filtering by status (valid / expiring / expired), sorting by medication name, and pagination. Priority: must-have
  > Socrates: Counter-argument considered: "flat unordered list is sufficient; search covers discovery." Resolution: updated — filtering by status and pagination added for usability at scale; sort by name added per user requirement.

- FR-005: User can increase or decrease the package count on a cabinet entry, or delete it entirely. Priority: must-have
  > Socrates: Counter-argument considered: "no expiry date editing means batch changes are unrecordable." Resolution: kept — different expiry batches are separate entries added via FR-003; this keeps the edit scope intentionally narrow.

- FR-006: User can search their cabinet by free text matched against medication name or active ingredient. Priority: must-have
  > Socrates: Counter-argument considered: "users may want to search the full registry, not just their cabinet." Resolution: kept — cabinet-only search is MVP scope; registry browsing deferred to v2.

### Notifications
- FR-007: User can set a global notification threshold (7–90 days before expiry) and a preferred notification frequency (once / every 3 days / weekly). Priority: must-have
  > Socrates: Counter-argument considered: "one global threshold ignores critical medications (e.g. EpiPen)." Resolution: kept — single global threshold is sufficient for MVP; per-entry overrides deferred to v2.

- FR-008: User receives email notifications at their configured frequency while a medication is within the expiry threshold window; when fewer than 7 days remain until expiry, the system automatically escalates to daily notifications regardless of the user's frequency setting. Priority: must-have
  > Socrates: Counter-argument considered: "email requires background scheduler + email delivery service, adding infrastructure cost." Resolution: kept — email is the only viable async notification channel for a web-only app; infrastructure cost is accepted.

### Dashboard
- FR-009: Dashboard shows summary counts: total medications / valid / expiring soon / expired. Priority: must-have
  > Socrates: Counter-argument considered: "dashboard duplicates the filtered list (FR-004)." Resolution: kept — dashboard is the landing screen; at-a-glance counts are the primary value moment on open.

### Medication Details
- FR-011: Each cabinet entry displays the producer and route of administration (method of use) sourced from the official dataset. Priority: must-have
  > Socrates: Resolution: updated — display producer and route of administration only; general manufacturer field dropped as redundant.

- FR-012: Each cabinet entry displays links to the drug leaflet and specification sourced from the official dataset. Priority: must-have. Inline PDF preview: nice-to-have (v2).
  > Socrates: Counter-argument considered: "inline PDF preview is non-trivial across browsers." Resolution: links only for MVP; inline preview deferred to v2.

## User Stories

### US-01: Add a medication to the cabinet
**Given** a logged-in user on the add medication screen  
**When** they type a medication name, select from the autocomplete dropdown, choose a tablet count, enter a package count, and set an expiry date  
**Then** the medication appears in their cabinet with the correct status classification (valid / expiring / expired)

### US-02: Receive expiry notification
**Given** a user has set a notification threshold and has a medication expiring within that window  
**When** the scheduled notification check runs  
**Then** the user receives an email listing the medication name and days remaining before expiry

### US-03: Check cabinet at the pharmacy
**Given** a logged-in user on a mobile browser  
**When** they search their cabinet by medication name or active ingredient  
**Then** matching entries are returned quickly enough to use while standing at the pharmacy counter

## Business Logic

The system classifies each cabinet entry as valid, expiring soon, or expired — based on the user's configured threshold — and proactively alerts the user before a medication becomes unusable, escalating notification frequency automatically when expiry is imminent.

**Inputs**: expiry date recorded on each cabinet entry; user's configured notification threshold (7–90 days) and preferred frequency (once / every 3 days / weekly).  
**Output**: status classification per entry (valid / expiring soon / expired); recurring email alerts at the user's configured frequency while within the threshold window; automatic escalation to daily alerts when fewer than 7 days remain.  
**User encounter**: status is visible on every cabinet list row and in the dashboard counts; emails arrive per the configured schedule, with the system silently switching to daily cadence in the final 7-day window.

## Non-Functional Requirements

- The app must be fully usable on mobile browsers (responsive layout); web-only, no native app required
- Search and autocomplete must return results with no perceptible lag (user-perceived response < 500ms p95)
- One user's cabinet data must never be visible to another user (strict per-account data isolation)

## Non-Goals

- No native mobile app (iOS/Android) — web-only for MVP
- No multi-profile or household member support — one cabinet per account; no assigning medications to family members
- No prescription checking — the app tracks inventory, not prescriptions
- No photo, barcode, or document scanning for adding medications — manual entry via approved list only

## Open Questions

_(none at close of shaping — all gaps resolved during discovery)_
