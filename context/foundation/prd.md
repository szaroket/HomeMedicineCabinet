---
project: "Home Medicine Cabinet"
version: 1
status: draft
created: 2026-05-29
context_type: greenfield
product_type: web-app
target_scale:
  users: small
  qps: low
  data_volume: small
timeline_budget:
  mvp_weeks: 2
  hard_deadline: "2026-07-05"
  hard_deadline_fallback: "2026-08-10"
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
- User receives an in-app notification when a medication is close to expiry, when an important medication falls below the configured minimum, or when a used medication with an end date is at risk of running out before the course ends and the estimated run-out falls within the configured close-to-finish threshold

### Secondary
- User returns to check their cabinet at least once a week without an external prompt (signals genuine habit formation)

### Guardrails
- Search and autocomplete return correct medication matches ≥ 95% of the time — wrong suggestions corrupt cabinet data
- One user's cabinet data is never visible to another user
- Dosage-based finish-date calculations must clearly display their assumptions so the user can trust or override them

## User Stories

### US-01: Add a medication to the cabinet

- **Given** a logged-in user on the add medication screen
- **When** they type a medication name, select from the autocomplete dropdown, choose a tablet count, enter a package count (≥ 1), and set an expiry date
- **Then** the medication appears in their cabinet with the correct status classification (valid / expiring / expired)

### US-02: Receive in-app notification for expiry

- **Given** a user has set an expiry threshold and has a medication expiring within that window
- **When** they open the application
- **Then** the notification bell shows an unread count and the notification center lists the medication name and days remaining before expiry

### US-03: Check cabinet at the pharmacy

- **Given** a logged-in user on a mobile browser
- **When** they search their cabinet by medication name or active ingredient
- **Then** matching entries are returned quickly enough to use while standing at the pharmacy counter

### US-04: Track an active medication course

- **Given** a logged-in user who has added a medication
- **When** they assign it to the "used" category with frequency (3×/day), tablets per dose (1), and no end date
- **Then** the cabinet entry displays the estimated finish date (no close-to-finish notification fires — notifications for run-out require an end date to be set)

### US-05: Important medication below minimum

- **Given** a user has marked a medication as "important" and set a global minimum of 2 packages
- **When** the package count on that entry drops to 1
- **Then** the entry displays an "out of stock" badge and an in-app notification appears in the notification center

## Functional Requirements

### Authentication
- FR-001: User can register with an email address and password. Priority: must-have
  > Socrates: Counter-argument considered: "skip registration; store data locally." Resolution: kept — data must persist across devices and browsers; local storage is too fragile.

- FR-002: User can log in and log out. Priority: must-have
  > Socrates: Counter-argument considered: "logout is rarely used in personal apps." Resolution: kept — logout is a basic security requirement inseparable from any auth system.

### Adding Medications
- FR-003: User can add a medication by typing a name, selecting from an autocomplete dropdown sourced from the Polish-approved medications list, selecting tablet count (from official dataset), entering number of packages (minimum 1; 0 packages is not a valid starting value), setting an expiry date, and optionally entering an actual tablet count for a partially-opened package. If the actual tablet count is left blank, the system assumes the package is full. For non-tablet medications (those without a tablet count in the dataset, e.g. syrups or drops), the tablet-count and partial-package fields are hidden; the entry is recorded by name, package count, and expiry date only. Priority: must-have
  > Socrates: Counter-argument considered: "official dataset may be stale or missing newly approved drugs." Resolution: kept — constraining to the approved list is the core differentiator; data quality is the product. Manual fallback deferred to v2.

- FR-010: When adding a medication, if an entry with the same drug + tablet count + expiry date already exists, the system merges the addition into the existing entry by summing total tablets across both. Total tablets per entry = (full packages × tablets per package) + actual tablet count of the partially-opened package (if set; otherwise all packages are full). After summing, the merged total is normalized: if it divides evenly by tablets per package, package count = merged total ÷ tablets per package with the actual tablet count cleared (all packages full); otherwise package count = ⌈merged total ÷ tablets per package⌉ with the actual tablet count = merged total mod tablets per package (one partial package, remainder full). Differing expiry dates create a new entry. For non-tablet medications, the dedup key is (drug + expiry date) only; merging increments the package count without tablet-pool re-normalization (partial-tablet tracking does not apply). Priority: must-have
  > Socrates: Counter-argument considered: "silently merging could hide a different expiry batch." Resolution: updated — deduplication key is drug + tablet count + expiry date (three-field match); differing expiry date creates a new entry. Partial-package values from both sides are summed and re-normalized so the merge preserves total tablet count (the value the FR-016 finish-date calculation depends on); physical detail of "which package was opened first" is intentionally not tracked.

