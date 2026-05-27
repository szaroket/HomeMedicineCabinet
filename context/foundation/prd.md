---
project: Home Medicine Cabinet
version: 1
status: draft
created: 2026-05-27
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 2
  hard_deadline: "2026-07-05"
  after_hours_only: true
---

## Vision & Problem Statement

A single adult managing their own medications cannot reliably track what is in their home medicine cabinet — what they have, how many packages remain, when things expire, and whether they have enough of what they are currently taking. The pain is sharpest at the pharmacy: standing in the aisle, unsure whether they already have a medication at home, or when their current supply will run out. The cost today is duplicate purchases, discovering expired medications too late, and running out of an active medication mid-course.

Existing apps fail because they rely on free-text entry, which produces inconsistent, typo-ridden records that erode trust in the data. A medication cabinet app backed by the Polish-approved medications registry solves the data quality problem at the root.

## User & Persona

**Primary persona**: A single adult managing their own medications. Not a medical professional. Uses a web browser on both desktop and mobile. Wants a fast answer to "do I have this?" and "will I run out before my next doctor visit?" before or during a pharmacy visit.

## Success Criteria

### Primary
- User can find any medication in the Polish-approved registry and add it to their cabinet (with tablet count, package count, and expiry date) in a single flow
- User receives an in-app notification when a medication is close to expiry, when an important medication falls below the configured minimum, or when a used medication is close to its estimated finish date

### Secondary
- User returns to check their cabinet at least once a week without an external prompt (signals genuine habit formation)

### Guardrails
- Search and autocomplete return correct medication matches ≥ 95% of the time — wrong suggestions corrupt cabinet data
- One user's cabinet data is never visible to another user
- Dosage-based finish-date calculations must clearly display their assumptions so the user can trust or override them

## User Stories

### US-01: Add a medication to the cabinet

**Given** a logged-in user on the add medication screen  
**When** they type a medication name, select from the autocomplete dropdown, choose a tablet count, enter a package count (≥ 1), and set an expiry date  
**Then** the medication appears in their cabinet with the correct status classification (valid / expiring / expired)

#### Acceptance Criteria
- Package count of 0 is rejected at input — minimum is 1 (FR-022)
- Medication name and tablet count options are sourced from the Polish-approved registry, not free text (FR-003)
- If the same drug + tablet count + expiry date already exists, the system increments the package count rather than creating a duplicate (FR-010)
- Status classification (valid / expiring / expired) is computed immediately on add based on the user's configured expiry threshold (FR-007)

### US-02: Receive in-app notification for expiry

**Given** a user has set a notification threshold and has a medication expiring within that window  
**When** they open the application  
**Then** the notification bell shows an unread count and the notification center lists the medication name and days remaining before expiry

#### Acceptance Criteria
- Notification center is accessible via a bell icon showing unread count (FR-008)
- Each notification names the medication and the specific condition triggering it (FR-008)
- Notification persists in the center until the triggering condition is resolved (FR-019)

### US-03: Check cabinet at the pharmacy

**Given** a logged-in user on a mobile browser  
**When** they search their cabinet by medication name or active ingredient  
**Then** matching entries are returned quickly enough to use while standing at the pharmacy counter

#### Acceptance Criteria
- Search matches on medication name and on active ingredient (FR-006)
- Results are returned within user-perceived acceptable response time for a time-pressured pharmacy context (NFR: < 500 ms p95)
- The cabinet list is navigable on a mobile browser without horizontal scrolling (NFR: responsive layout)

### US-04: Track an active medication course

**Given** a logged-in user who has added a tablet-based medication  
**When** they assign it to the "used" category with frequency (3 times/day), dosage (1 tablet per intake), and no end date  
**Then** the cabinet entry displays the estimated finish date and a notification appears in the notification center when the finish date falls within the configured close-to-finish threshold

#### Acceptance Criteria
- Dosage fields (times, period, tablets per dose) are shown only for tablet-based medications; non-tablet medications show start/end date fields only (FR-015)
- Estimated finish date = (package count × tablets per package) ÷ daily consumption rate, where daily consumption rate = (times × dosage per intake) ÷ period in days (FR-016)
- Notification appears in the notification center when estimated finish date is within the user-configured close-to-finish threshold (FR-019)
- Both "used" and "important" categories can be active simultaneously on the same entry (FR-013)

