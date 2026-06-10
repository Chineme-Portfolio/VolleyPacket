# Architecture

The structural contract for VolleyPacket. Where code lives, how the pieces talk to each other, and the rules that must never be violated. Read this before touching anything that crosses a boundary — and read the **Async Task Execution Model** section before touching anything job-related, because that is where every hard bug in this project has lived.

---

## Stack

### Backend (`app/`)

| Layer | Tool | Purpose |
| --- | --- | --- |
| Framework | FastAPI (Python 3.11) | API server |
| ORM / DB | SQLAlchemy → PostgreSQL (prod) / SQLite (local) | Users, jobs, templates, subscriptions |
| Data processing | pandas + openpyxl | Spreadsheet parsing and manipulation |
| PDF rendering | WeasyPrint | HTML → PDF (needs Pango system libs — see Dockerfile) |
| AI | Anthropic Claude (`claude-sonnet-4-6`) | Template generation, email drafting |
| Email | Resend / SendGrid / SMTP (pluggable providers) | Per-user configured delivery |
| SMS | BulkSMS Nigeria | SMS channel |
| Billing | Stripe (intl/USD) + Paystack (Nigeria/NGN) | Subscriptions |
| Storage | boto3 S3 (Railway bucket) or local filesystem | Files: uploads, PDFs, zips, logs |
| Auth | PyJWT (HS256) + bcrypt + Google OAuth | Sessions and identity |
| Secrets at rest | cryptography (Fernet) | Email provider credentials |
| Server | gunicorn + uvicorn workers (**2 workers**) | Production process model |

### Frontend (`frontend/`)

| Layer | Tool | Purpose |
| --- | --- | --- |
| Framework | Next.js 16 (App Router) + React 19 | UI |
| Styling | Tailwind CSS v4 (`@theme` in globals.css) | Green-brand utility styling |
| Animation | Framer Motion | Logo/landing animations |
| Font | Inter via `next/font/google` | `--font-inter` variable |
| API access | `src/lib/api.ts` (single fetch wrapper) | All backend calls |

### Deployment

- **Railway**, two services: backend (Dockerfile, gunicorn `--workers 2 --timeout 120`) and frontend (own Dockerfile).
- Backend container needs WeasyPrint's apt packages (Pango, GDK-Pixbuf, etc.) — both `Dockerfile` and `nixpacks.toml` install them.
- Railway filesystem is **ephemeral** — anything not in the DB or S3 is lost on redeploy.
- Railway injects S3 vars (`BUCKET`, `ACCESS_KEY_ID`, …) when an object store is linked; storage auto-switches to S3 when `BUCKET` exists.

---

## Repository Structure