### Cabinet Management
- FR-004: User can view their cabinet as a list with filtering by status (valid / expiring / expired / out-of-stock badge) and by category (important / used; multi-select — selecting both returns entries that have either category), sorting by medication name, and pagination. Status and category filters can be combined (intersection: e.g., expiring + important). Priority: must-have
  > Socrates: Counter-argument considered: "flat unordered list is sufficient; search covers discovery." Resolution: updated — filtering by status and pagination added for usability at scale; sort by name added per user requirement.

- FR-005: User can increase or decrease the package count on a cabinet entry, update the actual tablet count of the partially-opened package (or clear it to mark the package as full), or delete the entry. Deleting requires explicit confirmation; if the entry carries an "out of stock" badge, the confirmation states it will also be cleared. When decrementing the package count would result in 0 packages: if the entry is in neither the "important" nor "used" category, the system shows a confirmation pop-up warning that the entry will be deleted, and removes the entry on confirm. If the entry is in the "important" or "used" category, the entry stays at package count = 0 so the user can restock — the FR-020 below-minimum badge surfaces "important" entries; "used" entries remain visible in the active-course context with 0 days of supply. Priority: must-have
  > Socrates: Counter-argument considered: "no expiry date editing means batch changes are unrecordable." Resolution: kept — different expiry batches are separate entries added via FR-003; this keeps the edit scope intentionally narrow.
  > Socrates: Counter-argument considered: "auto-deleting on decrement-to-zero could surprise users who didn't intend to remove the entry." Resolution: confirmation pop-up is required before delete; important/used entries are exempt from auto-delete because their category implies the user wants to track them through restocking.

- FR-006: User can search their cabinet by free text matched against medication name or active ingredient. Priority: must-have
  > Socrates: Counter-argument considered: "users may want to search the full registry, not just their cabinet." Resolution: kept — cabinet-only search is MVP scope; registry browsing deferred to v2.

### Medication Categories
- FR-013: User can assign a medication entry to the "important" category. A medication can simultaneously hold both "important" and "used" categories. Priority: must-have
  > Socrates: Counter-argument considered: "important flag without per-entry minimum is too coarse — EpiPen and ibuprofen deserve different thresholds." Resolution: kept for MVP — one global minimum applies to all important medications; per-entry overrides deferred to v2.

- FR-014: User can set a global minimum package count for "important" medications (minimum value: 1; default: 1; same threshold applies to all important medications in MVP). Priority: must-have
  > Socrates: Counter-argument considered: "one global minimum means the system can't distinguish truly critical drugs (must always have 2) from low-priority ones." Resolution: accepted tradeoff — single global value keeps the settings screen simple; per-entry minimum deferred to v2.

- FR-015: User can assign a medication entry to the "used" category with start date (default: date of assignment) and an optional end date. For tablet-based medications (those with a tablet count from the registry), three additional dosage fields are shown: (1) how many times (integer), (2) period — per day or per week, (3) dosage amount per intake (integer, in tablets). Example: "3 × 2 tablets per day". For non-tablet medications (e.g. syrups, without a tablet count), the dosage fields are hidden and no finish-date calculation is available. Priority: must-have
  > Socrates: Counter-argument considered: "variable dosing (e.g. 1 tablet some days, 2 on others) cannot be captured as fixed frequency + period." Resolution: accepted — fixed schedule is the MVP approximation; the system displays the assumption explicitly so the user can judge accuracy. Separate UI fields (times / period / dosage) make the structure clear.

