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

- [ ] **Billing hardening — finish the pass** (this is where the last four commits live)
  - [ ] End-to-end verify: checkout → webhook → tier upgrade → limits change, on BOTH providers
  - [ ] Verify cancel/resume → period-end downgrade path
  - [ ] Webhook idempotency (replayed events must not double-apply)
- [ ] **Remove the temporary `/debug/db` endpoint** once DB diagnostics are no longer needed (it's unauthenticated)
- [ ] **Active-bug burndown** — work the list in `progress-tracker.md` § Active Issues as items are confirmed
- [ ] **Known soft spots** (candidates — confirm before working):
  - [ ] No retry mechanism for transiently-failed email/SMS rows (currently: rerun the task; skip-existing makes it safe for PDFs, less so for sends)
  - [ ] Tier check happens at template *attach* time only — a downgraded user keeps an attached premium template
  - [ ] No rate limiting on upload/AI endpoints
  - [ ] `clean_email()` over-repair risk — consider flagging repaired addresses in the report

## Phase C — Next features (proposals — confirm priority before building)

- [ ] Scheduled / deferred job runs (send at a chosen time)
- [ ] Resend-failed-only action (retry just the failed rows from the report)
- [ ] Additional SMS providers (beyond BulkSMS Nigeria)
- [ ] WhatsApp channel
- [ ] Template editor improvements (edit existing AI templates conversationally)
- [ ] Dashboard analytics beyond stat cards (sends over time, success rates)
- [ ] Team/organization accounts

## Phase D — Later / ideas parking lot

Anything tempting but unscheduled goes here instead of into a diff: multi-language templates, public API, Zapier integration, custom domains for sender identity.

---

## Workstream protocol

For each workstream: reproduce/baseline → implement smallest sound fix or feature slice → verify per checklist → update `progress-tracker.md` (+ `failure-modes.md` if a failure class opened/closed) → commit (`fix:`/`feat:` conventional message).
