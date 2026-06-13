# Progress Tracker

Update this file after every working session. Any agent reading this should immediately know the current state, what was recently done and why, and what's next. This is the project's memory across sessions — the decisions log keeps settled questions settled.

---

## Current Status

**Branch:** `v2.0` (default branch for PRs: `main`)
**Phase:** B — Stabilization (see `roadmap.md`)
**Current focus:** Billing hardening is **done**; the only open billing item is **testing the Paystack route end-to-end** (checkout → webhook → tier change).
**Last completed:** Billing hardening — Stripe webhook/customer-ID fixes + subscription cancel/resume + account deletion (`009abc9`).
**Next:** Test the Paystack route → then begin the Phase C **AI capabilities upgrade** (build the AI seam first — see `roadmap.md` + `architecture.md` § AI Generation & Model Tiering).

---

## Active Issues

> The live bug list. Add entries as issues are observed; move them to the changelog when fixed; promote recurring ones to `failure-modes.md`.

- [ ] *(none recorded yet — when you hit the next bug, log it here with: symptom, where observed (local/prod), suspected failure class from `failure-modes.md`)*

### Watchlist (suspected, not yet confirmed bugs)
- `clean_email()` can over-repair (insert `@` into non-emails) — no confirmed mis-send yet; watch reports.
- Webhook handlers not yet verified idempotent against replayed events.
- Failed email/SMS rows have no targeted retry — rerunning a send task re-sends to everyone in valid_data (PDFs skip existing; sends don't).

---

## Decisions Made During Build

The load-bearing decisions and the reasoning — do not re-litigate these without new evidence:

- **DB is the single source of truth for job/task state; no in-memory job cache.** The cache was tried and removed (`d73971e`) — with 2 gunicorn workers, memory diverges. Every request loads fresh; only background threads hold live Job references.
- **Background work = daemon threads, not Celery/asyncio.** Deliberate simplicity: no broker to operate. The cost — cross-worker invisibility, redeploy death — is paid via DB-backed state, flag polling, and startup stale-task marking. Don't introduce a second concurrency mechanism casually.
- **`tasks_json` is merge-written, control flags are direct-written.** Progress merges (terminal wins, higher progress wins); cancel/pause/resume bypass `save()` into dedicated columns so they can't be overwritten (`ade869b`, `0f583d2`).
- **Stale-"running" recovery happens once at startup, never per-load.** Per-load marking corrupted legitimately-running tasks on the other worker.
- **Two job loaders.** Full (DataFrame from storage, ~3s, can save) vs light (metadata only, instant, must NEVER save) — list/status/SSE endpoints use light (`c71b7cf`).
- **Spreadsheets are read as strings, always.** Type inference destroyed phone numbers/dates (`88f0883`).
- **Storage is dual-write local+S3 with on-demand restore; ZIPs preferred over per-file round-trips** (`e8f0686`, `6aacd92`). Railway disk is ephemeral.
- **Schema migrations are additive-only and automatic** (`2ef6a87`) — model-vs-DB diff on startup, columns added with safe defaults, nothing dropped, errors logged not swallowed (`746f35a`).
- **Dual billing by region.** NG → Paystack/NGN, else Stripe/USD; one `TIERS` dict carries both prices. Tier changes only via verified server-side events.
- **Stripe webhook payloads parsed as plain JSON dicts; stored customer IDs validated and recreated if stale** (`7532883`, `9208dde`).
- **Tier guards enforced server-side on the endpoints** (job count, row count with photo-column stricture, AI quota, template access) (`d479e1f`).
- **Image media types from magic bytes, never extensions** (`4ea9dbc`, `4262218`).
- **SSE reads light jobs from DB on a 2s/10s cadence; TaskPanel is presentation-only** — polling lifecycle lives in the job-detail page (`0f583d2`, `c53ec31`, `51df5eb`).
- **Frontend: one API wrapper (`lib/api.ts`) with auto-logout on 401; `vp_`-prefixed localStorage keys.**
- **AI model tiering via a thin per-task seam (planned).** Template generation/editing → top-tier model (quality-critical, low-frequency, the core output); email/SMS drafting → cheap model (low-stakes, user-edited). One `ai` seam holds a *static* task→model map + a real `messages[]` conversation contract — **client-replayed, backend stateless** (no server-side conversation state; that would be another multi-worker consistency surface) — plus centralized prompt caching, JSON-repair, and AI-quota checks. Earned now (≥2 real tiers across 4 call sites: template-gen, in-job edit, email, SMS) — but **not** a dynamic router. Vehicle TBD: OpenRouter (best-of-breed mix, keep Claude for templates) vs single-vendor Gemini (Pro + Flash-Lite). Template-tier quality comes from a WeasyPrint-aware prompt + render-check, not model tier alone. Full design in `architecture.md` § AI Generation & Model Tiering.

---

## Changelog (recent, newest first)

### Billing hardening (current)
- `009abc9` feat: subscription cancel/resume + account deletion
- `7532883` fix: parse Stripe webhook payload as plain JSON dicts
- `345ca24` fix: harden Stripe checkout webhook handler, add diagnostic logging
- `9208dde` fix: validate stored Stripe customer ID, recreate if stale

### Marketing & SEO
- `ee8904e` feat: /blog route with SEO-targeted articles
- `88e1042` feat: SEO metadata, sitemap, robots.txt, branding in AI prompts
- `a9ec85a` feat: demo video in landing hero · `836ee38` fix: favicon

### Data & tasks reliability sweep
- `88f0883` fix: read Excel as strings (preserve dates/phone numbers)
- `8e5e445` feat: job completion status fix, photo download rewrite, photo ZIP
- `d479e1f` feat: tier guards on all endpoints + per-job row limits
- `cd9ab6a` feat: individual log file download
- `ade869b` fix: merge tasks_json in save() — cross-worker state regression
- `df91e67` fix: BulkSMS config vars + fail-fast on missing token
- `b003d61` fix: clear stale pause flag before starting any task
- `2c494bb` fix: save progress during PDF skip loop (SSE accuracy)
- `c71b7cf` perf: lightweight job loading for read-only endpoints
- `6aacd92` fix: restore PDFs from S3 ZIP, skip existing, filename mismatch
- `d73971e` fix: remove in-memory cache — always read job state from DB
- `e8f0686` fix: persist PDFs to S3, survive redeploys
- `3a3a71e` fix: detect and report lost data files after redeploy
- `346e6b6` fix: prevent silent thread death in all background tasks
- `551b3bb` fix: persist interrupted status to DB for SSE
- `746f35a` / `2ef6a87` fix: auto-migrate all tables on startup, log errors, never drop
- `0f583d2` fix: SSE reads from DB; per-task cancel/restart
- `f5fbf1a` fix: persist task status to DB for multi-worker

### Template generator (earlier)
- `4262218` / `4ea9dbc` fix: image media type from magic bytes
- `fea0139` feat: image intent (embed vs design reference) · `8063f07` feat: embedded images + PDF download · `37aff30` feat: multi-file upload

---

## Session Notes

> Append a dated entry per session: what was done, how it was verified, gotchas discovered.

### 2026-06-13 — Context-system refinement + AI planning
- `code-standards.md`: added **Design Principles & Patterns** (SOLID anchored to `storage`/`email_providers`; GoF reference table; "earn the abstraction" guardrails).
- `architecture.md`: added **Pluggable Providers (Email & SMS)** (SMS to mirror email's provider/factory/encrypted-settings pattern — planned) and **AI Generation & Model Tiering** (the planned AI seam, `messages[]` contract, per-task tiering).
- `project-overview.md`: corrected wording — photos is *collection*, not a delivery channel; "multi-tenant" → precise per-user tenancy (no orgs/SSO).
- `roadmap.md`: billing hardening marked done pending the **Paystack route test**; added the **AI capabilities upgrade** workstream (seam → SMS composer → in-job template editing).
- **Removed the `/debug/db` route** (`app/main.py`) — unauthenticated; built 2026-05-23 for DB diagnosis during the auto-migration work, no longer needed. Synced the route references in `architecture.md` and `roadmap.md`.
- Decision recorded: **AI model tiering + thin seam** (see Decisions).
- Maintainer reported: billing hardening done; only the Paystack route test remains.

### 2026-06-10 — Context system created
- Built the 9-file context system in `context/` (this directory), grounded in the codebase + git history: project-overview, architecture, code-standards, library-docs, **failure-modes** (diagnostic backbone), ui-guidelines, ui-registry, roadmap, progress-tracker. Root `CLAUDE.md` added as the entry point.
- Items needing the maintainer's confirmation: Out-of-Scope list (project-overview), Phase C priorities (roadmap), watchlist items above.

---

## Update Protocol

After every session, update:
1. **Current Status** — focus / last completed / next.
2. **Active Issues** — new bugs in, fixed bugs out (with the commit).
3. **Decisions** — any new load-bearing decision *with the why*.
4. **Session Notes** — dated entry: changes, verification performed, gotchas.
5. Cross-file: new failure class → `failure-modes.md`; new/changed component → `ui-registry.md`; scope change → `roadmap.md`.