### US-05: Important medication below minimum

**Given** a user has marked a medication as "important" and set a global minimum of 2 packages  
**When** the package count on that entry drops to 1  
**Then** the entry displays an "out of stock" badge and an in-app notification appears in the notification center

#### Acceptance Criteria
- "Out of stock" badge is computed automatically — no manual action required (FR-020)
- Badge clears automatically when the package count rises to or above the minimum (FR-020)
- In-app notification names the medication and the reason: below minimum (FR-008)
- If the user deletes the entry, a confirmation dialog states the entry will also be removed from any active "out of stock" state (FR-005)

## Functional Requirements

### Authentication
- FR-001: User can register with an email address and password. Priority: must-have
  > Socrates: Counter-argument considered: "skip registration; store data locally." Resolution: kept — data must persist across devices and browsers; local storage is too fragile.

- FR-002: User can log in and log out. Priority: must-have
  > Socrates: Counter-argument considered: "logout is rarely used in personal apps." Resolution: kept — logout is a basic security requirement inseparable from any auth system.

### Adding Medications
- FR-003: User can add a medication by typing a name, selecting from an autocomplete dropdown sourced from the Polish-approved medications list, selecting tablet count (from official dataset), entering number of packages (minimum 1; 0 packages is not a valid starting value), and setting an expiry date. Priority: must-have
  > Socrates: Counter-argument considered: "official dataset may be stale or missing newly approved drugs." Resolution: kept — constraining to the approved list is the core differentiator; data quality is the product. Manual fallback deferred to v2.

- FR-010: When adding a medication, if an entry with the same drug + tablet count + expiry date already exists, the system increments its package count instead of creating a duplicate. Priority: must-have
  > Socrates: Counter-argument considered: "silently merging could hide a different expiry batch." Resolution: updated — deduplication key is drug + tablet count + expiry date (three-field match); differing expiry date creates a new entry.

### Cabinet Management
- FR-004: User can view their cabinet as a list with filtering by status (valid / expiring / expired / out-of-stock badge), sorting by medication name, and pagination. Priority: must-have
  > Socrates: Counter-argument considered: "flat unordered list is sufficient; search covers discovery." Resolution: updated — filtering by status and pagination added for usability at scale; sort by name added per user requirement.

- FR-005: User can increase or decrease the package count on a cabinet entry, or delete it. Deleting requires explicit confirmation; if the entry carries an "out of stock" badge, the confirmation states it will also be cleared. Priority: must-have
  > Socrates: Counter-argument considered: "no expiry date editing means batch changes are unrecordable." Resolution: kept — different expiry batches are separate entries added via FR-003; this keeps the edit scope intentionally narrow.

- FR-006: User can search their cabinet by free text matched against medication name or active ingredient. Priority: must-have
  > Socrates: Counter-argument considered: "users may want to search the full registry, not just their cabinet." Resolution: kept — cabinet-only search is MVP scope; registry browsing deferred to v2.

### Medication Categories
- FR-013: User can assign a medication entry to the "important" category. A medication can simultaneously hold both "important" and "used" categories. Priority: must-have
  > Socrates: Counter-argument considered: "important flag without per-entry minimum is too coarse — EpiPen and ibuprofen deserve different thresholds." Resolution: kept for MVP — one global minimum applies to all important medications; per-entry overrides deferred to v2.

- FR-014: User can set a global minimum package count for "important" medications (minimum value: 1; same threshold applies to all important medications in MVP). Priority: must-have
  > Socrates: Counter-argument considered: "one global minimum means the system can't distinguish truly critical drugs (must always have 2) from low-priority ones." Resolution: accepted tradeoff — single global value keeps the settings screen simple; per-entry minimum deferred to v2.

