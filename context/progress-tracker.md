# Progress Tracker

Update this file after every working session. Any agent reading this should immediately know the current state, what was recently done and why, and what's next. This is the project's memory across sessions — the decisions log keeps settled questions settled.

---

## Current Status

**Branch:** `v2.0` (default branch for PRs: `main`)
**Phase:** B — Stabilization (see `roadmap.md`)
**Current focus:** Stabilization audit — **delivery report + log downloads** fixed and upgraded (multi-channel, accurate, streamed). Open from Phase B: **testing the Paystack route end-to-end** (checkout → webhook → tier change).
**Last completed:** Report/log audit — fixed the "successful sends in the failure sheet" bug + the gibberish downloads; report now covers email/SMS/PDF/photos, available once any task completes (this session).
**Next:** Live-verify the report + log downloads on a real backend → live-verify SMS providers (Feature 3) → the unified AI seam → Paystack route test.

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
- **In-job template editing shipped ahead of the AI seam, on a focused edit function.** Rather than block the feature on the full seam refactor, `edit_template_with_ai()` uses the existing Anthropic client directly with the AI-quota pair and the `messages[]`/edit-don't-regenerate/fork-don't-mutate rules already honored. When the seam lands it should *absorb* this call site (and email/SMS) — the model id already lives in one place (`config.AI_MODEL_TEMPLATE_EDIT`). The job-local fork is stored in `JobRow.template_json`; rendering is unchanged because PDF generation already reads `job.template`.

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

### 2026-06-13 — Audit fix: delivery report + log downloads
- **Report "successful sends in failure sheet" bug** (failure-modes [14]): `generate_report` read the email log only via `job.log_path`, which `from_db_row` resets to `None` — so on every (fresh-loaded) report download the log was never read and all candidates fell into "Not Sent". Rewrote `report_tasks.py` to read each task's log by deterministic key from `job.timestamp`; the report is now **log-driven** (Summary + one sheet per channel), so it can't re-derive status wrong.
- **Gibberish downloads** (failure-modes [15]): `store.serve` redirects to an S3 presigned URL when the file isn't local (post-redeploy/other worker), and the authenticated browser fetch could save a garbled body. Logs + report now **stream** via `ensure_local` → `FileResponse` (`text/csv; charset=utf-8`), never a redirect. (Big ZIPs keep presigned.)
- **Multi-channel report**: now covers Email/SMS/PDF/Photos + Invalid Emails; **available once ANY task completes** (was emails-only), regenerated per download so it reflects the latest. Added a **per-row PDF log** (`pdf_run_*.csv`) and made PDF generation **continue-on-error** (one bad row no longer aborts the batch); added `pdfs` to `LOG_TYPES` so the PDF log is viewable/downloadable.
- Files: `report_tasks.py` (rewrite), `pdf_tasks.py` (log + resilience), `routes/jobs.py` (gate→any-task, stream downloads, LOG_TYPES), `jobs/[id]/page.tsx` (report shows when any task complete).
- **Verified**: report unit test (sent=success with `log_path=None`; Email 2/1, SMS 1/0, PDFs 1/1; multi-channel sheets); py_compile; tsc + next build. **Not yet**: live download on prod (S3) to confirm the gibberish fix end-to-end.

### 2026-06-13 — Feature 3: pluggable SMS providers + multi-country
- **SMS now mirrors email's provider system.** New `app/services/sms_providers/` (`SmsProvider` ABC + `SmsMessage{to,body,sender_id}`) with 5 REST adapters — BulkSMS, Twilio, Vonage, Termii, Africa's Talking — + `create_sms_provider` factory + `PROVIDER_FIELDS`.
- **Multi-country**: new `phonenumbers` dep; `to_e164(raw, default_region)` parses any number to canonical E.164 (NG local / bare-234 / +E.164 / US / UK …); each provider keeps or strips the `+` for its API. Replaces the Nigeria-only `normalize_phone`.
- **Per-user config**: new `sms_settings` table (`provider_name`, `credentials_encrypted`, `sender_id`, `default_region`) + `/sms-settings` routes (GET/POST/DELETE/test/providers) mirroring email; Fernet-encrypted creds. `sms_tasks` now depends only on `SmsProvider`; `/sms/send` loads the user's provider (env BulkSMS as transition fallback via `SMS_DEFAULT_SENDER`).
- **Frontend**: `settings/sms/page.tsx` (5 providers + per-provider How-Tos + `sender_id` + default-country + test-to-number), Settings hub entry + `SmsIcon`, `getSmsProviderStatus` in `api.ts`.
- **Docs**: architecture.md SMS flipped planned→implemented + `sms_settings` schema; roadmap item done; code-standards approved deps += `phonenumbers`.
- **Verified**: py_compile; `to_e164` across NG/US/UK/bare/junk; factory builds all 5 + `validate_config`; `sms_settings` migration + encrypted round-trip; `tsc` + `next build` (incl. `/settings/sms`). **Not yet**: live sends per provider — BulkSMS verifiable with your token; the other four are best-effort from API docs until creds are available.

