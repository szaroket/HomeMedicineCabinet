---
project: home-medicine-cabinet
researched_at: 2026-06-02
recommended_platform: Render
runner_up: Railway
context_type: mvp
tech_stack:
  language: python + javascript
  framework: FastAPI + Vite/React
  runtime: uvicorn (backend) / static (frontend)
  database: Supabase (PostgreSQL, external)
---

## Recommendation

**Deploy on Render.**

Render is the only evaluated platform that supports the full stack (FastAPI + SQLModel/psycopg2 + Vite/React) without any code changes, at zero initial cost. The backend runs as a Render Web Service (free tier with cold starts, upgradeable to always-on at $7/month); the frontend runs as a Render Static Site (always free, no cold starts, CDN-served). Cloudflare Workers was blocked by C-extension incompatibility with SQLAlchemy/psycopg2; Vercel required significant app restructuring; Fly.io has no free tier and demands a Dockerfile from day one. Render fits the cost-minimization priority, the single-platform preference, and the 2-week after-hours timeline with zero platform-forced rework.

## Platform Comparison

| Criterion | Render | Railway | Vercel | Fly.io | Cloudflare | Netlify |
|---|---|---|---|---|---|---|
| CLI-first | ⚠️ Partial | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass |
| Managed/serverless | ⚠️ Partial | ✅ Pass | ✅ Pass | ⚠️ Partial | ✅ Pass | ✅ Pass |
| Agent-readable docs | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass |
| Stable deploy API | ⚠️ Partial | ⚠️ Partial | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass |
| MCP / integration | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass | ✅ Pass |
| **Score** | 2P / 3Partial | 4P / 1Partial | 5 Pass | 4P / 1Partial | 5 Pass* | DROPPED |
| **Free tier** | ✅ Yes | ❌ $5/mo min | ✅ Yes | ❌ No | ✅ Very generous | N/A |
| **Stack compatible** | ✅ Yes | ✅ Yes | ⚠️ Restructure needed | ✅ Yes | ❌ SQLAlchemy blocked | ❌ No Python |

\* Cloudflare scores 5/5 on criteria but is blocked by Python Workers beta status and C-extension incompatibility with SQLAlchemy/psycopg2 — dropped from shortlist on hard filter.

### Shortlisted Platforms

#### 1. Render (Recommended)

Full GA Python/FastAPI support, zero code changes required. Static Site service hosts the Vite/React frontend free with no cold starts; Web Service hosts FastAPI on the free tier (cold starts after 15 min inactivity) with a clear $7/month upgrade path to always-on. Single platform, one dashboard. Render MCP (GA, 20+ tools) covers deploy, logs, restart, and rollback for agent-driven operations. The Partial scores on CLI-first and stable deploy API reflect the absence of a CLI rollback command — mitigated by the Render MCP rollback tool.

#### 2. Railway

Best developer experience of all candidates: auto-detects Python, no Dockerfile, no code restructuring, no cold starts. $5/month Hobby plan with $5 usage credit included (effective usage-based billing at low traffic). Railway MCP (GA) and llms.txt. Drops to runner-up because: (a) $5/month vs Render's $0 free tier goes against the cost-minimization priority; (b) billing has no hard cap — a misconfigured service or burst traffic can exceed the credit unexpectedly; (c) no `railway rollback` CLI command; (d) PR Environments are in beta as of Q2 2026.

#### 3. Fly.io

Already referenced in `tech-stack.md`. The most operationally capable platform — Firecracker VMs, FlyMCP (GA), full persistent process support, scale-to-zero optional. Drops to third because: (a) no free tier (minimum ~$3–6/month); (b) Dockerfile required from day one; (c) steepest learning curve for a developer with no prior platform familiarity; (d) `fly.toml` networking is permissive by default, requiring explicit hardening. Right platform for production scale, over-engineered for a 2-week personal MVP.

## Anti-Bias Cross-Check: Render

### Devil's Advocate — Weaknesses

1. **Cold starts corrupt first impressions.** Free Web Services sleep after 15 minutes of inactivity. The first request wakes them — 30–60 seconds of spinner before any response. Every session after a break starts cold.
2. **No CLI rollback command.** Rolling back requires `POST /services/{id}/rollback-deploy` via the Render REST API, the dashboard, or the Render MCP tool. Manual recovery without MCP configured requires knowing the deploy ID and an API token.
3. **Free tier shared compute is non-deterministic.** Performance on shared infrastructure varies — hard to distinguish a platform noisy-neighbour spike from an application bug.
4. **Custom domains require a paid plan.** The backend lives at `.onrender.com` on the free tier. Attaching a real domain requires upgrading to paid first.
5. **750 CPU-hours/month free limit.** A 512 MB service that stays alive via keep-alive pings uses ~372 CPU-hours/month, leaving limited headroom for a second service or traffic spikes.

### Pre-Mortem — How This Could Fail