```
/
├── context/                  → This context system (9 files)
├── Dockerfile                → Backend image (WeasyPrint deps + gunicorn)
├── railway.json / nixpacks.toml
├── requirements.txt
├── app/                      → FastAPI backend
│   ├── main.py               → App factory, CORS, router registration, lifespan (init_db)
│   ├── config.py             → Env vars + folder paths (single source for both)
│   ├── database.py           → SQLAlchemy models, engine, additive auto-migration
│   ├── models.py             → Pydantic models (TemplateConfig, TaskStatus, JobResponse…)
│   ├── dependencies.py       → get_current_user (JWT via HTTPBearer)
│   ├── middleware/logging.py → Request logging middleware
│   ├── routes/               → HTTP layer ONLY — thin handlers, no business logic
│   │   ├── auth.py           → /auth: signup, login, google-login, me
│   │   ├── upload.py         → /upload: parse document/image for template generation
│   │   ├── generate.py       → /generate-template (+ /preview): AI template creation
│   │   ├── templates.py      → /templates: CRUD, visibility, preview, download
│   │   ├── jobs.py           → /jobs: the big one — job CRUD, task start/control, SSE, downloads, logs, column mapping
│   │   ├── email_settings.py → /email-settings: provider config (encrypted)
│   │   ├── billing.py        → /billing: tiers, checkout, portal, cancel/resume, webhooks (/webhook, /webhook/paystack)
│   │   └── ai_email.py       → /ai-email/generate: AI email drafting
│   └── services/             → ALL business logic
│       ├── jobs.py           → Job class, DB persistence, control flags, email cleaning ★ core
│       ├── pdf_tasks.py      → PDF generation task (thread)
│       ├── email_tasks.py    → Email send task (thread)
│       ├── sms_tasks.py      → SMS send task (thread)
│       ├── photo_tasks.py    → Photo download task (thread, 4-worker pool)
│       ├── report_tasks.py   → Delivery report (multi-sheet Excel)
│       ├── template_renderer.py → fill_placeholders, render_pdf, html preview
│       ├── ai_generator.py   → Claude template generation
│       ├── read_data.py      → Spreadsheet ingestion (header detect, strings-only)
│       ├── document_parser.py→ PDF/DOCX/HTML/TXT text extraction
│       ├── storage.py        → Local/S3 storage abstraction ★ core
│       ├── auth.py           → bcrypt, JWT, Google token verify, user CRUD
│       ├── encryption.py     → Fernet encrypt/decrypt for stored credentials
│       ├── billing.py        → TIERS dict, tier guards, AI usage counters
│       ├── paystack.py       → Paystack REST wrapper
│       ├── generator.py      → safe_filename, photo download helpers
│       ├── allocator.py      → Exam slot allocation utility (legacy v1 feature)
│       └── email_providers/  → base.py (interface) + resend/sendgrid/smtp + factory
└── frontend/
    └── src/
        ├── app/              → Pages: /, login, signup, dashboard, jobs, jobs/[id],
        │                       templates, settings{,/email,/billing}, guides, blog, blog/[slug]
        ├── components/       → 18 components (see ui-registry.md)
        └── lib/
            ├── api.ts        → THE fetch wrapper + every API function + shared interfaces
            ├── auth.tsx      → AuthProvider/useAuth (token in localStorage `vp_token`)
            ├── errors.ts     → parseApiError / parseFetchError → human-readable messages
            ├── status.ts     → statusBadge() — status → Tailwind badge classes
            └── blog.ts       → Static blog content
```

---

## System Boundaries

