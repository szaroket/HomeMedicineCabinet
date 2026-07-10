# Welcome Landing Page (S-10) — Plan Brief

> Full plan: `context/changes/welcome-landing-page/plan.md`

## What & Why

An unauthenticated visitor should land on a public welcome page that briefly describes the app (what it is and what they can do) and can navigate from there to log in or register. Today there is no public front door — an unauthenticated visit to `/` just bounces to `/login`. This slice (roadmap S-10) adds the marketing entry surface. All copy is Polish.

## Starting Point

`/` is currently the protected dashboard; `PublicLayout` is a bare pass-through with no auth check (so logged-in users can still see the login/register forms — an existing gap). The guard lives in `ProtectedLayout` (token check → `/login`). Public pages (login/register) follow a self-contained dark full-screen shell + `AppFooter` pattern.

## Desired End State

Logged-out visitors see a Polish welcome page at `/` — logo, headline, one-paragraph description, four capability highlights, and Register-primary / Login-secondary CTAs. The dashboard moves to `/dashboard`. Any authenticated visitor to `/`, `/login`, or `/register` is redirected to `/dashboard`; login/registration land there too.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Routing shape | Welcome at `/`, dashboard → `/dashboard` | `/` as the true public front door is the conventional shape; the cost is updating a handful of `/` references | Plan |
| Authed redirect scope | Guard `/`, `/login`, `/register` in `PublicLayout` | Fixes the existing gap (logged-in users seeing auth forms) in one place, consistently | Plan |
| Visual scope | Hero + four short feature highlights | Actually "describes what they can do" per the roadmap outcome while reusing the login-page shell | Plan |
| Highlights shown | Registry-clean data, expiry/low-stock alerts, dosage tracking, dashboard overview | The four capabilities that best convey the product's value | Plan |
| CTA hierarchy | Register primary, Login secondary | A landing page's job is to convert new visitors; returning users still find login easily | Plan |

## Scope

**In scope:** static welcome page component + unit test; route rewire (welcome at `/`, dashboard at `/dashboard`); `PublicLayout` authed-redirect guard; update all `/` references + affected tests; E2E for landing and redirect flows.

**Out of scope:** rich multi-section marketing site; any backend/schema/data fetching; new shared UI primitives; i18n framework; changing `ProtectedLayout`'s unauthenticated redirect target.

## Architecture / Approach

New `features/landing/components/welcome-page.tsx` reuses the public-page shell (full-screen `bg-slate-900`, logo, `AppFooter`, Tailwind dark theme) and `Link`s to `/register` and `/login`. Routing change mounts it in the public group at `/`, relocates the dashboard route, and adds a `token`→`/dashboard` `<Navigate>` guard to `PublicLayout` (mirroring `ProtectedLayout`). Six `/`-references and one test assertion are updated in lockstep.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Welcome page component | Self-contained, unit-tested landing page (not yet routed) | Copy/layout polish; low risk — no routing touched |
| 2. Routing rewire & redirects | Welcome at `/`, dashboard at `/dashboard`, `PublicLayout` guard, all references + tests updated, E2E | Missing a `/`-reference (post-login nav, sidebar, account-deleted) causes a dead link |

**Prerequisites:** F-01 auth scaffold (done). No new deps.
**Estimated effort:** ~1 session across 2 phases.

## Open Risks & Assumptions

- The `/`-reference inventory in the plan must be complete — a missed one leaves a link pointing at the now-public welcome page instead of the dashboard. The plan lists all seven; E2E on post-login and sidebar navigation catches regressions.
- `PublicLayout` guard uses `token` presence only (no silent-refresh validation); a stale token redirects to `/dashboard` where `ProtectedLayout` validates and bounces to `/login` if invalid — acceptable.

## Success Criteria (Summary)

- Logged-out visitor lands on the Polish welcome page at `/` and can reach register and login.
- Logged-in visitor never sees a public page — always redirected to `/dashboard`.
- Login/registration and sidebar navigation all resolve to `/dashboard` with no broken links; build, lint, unit, and E2E all pass.