- FR-015: User can assign a medication entry to the "used" category with start date (default: date of assignment) and an optional end date. For tablet-based medications (those with a tablet count from the registry), three additional dosage fields are shown: (1) how many times (integer), (2) period — per day or per week, (3) dosage amount per intake (integer, in tablets). Example: "3 × 2 tablets per day". For non-tablet medications (e.g. syrups, without a tablet count), the dosage fields are hidden and no finish-date calculation is available. Priority: must-have
  > Socrates: Counter-argument considered: "variable dosing (e.g. 1 tablet some days, 2 on others) cannot be captured as fixed frequency + period." Resolution: accepted — fixed schedule is the MVP approximation; the system displays the assumption explicitly so the user can judge accuracy. Separate UI fields (times / period / dosage) make the structure clear.

- FR-016: For tablet-based medications in the "used" category (dosage fields present), the system calculates the estimated finish date. Daily consumption rate = (times × dosage amount) ÷ period in days (1 for per-day, 7 for per-week). Days of supply = (package count × tablets per package) ÷ daily consumption rate. For non-tablet medications assigned to "used", no finish-date calculation is shown. Priority: must-have
  > Socrates: Counter-argument considered: "calculation assumes full packages and consistent dosing; a half-used package or a skipped day will make the estimate wrong." Resolution: kept — the estimate is displayed with its assumptions; accuracy depends on the user keeping package count current, which they already do via FR-005.

- FR-017: For "used" medications with an end date, the system displays whether the current stock is sufficient to last until that date. Priority: must-have
  > Socrates: Counter-argument considered: "'sufficient' is ambiguous — does it mean exactly enough, or with buffer?" Resolution: the system shows exact days remaining vs. days of supply, letting the user judge sufficiency; no buffer is computed by the system.

- FR-018: For "used" medications with no end date, the system displays the calculated estimated finish date. Priority: must-have
  > Socrates: Counter-argument considered: "without an end date the finish date is only useful if the user acts on it — otherwise it's just a number." Resolution: kept — the estimated finish date is the input for the close-to-finish notification (FR-019); it is also useful at the pharmacy when deciding whether to restock.

### Notifications (In-App)
- FR-007: User can configure notification settings: expiry alert threshold (7–90 days before expiry) and close-to-finish threshold (days before estimated run-out for "used" medications). Priority: must-have
  > Socrates: Counter-argument considered: "two separate thresholds in settings adds cognitive load." Resolution: kept — expiry and finish-date concerns are distinct and the user may want different sensitivity for each (e.g. 14 days for expiry, 7 days for run-out).

- FR-008: The system delivers in-app notifications via a notification center (bell icon with unread count) triggered by: (a) a medication entering the expiry threshold window; (b) an "important" medication's package count falling below the configured minimum; (c) a "used" medication's estimated finish date falling within the close-to-finish threshold. Priority: must-have
  > Socrates: Counter-argument considered: "in-app notifications are only seen when the user opens the app — they may miss time-sensitive alerts." Resolution: accepted for MVP — the product is web-only and the persona checks the app regularly; push/email notifications deferred to v2.

- FR-019: The system shows an in-app notification when a "used" medication's estimated finish date is within the user-configured close-to-finish threshold. Priority: must-have
  > Socrates: Counter-argument considered: "notification fires repeatedly until restocked, which could become noise." Resolution: notification persists in the notification center until the condition is resolved (restocked or category removed); no repeated re-firing once shown.

### Out of Stock Status
- FR-020: The system automatically displays an "out of stock" badge on an "important" medication entry when any of these conditions hold: (a) the medication is close to expiry (within expiry threshold) or expired; (b) package count is below the user-configured minimum. The badge is computed — it clears automatically when conditions no longer hold. Priority: must-have
  > Socrates: Counter-argument considered: "a drug expiring soon but with many packages isn't really out of stock — the label is misleading." Resolution: "out of stock" is a working name; the badge surfaced to the user communicates the specific condition (expiring / expired / below minimum), not a single opaque label. Display copy is a UI concern.

### Dashboard
- FR-009: Dashboard shows summary counts: total medications / valid / expiring soon / expired / out-of-stock badges active. Priority: must-have
  > Socrates: Counter-argument considered: "dashboard duplicates the filtered list (FR-004)." Resolution: kept — dashboard is the landing screen; at-a-glance counts are the primary value moment on open.