| Location | Owns | Must never |
| --- | --- | --- |
| `app/routes/` | HTTP: auth dependency, request validation, calling services, shaping responses | Contain business logic, spawn threads directly, hold state |
| `app/services/` | All business logic, task bodies, DB persistence | Import from routes; assume a single worker |
| `app/services/*_tasks.py` | Background thread bodies (`run_*`) + spawners (`start_*`) | Run without try/except; skip `should_stop()` checks; write control flags via `save()` |
| `app/database.py` | Schema + engine + additive migration | Drop/alter columns destructively |
| `frontend/src/lib/api.ts` | Every backend call + shared types | Be bypassed — components never call `fetch` directly to the API |
| `frontend/src/components/` | UI + local state | Hold auth logic (that's `lib/auth.tsx`) or build URLs by hand |

---

## The Async Task Execution Model ★

This is the heart of the system and the source of nearly every hard bug so far. Internalize this before changing anything in `jobs.py`, `*_tasks.py`, or the SSE route.

### The physical reality

- Production runs **gunicorn with 2 uvicorn workers** = 2 separate Python processes.
- A background task is a **daemon thread inside whichever worker received the start request**.
- The *next* API request (status poll, cancel click, SSE connection) can land on the **other** worker, which has no view of that thread's memory.
- Railway **redeploys kill all processes** — threads die mid-run, and local files vanish.

### The rules that follow from it

1. **The database is the only source of truth.** There is deliberately *no in-memory job cache* (it was removed — commit `d73971e`). Every API request loads a fresh `Job` from the DB via `get_job_for_user()` / `get_job_light_for_user()`. Only the background thread holds a long-lived `Job` reference.

2. **`Job.save()` merges `tasks_json`, never blind-writes** (`app/services/jobs.py:save`). A save from worker B (e.g. user edits email content) must not clobber the progress the thread on worker A just wrote. Merge rules:
   - terminal states (`complete`/`cancelled`/`failed`/`interrupted`) in DB win over non-terminal in memory
   - higher progress wins
   - exception: a fresh task start (`running`, progress 0, total > 0) may override — that's a legitimate restart.

3. **Control signals bypass `save()`.** `cancel_task()`, `pause_task()`, `resume_task()` write `stop_flags_json` / `paused_json` directly as dedicated columns, so the running thread's periodic `save()` can never overwrite a cancel/pause signal. `save()` also *reads* stop flags from the DB before writing tasks, honoring externally-set cancels.

4. **Threads poll for signals.** Every task loop calls `job.should_stop(task)` regularly. It checks memory flags, refreshes flags from the DB every **3 seconds** (cross-worker propagation), and blocks while paused (0.5s sleep loop). A loop iteration that doesn't call `should_stop()` is a loop that can't be cancelled.

5. **Threads persist progress** every 10 rows and on completion (`(idx + 1) % 10 == 0`). The SSE stream reads from the DB, so unpersisted progress is invisible progress.

6. **Stale-task recovery happens ONCE, at startup.** `mark_stale_running_tasks()` (called from `init_db()`) marks any DB-`running` task as `interrupted` — if it says running while this process is booting, its thread is dead. This must NOT run on per-request job loads: in multi-worker, a task may be legitimately running on the *other* worker (that bug already happened).

7. **Whole thread body wrapped in try/except.** On any unhandled exception, the task status must be set to `failed` with the error message and saved — silent thread death leaves a forever-"running" task (commit `346e6b6`).

8. **Lightweight jobs never save.** `get_job_light()` skips loading the DataFrame for speed (~instant vs ~3s). Calling `save()` on one would write `candidate_count=0` and empty data. Light jobs are for read-only endpoints ONLY.

### Live progress (SSE)

```
Frontend EventSource → GET /jobs/{id}/stream (app/routes/jobs.py:162)
        ↓
Loop: load job (light) fresh from DB → emit task statuses as SSE events
        ↓
Poll cadence: fast (~2s) while any task is running, slow (~10s) when idle
```

The stream never reads from process memory — that worker may not be running the thread.

### Task lifecycle

```
POST /jobs/{id}/pdfs/generate
        ↓
route: auth → load full Job from DB → tier/state checks → clear stale pause flag
        ↓
start_pdf_generation(job) → threading.Thread(target=run_pdf_generation, daemon=True).start()
        ↓
thread loop per row:
    job.should_stop("pdfs")?  → exit cleanly (status cancelled)
    render row → update counters
    every 10 rows → job.save()  (progress visible to SSE + other worker)
        ↓
finish: zip outputs → store.save_local_file(zip) → status complete → job.save()
except: status failed + error message → job.save()
```

---

## Storage Layer

`app/services/storage.py` — singleton behind a lazy proxy: `from app.services.storage import store`.

- **Keys are relative paths** (`output/pdfs_{job_id}.zip`, `data/jobs/{id}/data.xlsx`); local paths are `{BASE_DIR}/{key}`. Convert with `_key_from_local()`.
- **Backend selection:** `STORAGE_BACKEND=local|s3`, else auto: S3 if `BUCKET` env var exists (Railway), local otherwise. Local-on-prod logs a loud warning.
- **Write pattern (dual-write):** write the file locally first, then `store.save_local_file(path)` syncs it to S3. S3 failures are logged, not raised — local copy remains.
- **Read pattern:** `store.ensure_local(key)` — returns local path, downloading from S3 if missing locally. *Never* `open()` a path you haven't ensured.
- **Serving:** `store.serve()` / `serve_inline()` — FileResponse locally, presigned URL redirect (1h) for S3.
- **Durability convention:** every artifact a user can download later (PDF zips, photo zips, reports, logs, job data xlsx) must be synced to storage, because local disk dies on redeploy. PDFs are restored on demand: ZIP from S3 first (fast), individual files as fallback (`Job._restore_pdfs_from_storage`).

---

## Database Schema

Engine: `DATABASE_URL` env (Postgres; `postgres://` auto-rewritten to `postgresql://`) or SQLite at `data/volleypacket.db`. `pool_pre_ping=True`. **Auto-migration is additive-only** — on startup, missing columns are added with safe defaults; nothing is ever dropped.

### `users`
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | UUID |
| email | str unique | |
| password_hash | str nullable | null for Google users |
| auth_provider | str | "local" / "google" |
| tier | str | "free" / "classic" / "pro" |
| region | str nullable | ISO country code ("NG", "US") — routes billing |
| created_at | datetime | |

### `jobs` (JobRow)
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | 8-char UUID |
| owner_id | str FK users | every query scopes by this |
| status | str | created / running / paused / complete / failed / cancelled |
| timestamp | str | "YYYYMMDD_HHMMSS" — used in log/file names |
| candidate_file | str | original upload filename |
| candidate_count | int | row count (so list views skip the DataFrame) |
| columns_json | text | JSON array of column names |
| template_id | str nullable | |
| job_mode | str | dynamic_pdf / static_attachment / email_only |
| email_subject / email_body / sms_body | text | with `{Placeholder}` fields |
| cancelled | bool | job-level kill |
| column_mapping_confirmed | bool | |
| paused_json | text | per-task pause flags — **written directly, not via save()** |
| stop_flags_json | text | per-task stop flags — **written directly, not via save()** |
| tasks_json | text | serialized TaskStatus per task — **merge-written by save()** |
| created_at / updated_at | datetime | |

### `templates` (TemplateRow)
| Column | Type | Notes |
| --- | --- | --- |
| id | str PK | |
| name / description | str | |
| owner_id | str FK nullable | null = system template |
| owner_name | str | display name, default "VolleyPacket" |
| visibility | str | "private" / "public" |
| tier_required | str | gates access by user tier |
| config_json | text | full TemplateConfig (html_content + placeholders) |

### `email_settings`
One row per user. `provider_name` + `credentials_encrypted` (Fernet JSON) + `from_name`/`from_email`.

### `subscriptions`
Dual-provider: `payment_provider` ("stripe"/"paystack"), Stripe customer/subscription IDs, Paystack codes, `tier`, `status` (active/cancelled/past_due/trialing), period bounds, `cancel_at_period_end`.

### `ai_usage`
`(user_id, year_month, count)` — monthly AI message quota counter.

Job **data files** are NOT in the DB: `data/jobs/{job_id}/data.xlsx` (+ `valid_data.xlsx`, `invalid_data.xlsx`) in storage.

---

## Auth Model

- **Backend:** `Depends(get_current_user)` on every protected router (everything except `/auth/*`, `/`, `/debug/db`, billing webhooks). JWT HS256, 24h expiry, `sub` = user id. Google login verifies `id_token` against Google's tokeninfo endpoint with `GOOGLE_CLIENT_ID`.
- **Frontend:** token in `localStorage.vp_token`; `lib/api.ts` injects `Authorization: Bearer` on every call and **auto-logs-out on 401** (clears `vp_*` keys, redirects to /login). `AuthProvider` hydrates the user on mount via `/auth/me`.
- **Ownership:** every job/template access goes through `get_job_for_user()` / owner checks — a user can never load another user's job. Never add an endpoint that loads a job by ID without the user filter.

---

## Billing & Tier Enforcement

Source of truth: `TIERS` dict in `app/services/billing.py` — never hardcode limits elsewhere.

| Guard | Where enforced | Rule |
| --- | --- | --- |
| `check_job_limit` | POST /jobs | free: max 3 active jobs |
| `check_row_limit` | POST /jobs (+ re-upload) | free 5k / classic 10k / pro ∞ — stricter (3k/7k) if any column name matches photo/image patterns |
| `check_ai_limit` + `increment_ai_usage` | /generate-template, /ai-email/generate | free 10, classic 100, pro ∞ per month |
| `check_template_access` | POST /jobs/{id}/template | tier rank ≥ template.tier_required |

Region routing: `region == "NG"` → Paystack/NGN, else Stripe/USD. Webhooks: `/billing/webhook` (Stripe — payload parsed as **plain JSON dicts**, not SDK objects) and `/billing/webhook/paystack`. Webhook handlers update `subscriptions` + `users.tier`.

---

## Environment Variables

| Variable | Used in | Notes |
| --- | --- | --- |
| `SECRET_KEY` | config.py | **required** — app refuses to boot without it |
| `ENCRYPTION_KEY` | encryption.py | Fernet key for stored credentials |
| `GOOGLE_CLIENT_ID` | auth | optional — blank disables Google login |
| `ANTHROPIC_API_KEY` | ai_generator, ai_email | |
| `DATABASE_URL` | database.py | present = Postgres; absent = SQLite |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_CLASSIC` / `STRIPE_PRICE_PRO` | billing | |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_WEBHOOK_SECRET` / `PAYSTACK_PLAN_CLASSIC` / `PAYSTACK_PLAN_PRO` | paystack | |
| `BULKSMS_API_TOKEN` / `BULKSMS_API_URL` | sms_tasks | fail-fast guard if missing when SMS starts |
| `FRONTEND_URL` | billing redirects | default http://localhost:3000 |
| `CORS_ORIGINS` | main.py | comma-separated, required in prod |
| `STORAGE_BACKEND` | storage.py | force "local"/"s3"; else auto-detect via `BUCKET` |
| `BUCKET`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `ENDPOINT`, `REGION` | storage.py | Railway-injected; `S3_*`/`AWS_*` variants also accepted |
| `NEXT_PUBLIC_API_URL` | frontend api.ts | default http://localhost:8000 |

Add any new variable to `.env.example` with a comment the moment it's introduced.

---

## Invariants

Rules that must never be violated. Each one exists because its violation already caused (or narrowly avoided) a production bug — see `failure-modes.md` for the war stories.

**Task state & concurrency**
- The DB is the source of truth for job/task state. Never reintroduce an in-memory job cache. Every request loads fresh.
- Never write `tasks_json` except through `Job.save()`'s merge logic (or the narrow direct-writes inside cancel/pause/resume).
- Never write pause/stop/cancel signals through `save()` — always the dedicated direct-to-DB methods.
- Every background loop iteration checks `job.should_stop(task)`; progress is saved at least every 10 rows.
- Every `run_*` task body is fully wrapped: on exception → status `failed` + error message + `save()`. No silent thread death.
- `mark_stale_running_tasks()` runs at startup only — never on per-request load.
- Objects from `get_job_light*()` never call `save()`.
- New long-running work follows the existing pattern: `start_*` spawner + `run_*` body + TaskStatus + should_stop + periodic save. No new mechanisms (no asyncio tasks, no celery) without an explicit decision.

**Files & storage**
- All file access goes through `store` — `ensure_local()` before reading, `save_local_file()`/`save_bytes()` after writing. Never assume a local file survives a redeploy.
- Every user-downloadable artifact is synced to storage at creation time.
- Storage keys are relative paths; never hardcode absolute paths outside `config.py`.

**Data ingestion**
- Spreadsheet cells are always read **as strings** (phone numbers, exam numbers, and dates are destroyed by float coercion).
- Emails are cleaned via `clean_email()` then validated; invalid rows go to `invalid_data` with a Reason — never silently dropped, never sent to.

**Auth & tenancy**
- Every job/template/data access is scoped to the authenticated user (`get_job_for_user`, owner checks). No exceptions.
- Email provider credentials are Fernet-encrypted at rest and never logged.
- JWT secret and all keys come from env — nothing secret in code.

**API contract**
- Errors return FastAPI's `{"detail": "..."}` shape with proper status codes; the frontend's `parseApiError` depends on it.
- All frontend → backend calls go through `lib/api.ts`. New endpoints get a typed function there.

**Billing**
- Tier limits live only in `TIERS` (billing.py). Guards run server-side on the endpoint — never trust the client.
- Stripe webhook payloads are parsed as plain JSON dicts; always verify the webhook signature.

**Database**
- Schema changes are additive (new nullable/defaulted columns). The auto-migration never drops anything; neither do you.
