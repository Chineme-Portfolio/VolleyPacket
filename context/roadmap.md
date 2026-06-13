# Roadmap

VolleyPacket's equivalent of a build plan — adapted for a project that is **half-built and stabilizing**, not greenfield. The unit of work here is a *workstream* (a bug class to close or a feature to ship), and stabilization outranks features.

---

## Core Principles

1. **Stabilize before extending.** A new feature built on a flaky task system inherits the flakiness. Reliability workstreams come first.
2. **Every change visible and testable.** Nothing is done until it's been exercised against a running app (see the verification checklist in `code-standards.md`).
3. **Fix the class, not the instance.** When a bug is fixed, close the whole failure class and record it in `failure-modes.md`.
4. **One workstream at a time.** Finish and verify before starting the next.

---

## Phase A — Shipped (the working core)

- [x] Auth: email/password + Google OAuth, JWT sessions, auto-logout on expiry
- [x] Job pipeline: upload → parse (header detect, strings-only, email repair) → job creation
- [x] Template system: CRUD, visibility (private/public/system), tier gating, preview, download
- [x] AI template generation from documents/images (Claude, multi-file, embedded images)
- [x] AI email drafting with placeholder awareness
- [x] PDF generation task (WeasyPrint, photo embedding, zip, S3 persistence + restore)
- [x] Email task (Resend/SendGrid/SMTP providers, encrypted creds, dynamic/static/none attachments)
- [x] SMS task (BulkSMS Nigeria, phone normalization)
- [x] Photo download task (Drive/Dropbox/direct, optimization, zip)
- [x] Delivery report (multi-sheet Excel)
- [x] Task control: start / pause / resume / cancel, cross-worker safe
- [x] Live progress via SSE, DB-backed
- [x] Column mapping (auto-match + manual confirm)
- [x] Job logs viewer + per-log download
- [x] Billing: tiers, Stripe + Paystack, region routing, webhooks, tier guards on endpoints
- [x] Subscription cancel/resume + account deletion
- [x] Storage abstraction (local/S3) with redeploy durability
- [x] Marketing: landing page, SEO metadata/sitemap/robots, blog, guides

## Phase B — Stabilization (current focus)

The async-task reliability war is largely won (see `failure-modes.md` for everything closed). What remains, in priority order:

- [~] **Billing hardening — effectively done; one check remaining**
  - [x] Stripe checkout → webhook → tier change hardened (plain-JSON payloads, stale-customer-ID recovery)
  - [x] Subscription cancel/resume + account deletion shipped (`009abc9`)
  - [ ] **Test the Paystack route end-to-end** (checkout → webhook → tier change) — the last open billing item
  - [ ] Confirm webhook idempotency (replayed events must not double-apply) while testing the Paystack route
- [x] **Removed the temporary `/debug/db` endpoint** (2026-06-13) — was unauthenticated; added 2026-05-23 (`022f439`) to diagnose job-creation / table-presence issues during the Railway DB + auto-migration work, no longer needed.
- [ ] **Active-bug burndown** — work the list in `progress-tracker.md` § Active Issues as items are confirmed
- [ ] **Known soft spots** (candidates — confirm before working):
  - [ ] No retry mechanism for transiently-failed email/SMS rows (currently: rerun the task; skip-existing makes it safe for PDFs, less so for sends)
  - [ ] Tier check happens at template *attach* time only — a downgraded user keeps an attached premium template
  - [ ] No rate limiting on upload/AI endpoints
  - [ ] `clean_email()` over-repair risk — consider flagging repaired addresses in the report

## Phase C — Next features (proposals — confirm priority before building)

### AI capabilities upgrade ★ (planned — full design in `architecture.md` § AI Generation & Model Tiering)

Build order matters — the seam is the foundation the other two sit on:

1. [ ] **AI seam + conversation contract + model tiering** — one `ai` module: `{task, messages[], images?, columns?} → structured output`, with a *static* per-task model map (template tier = top model; email/SMS = cheap), centralized prompt caching, JSON-repair, and the AI-quota check. Delivers "keep context for the session" (real `messages[]`, client-replayed, **stateless backend**) and the tiering. **Not** a dynamic router.
2. [ ] **AI SMS composer** — mirror the email composer for `SmsComposer` (cheap model; bake in SMS constraints: ~160-char segments, plain text, sender ID). Must call `check_ai_limit`/`increment_ai_usage` — don't let a new AI entry point bypass billing.
3. [ ] **In-job template editing** (replaces the old "edit templates conversationally" item) — edit a job's template via prompts, **top-tier** model. Must: (a) **fork to a job-local template copy**, never mutate the shared `TemplateRow`; (b) **edit the existing HTML**, not regenerate; (c) pass the job's real columns and validate every `{Placeholder}` against them.

Template-quality note (top tier alone is not enough): pair the top model with a **WeasyPrint-aware prompt** (no flex/grid) + few-shot good templates + a **render-and-check auto-fix pass** — that drives "first-try" success more than model tier.

### Other proposals

- [ ] Scheduled / deferred job runs (send at a chosen time)
- [ ] Resend-failed-only action (retry just the failed rows from the report)
- [ ] Additional SMS providers (beyond BulkSMS Nigeria) — see the SMS provider plan in `architecture.md`
- [ ] WhatsApp channel
- [ ] Dashboard analytics beyond stat cards (sends over time, success rates)
- [ ] Team/organization accounts (org-level tenancy + roles; would also enable SSO)

## Phase D — Later / ideas parking lot

Anything tempting but unscheduled goes here instead of into a diff: multi-language templates, public API, Zapier integration, custom domains for sender identity.

---

## Workstream protocol

For each workstream: reproduce/baseline → implement smallest sound fix or feature slice → verify per checklist → update `progress-tracker.md` (+ `failure-modes.md` if a failure class opened/closed) → commit (`fix:`/`feat:` conventional message).