### 2026-06-13 — Feature 2: email/SMS expansion + "Ask Volley"
- **"Ask Volley"** is now the brand for all AI drafting (template/email/SMS) — tab labels + chat copy.
- **Email** is now an accordion with **Ask Volley / Rich text / HTML** tabs over `email_body` (subject = plain input). **SMS** got **Edit / Ask Volley** tabs (plain text only — SMS can't render HTML). Template editor's "Prompt" tab renamed to **Ask Volley**.
- **Server-persisted conversations:** new `JobRow.ai_chats_json` (`{template,email,sms}` of `{role,content}`). AI-draft endpoints persist the transcript on each turn; `GET /jobs/{id}/ai-chats` loads it (fast — light loader parses it); `PUT /jobs/{id}/ai-chats/{channel}` handles Clear. The AI calls stay **stateless** (client replays full `messages[]`; DB is the durable backup) — NOT a violation of the "no server-side live conversation state" rule. Template chat migrated off localStorage onto this.
- **New backend:** `draft_email_with_ai` / `draft_sms_with_ai` in `ai_generator.py` (mirror `edit_template_with_ai`); `config.AI_MODEL_EMAIL_SMS` (default `claude-sonnet-4-6`, cheap-tier swappable); routes `POST /jobs/{id}/email/ai-draft` + `/sms/ai-draft` (quota-paired, apply + persist). Old `/ai-email/generate` left in place but unused (frontend wrapper removed).
- **SMS override fix:** removed the silent `DEFAULT_SMS_BODY` fallback in `sms_tasks.py`; `/sms/send` now 400s if `sms_body` is empty — the user's content is the only thing that sends. (Email's identical `DEFAULT_EMAIL_BODY` left as-is — known parallel, out of scope.)
- **New shared frontend:** `AskVolleyChat.tsx` (reusable chat panel) + `RichTextEditor.tsx` (fragment WYSIWYG, contenteditable — no iframe since email body is a fragment). Email/SMS Ask Volley **apply immediately** (auto-save) like the template editor.
- **Verified:** `tsc` + `next build` clean; backend round-trip on SQLite (ai_chats migration + transcript persist + light-load reads); SMS-empty → 400 guard in place. **Not yet:** live AI-call + browser smoke test (needs WeasyPrint + API key).

### 2026-06-13 — In-job template editing (Phase C, first slice)
- **Feature:** edit a job's PDF template inside the job — by AI **prompt**, raw **HTML**, and visible-text **rich text** — in a collapsible accordion on the job page.
- **Fork, don't mutate:** new additive `JobRow.template_json` column holds a job-local `TemplateConfig` copy. `Job.save()` snapshots `job.template` into it (so attach + every save forks automatically); `from_db_row()` prefers it, falling back to the shared `TemplateRow` for old jobs. Library template is never touched. (`app/database.py`, `app/services/jobs.py`).
- **Edit, don't regenerate:** new `edit_template_with_ai()` in `ai_generator.py` passes the current HTML + job columns + sample rows + a client-held `messages[]` transcript to **Opus** (`config.AI_MODEL_TEMPLATE_EDIT`, default `claude-opus-4-8`). Embedded base64 images are stripped to `{EMBEDDED_IMAGE_N}` before the model and re-injected after (reusable `strip_embedded_images`/`reinject_embedded_images`/`extract_placeholders` helpers; the generator now uses them too).
- **Endpoints** (`app/routes/jobs.py`, owner-scoped, blocked while a task runs): `GET/PUT /jobs/{id}/template`, `POST /template/ai-edit` (AI-quota-paired), `POST /template/reset`, `GET /template/preview` (renders first data row).
- **Frontend:** `JobTemplateEditor.tsx` (accordion + 3 tabs + side preview + reset), `lib/templateImages.ts` (client strip/inject mirroring backend), new `api.ts` functions (preview via Blob URL, not data: URL, because templates embed base64). Wired into `jobs/[id]/page.tsx` for `dynamic_pdf` jobs; `TemplateSelector` now confirms before re-forking.
- **Decision:** built a *focused* edit function on the existing Anthropic client rather than blocking on the full AI seam — the seam can absorb it later (logged below).
- **Verified:** `tsc --noEmit` clean; `next build` passes (19 pages, incl. `/jobs/[id]`); fork round-trip on a real SQLite DB — migration adds the column, fork wins over shared template, fallback works, `save()` leaves the library template untouched, two jobs isolated. Image strip/inject round-trips exactly. **Not yet done:** live endpoint + AI-call + browser smoke test (local venv lacks WeasyPrint; needs a real backend + API key). `npm run lint` has pre-existing repo-wide errors (auth.tsx etc.) — none in the new/changed files.
- **Gotcha:** rich-text editor is an iframe (`sandbox="allow-same-origin"`, body `contenteditable`, `execCommand`) so the document's `<style>`/`@page`/images stay intact; serializes `<!DOCTYPE html>` + `documentElement.outerHTML` on save. Confirm `execCommand` works under that sandbox during the live test.

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