The developer deployed FastAPI to Render's free tier, thrilled by the $0 cost. For the first two weeks, testing went smoothly — they visited the app frequently, so cold starts were rare. But when they tried to demo the medication cabinet to a friend, the friend clicked the link and stared at a loading spinner for 50 seconds — it looked broken. The developer added a keep-alive ping (a scheduled fetch to `/health` every 14 minutes) but this required an external cron service, adding a second dependency and a new failure mode. The ping occasionally failed; cold starts returned unpredictably. After month two, fed up with the cold-start dance, they upgraded to Render's $7/month paid plan. The app worked fine from that point — but they had spent hours debugging infrastructure instead of building features, and paid $14 total for what would have been $7 from day one.

### Unknown Unknowns

- **The keep-alive anti-pattern adds hidden complexity.** Avoiding cold starts requires either an external cron ping or frontend-side periodic requests — both workarounds with their own failure modes.
- **Render MCP rollback works; CLI rollback does not.** An agent with Render MCP configured can roll back via structured tool call. Without MCP, recovery requires a raw REST call with a deploy ID the developer may not have handy.
- **Free Web Services cannot use custom domains.** If the project ever publishes at a real domain, a paid plan upgrade is required before the domain can be attached — a forced upgrade that wasn't in the original cost estimate.
- **Preview environments (per-PR branch deploys) are a paid feature.** CI/CD that creates per-PR preview environments requires the paid plan on Render's Web Service.

## Operational Story

- **Preview deploys**: Render Static Site creates deploy previews per branch automatically (free). Web Service previews require paid plan. For MVP: preview the frontend freely; test backend changes against the free service URL directly or via a feature branch deploy.
- **Secrets**: Environment variables live in the Render dashboard under each service's Environment tab. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `DATABASE_URL` here — they are injected at runtime and never committed to the repo. Rotation: update the value in the dashboard, trigger a manual redeploy.
- **Rollback**: `POST https://api.render.com/v1/services/{service-id}/rollback-deploy` with `{"deployId": "<prior-deploy-id>"}` and `Authorization: Bearer <api-key>` header. Via Render MCP: call the `rollback_deploy` tool with the service ID. Via dashboard: Services → Events → click prior deploy → Rollback. Typical time-to-revert: 2–3 minutes. DB migrations do not auto-rollback — run a compensating migration manually if the schema changed.
- **Approval**: Render agent (via MCP) may perform: deploy, restart service, tail logs, read environment variable names (not values). Requires human: rotate the Render API key, change billing tier, attach a custom domain, delete a service.
- **Logs**: `render logs --service <service-id> --tail` (CLI, GA). Via Render MCP: `get_logs` tool with service ID and optional filter. Dashboard: Services → Logs tab. Real-time tailing works; historical logs beyond the last session require a log drain integration (Papertrail, Logtail) for persistence — not configured by default.

## Risk Register

| Risk | Source | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Cold starts make free tier feel broken to new users | Devil's advocate | H | M | Upgrade to $7/mo paid when sharing externally; accept cold starts during solo dev phase |
| Keep-alive workaround adds a hidden dependency | Unknown unknowns | M | L | Don't implement keep-alive; upgrade to paid instead when cold starts matter |
| No CLI rollback — incident recovery requires API or MCP | Devil's advocate | L | M | Configure Render MCP from day one; keep API key in password manager |
| Free tier shared compute causes unpredictable latency | Devil's advocate | M | L | Treat as environment noise during dev; diagnose app-level before blaming platform |
| Custom domain blocked on free tier | Unknown unknowns | M | L | Plan domain attachment to coincide with $7/mo upgrade |
| DB migration schema change not rolled back with service rollback | Pre-mortem | L | H | Write compensating migrations before rolling back service; test migrations on a branch first |
| Render free PostgreSQL deleted after 90 days | Research finding | L | L | Not applicable — database is Supabase (external); no Render DB in use |
| Preview environments unavailable on free Web Service | Unknown unknowns | M | L | Use feature branch deploys to the main free service for backend testing; frontend previews are free |

## Getting Started

1. **Create a Render account** at render.com — free, no credit card required for free tier services.
2. **Deploy the backend** (Render Web Service):
   - New → Web Service → connect your GitHub repo → select the `backend/` root directory
   - Runtime: Python 3 (auto-detected from `pyproject.toml` / `requirements.txt`)
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Add environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`
3. **Deploy the frontend** (Render Static Site):
   - New → Static Site → connect the same repo → select the `frontend/` root directory
   - Build command: `npm run build`
   - Publish directory: `dist`
   - Add environment variable: `VITE_API_URL=<your-render-web-service-url>`
4. **Update FastAPI CORS** to allow the Render Static Site URL (`.onrender.com` domain) in `allow_origins`.
5. **Wire GitHub Actions**: add `RENDER_API_KEY` and service IDs to GitHub Secrets; use the Render deploy hook URL (`https://api.render.com/deploy/<hook-id>?key=<key>`) in your CI pipeline's deploy step.

## Out of Scope

The following were not evaluated in this research:
- Docker image configuration
- CI/CD pipeline setup
- Production-scale architecture (multi-region, HA, DR)