- FR-016: For tablet-based medications in the "used" category (dosage fields present), the system calculates the estimated finish date. Daily consumption rate = (times × dosage amount) ÷ period in days (1 for per-day, 7 for per-week). Total tablets available = actual tablet count of the partially-opened package (if set) + remaining full packages × tablets per package. Days of supply = total tablets available ÷ daily consumption rate. For non-tablet medications assigned to "used", no finish-date calculation is shown. Priority: must-have
  > Socrates: Counter-argument considered: "calculation assumes full packages and consistent dosing; a half-used package or a skipped day will make the estimate wrong." Resolution: kept — the estimate is displayed with its assumptions; partial-package tracking (FR-003, FR-005) improves accuracy for opened packs; accuracy otherwise depends on the user keeping counts current.

- FR-017: For "used" medications with an end date, the system displays whether the current stock is sufficient to last until that date. Priority: must-have
  > Socrates: Counter-argument considered: "'sufficient' is ambiguous — does it mean exactly enough, or with buffer?" Resolution: the system shows exact days remaining vs. days of supply, letting the user judge sufficiency; no buffer is computed by the system.

- FR-018: For "used" medications with no end date, the system displays the calculated estimated finish date. Priority: must-have
  > Socrates: Counter-argument considered: "without an end date the finish date is only useful if the user acts on it — otherwise it's just a number." Resolution: kept — the estimated finish date is useful at the pharmacy when deciding whether to restock. Note: no close-to-finish notification fires without an end date (FR-019 requires an end date to determine that stock will run out before the course ends).

### Notifications (In-App)
- FR-007: User can configure two notification settings: (1) expiry threshold (7–90 days before expiry date; default: 30 days) — governs "expiring soon" classification and expiry notifications; (2) close-to-finish threshold (days before estimated run-out; default: 7 days) — governs run-out reminders for "used" medications with an end date. Both defaults are applied to every new account and remain in effect until the user changes them in settings. Priority: must-have
  > Socrates: Counter-argument considered: "two separate thresholds in settings adds cognitive load." Resolution: kept — expiry and finish-date concerns are distinct and the user may want different sensitivity for each (e.g. 14 days for expiry, 7 days for run-out). Both are single global values in MVP.

- FR-008: The system delivers in-app notifications via a notification center (bell icon with unread count) triggered by: (a) a medication entering the expiry threshold window; (b) an "important" medication's package count falling below the configured minimum; (c) a "used" medication with an end date whose estimated finish date falls before the end date and within the close-to-finish threshold. The user can dismiss any individual notification; a dismissed notification does not re-fire until the underlying condition clears and is triggered again from scratch. Clearance per trigger: (a) cleared when the entry is no longer within the expiry threshold window (entry deleted, restocked with a fresher expiry batch as a new entry, or threshold setting widened to exclude it); (b) cleared when package count strictly exceeds the configured minimum (e.g., min=2 → clears at count ≥ 3), providing a hysteresis buffer so the notification does not re-fire on each minor dip back to the minimum; (c) cleared when the estimated finish date moves outside the close-to-finish threshold window (user restocked, lowered dosage, or extended end date). Priority: must-have
  > Socrates: Counter-argument considered: "in-app notifications are only seen when the user opens the app — they may miss time-sensitive alerts." Resolution: accepted for MVP — the product is web-only and the persona checks the app regularly; push/email notifications deferred to v2.

- FR-019: The system shows an in-app notification when a "used" medication has an end date, the estimated finish date falls before that end date (stock will run out before the course ends), and the estimated finish date is within the user-configured close-to-finish threshold. Medications with no end date do not trigger this notification. The user can dismiss the notification; if dismissed while the condition is still active, it does not re-fire until the condition clears — i.e., the estimated finish date moves outside the close-to-finish threshold window (user restocked, lowered dosage, or extended end date) — and is triggered again from scratch. Priority: must-have
  > Socrates: Counter-argument considered: "notification fires repeatedly until restocked, which could become noise." Resolution: user can dismiss any notification manually; dismissed notifications do not re-fire until the triggering condition fully resolves and re-triggers.

### Out of Stock Status
- FR-020: The system automatically displays an "out of stock" badge on an "important" medication entry when any of these conditions hold: (a) the medication is close to expiry (within expiry threshold) or expired; (b) package count is below the user-configured minimum. The badge is computed — it clears automatically when conditions no longer hold. Priority: must-have
  > Socrates: Counter-argument considered: "a drug expiring soon but with many packages isn't really out of stock — the label is misleading." Resolution: "out of stock" is a working name; the badge surfaced to the user communicates the specific condition (expiring / expired / below minimum), not a single opaque label. Display copy is a UI concern.