### Medication Details
- FR-011: Each cabinet entry displays the producer and route of administration (method of use) sourced from the official dataset. Priority: must-have
  > Socrates: Resolution: updated — display producer and route of administration only; general manufacturer field dropped as redundant.

- FR-012: Each cabinet entry displays links to the drug leaflet and specification sourced from the official dataset. Priority: must-have. Inline PDF preview: nice-to-have (v2).
  > Socrates: Counter-argument considered: "inline PDF preview is non-trivial across browsers." Resolution: links only for MVP; inline preview deferred to v2.

### Package Count Constraint
- FR-022: Adding a medication entry requires a package count of at least 1. A count of 0 is not a valid value when creating an entry; the package count can only reach 0 by decrementing after the entry exists (FR-005). Priority: must-have
  > Socrates: Counter-argument considered: "a user might want to track a medication they know they need to buy but don't have yet." Resolution: not supported in MVP — the cabinet tracks what the user has, not a wish list. 0-package tracking deferred to v2.

## Non-Functional Requirements

- The app must be fully usable on mobile browsers (responsive layout); web-only, no native app required
- Search and autocomplete must return results with no perceptible lag (user-perceived response < 500 ms p95)
- One user's cabinet data must never be visible to another user (strict per-account data isolation)
- The application interface must be in Polish language

## Business Logic

The system classifies each cabinet entry and proactively alerts the user before a medication becomes unusable or runs out, based on multiple overlapping rules.

**Expiry classification**: each entry is classified as valid, expiring soon, or expired — based on the user's configured expiry threshold. An "out of stock" badge is computed on top of expiry classification for important medications when they are expiring soon or expired, or when their package count falls below the user's configured minimum.

**Dosage-based finish estimation**: for medications in the "used" category with tablet-based dosage, the system computes daily consumption rate = (times × dosage amount per intake) ÷ period in days (1 for per-day, 7 for per-week). Estimated days of supply = (package count × tablets per package) ÷ daily consumption rate. If an end date is set, the system compares days of supply against days until end date and displays sufficiency. If no end date is set, the system displays the estimated finish date. Non-tablet medications (no tablet count in registry) can be assigned to "used" for start/end date tracking only; dosage fields and finish-date estimation are not available for them.

**Notification triggers**: in-app notifications fire when (a) a medication enters the expiry threshold window, (b) an important medication's package count drops below the configured minimum, or (c) a used medication's estimated finish date falls within the close-to-finish threshold. Notifications are surfaced through a persistent notification center accessible from any screen.

**Inputs**: expiry date, package count, tablet count per package, user's expiry threshold (7–90 days), global minimum package count for important medications, dosage data (times, period [per day / per week], dosage amount per intake, start date, optional end date), close-to-finish threshold (days).  
**Output**: status classification per entry (valid / expiring soon / expired); out-of-stock badge (important entries only); estimated finish date or sufficiency indicator (used tablet-based entries); in-app notifications per the above triggers.

## Access Control

- Registration: email address + password
- Authentication: login / logout
- Role model: flat single-role (all registered accounts are equal users)
- Unauthenticated users cannot access any cabinet data or notification center
- No admin UI in MVP

## Non-Goals

- No native mobile app (iOS/Android) — web-only for MVP
- No multi-profile or household member support — one cabinet per account; no assigning medications to family members
- No prescription checking — the app tracks inventory, not prescriptions
- No photo, barcode, or document scanning for adding medications — manual entry via approved list only
- No email or push notifications in MVP — in-app notification center only
- No per-entry minimum package thresholds for important medications — one global minimum applies to all in MVP
- No variable dosing schedules for "used" medications — fixed frequency with per-day or per-week period only in MVP; as-needed (PRN) dosing not supported
- No inline PDF preview for drug leaflets — links only in MVP; inline preview deferred to v2
- No wish-list or zero-package tracking — the cabinet records what the user currently has

## Open Questions

_(none — all gaps resolved during shaping)_