### Dashboard
- FR-009: Dashboard shows summary counts: total medications / valid / expiring soon / expired / out-of-stock badges active. Each count is a clickable link that navigates to the cabinet list pre-filtered to the corresponding status. Priority: must-have
  > Socrates: Counter-argument considered: "dashboard duplicates the filtered list (FR-004)." Resolution: kept — dashboard is the landing screen; at-a-glance counts are the primary value moment on open. Clickable counts make the dashboard an active navigation hub, not just a summary.

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
- Search and autocomplete must return results with no perceptible lag (user-perceived response < 500ms p95)
- One user's cabinet data must never be visible to another user (strict per-account data isolation)
- The application interface must be in Polish language
- All cabinet data, user account data (email, password), and user preferences (expiry threshold, close-to-finish threshold, minimum package threshold) must persist across sessions and devices — the same data must remain accessible after the user logs in from a different browser or device

## Business Logic

The system classifies each cabinet entry and proactively alerts the user before a medication becomes unusable or runs out, based on multiple overlapping rules.

**Expiry classification**: each entry is classified as valid, expiring soon, or expired — based on the user's configured expiry threshold. An "out of stock" badge is computed on top of expiry classification for important medications when they are expiring soon or expired, or when their package count falls below the user's configured minimum.

**Dosage-based finish estimation**: for medications in the "used" category with tablet-based dosage, the system computes daily consumption rate = (times × dosage amount per intake) ÷ period in days (1 for per-day, 7 for per-week). Total tablets available = actual tablet count of the partially-opened package (if set; otherwise that package is assumed full) + remaining full packages × tablets per package. Estimated days of supply = total tablets available ÷ daily consumption rate. If an end date is set, the system compares days of supply against days until end date and displays sufficiency. If no end date is set, the system displays the estimated finish date. Non-tablet medications (no tablet count in registry) can be assigned to "used" for start/end date tracking only; dosage fields and finish-date estimation are not available for them.

**Notification triggers**: in-app notifications fire when (a) a medication enters the expiry threshold window, (b) an important medication's package count drops below the configured minimum, or (c) a used medication has an end date, its estimated finish date falls before that end date, and the finish date is within the close-to-finish threshold. Notifications appear in a persistent notification center (bell icon with unread count).

**Inputs**: expiry date, package count, tablet count per package, user's expiry threshold (7–90 days), user's close-to-finish threshold (days before estimated run-out), global minimum package count for important medications, dosage data (times, period [per day / per week], dosage amount per intake, start date, optional end date).
**Output**: status classification per entry (valid / expiring soon / expired); out-of-stock badge (important entries only); estimated finish date or sufficiency indicator (used entries); in-app notifications per the above triggers.

## Access Control

- Registration: email address + password
- Authentication: login / logout
- Role model: flat single-role (all registered accounts are equal users)
- No admin UI in MVP

## Non-Goals

- No native mobile app (iOS/Android) — web-only for MVP
- No multi-profile or household member support — one cabinet per account; no assigning medications to family members
- No prescription checking — the app tracks inventory, not prescriptions
- No photo, barcode, or document scanning for adding medications — manual entry via approved list only
- No email or push notifications in MVP — in-app notification center only
- No per-entry minimum package thresholds for important medications — one global minimum applies to all in MVP
- No variable dosing schedules for "used" medications — fixed frequency with per-day or per-week period only in MVP; as-needed (PRN) dosing not supported
- No grouped cabinet view — medications are displayed as a flat list of entries (drug + tablet count + expiry date); grouping by medication name with per-variant breakdown deferred to v2
- No registry data updates — the Polish-approved medications registry is stored in the database and imported once at MVP; each record is created once and not updated thereafter. Periodic/incremental refresh of registry records deferred to v2
- No veterinary medications — only medicines approved for human use are inserted into the registry database; animal/veterinary medicines are out of scope

## Open Questions

_None at close of shaping — all gaps from discovery and the post-shape verification round were resolved before PRD generation._
