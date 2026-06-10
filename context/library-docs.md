# Library Docs

Project-specific usage patterns for every third-party dependency that has bitten us or could. This file covers how **VolleyPacket** uses each library — the rules, patterns, and gotchas specific to this codebase, several of them paid for with production bugs.

---

## Before Using Any Library

1. **Check for an MCP server or skill** configured for the tool (e.g. Supabase/Stripe MCPs, Next.js guides under `frontend/node_modules/next/dist/docs/`). Live docs beat training data.
2. **Read this file** for the project-specific pattern.
3. Only then fall back to general knowledge — and distrust it for fast-moving APIs (Next.js 16, Anthropic SDK, Stripe).

Order of authority: **live docs/MCP → this file → training knowledge.**

The frontend's `AGENTS.md` already warns: this Next.js version has breaking changes; read `node_modules/next/dist/docs/` before writing Next-specific code.

---

## WeasyPrint (HTML → PDF)

```python
from weasyprint import HTML
pdf_bytes = HTML(string=html_content, base_url=base_dir).write_pdf()
```

**Rules & gotchas:**
- WeasyPrint needs **system libraries** (Pango, PangoCairo, GDK-Pixbuf, GLib, HarfBuzz, Fontconfig…). They are installed in `Dockerfile` AND `nixpacks.toml` — if PDF generation dies with `cannot load library 'libpango…'`, the container image is missing them. Keep both files in sync.
- Rendering is CPU-bound and runs inside the PDF task thread — fine, but never on the request path.
- Templates are full HTML documents with inline CSS; merge fields are `{PlaceholderName}` replaced by `fill_placeholders()` in `template_renderer.py` *before* rendering.
- Photos are embedded by URL/local path at render time; Google Drive links must be converted to direct-download form first (see Photo handling below).
- Local-only CSS: no JS executes; unsupported CSS is silently ignored — verify visual output, don't assume.

---

## pandas + openpyxl (spreadsheet ingestion)

The single most important rule in this project's data layer:

> **Always read cells as strings.** Pandas type inference turns phone numbers into floats (`08065140173` → `8065140173.0`), exam numbers into ints, and dates into Timestamps. That destroys the data we mail-merge. (Commit `88f0883` fixed this; don't regress it.)

Patterns (see `app/services/read_data.py`):
- Header row is **auto-detected** (scan the first ~20 rows for the most-filled row) — uploads often have title/logo rows above the real header.
- After load: `.fillna("")` — downstream code assumes strings, never NaN.
- Column names are normalized (e.g. "Photo Link" → `PhotoLink`); first/last-name splits are detected and combined.
- Round-trips (`data.xlsx`, `valid_data.xlsx`, `invalid_data.xlsx`) use `to_excel(index=False)` and reload with `.fillna("")`.

---

## Anthropic Claude

Used in `app/services/ai_generator.py` (template generation) and `app/routes/ai_email.py` (email drafting).

```python
from anthropic import Anthropic
client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
resp = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=...,
    messages=[...],
)
```

**Rules & gotchas:**
- Model string is `claude-sonnet-4-6` everywhere. Change it in one place at a time, deliberately.
- Template generation returns **JSON containing full HTML** — always parse + validate before saving; never trust the model's JSON blindly. Extract the placeholder list from the HTML, don't ask the model to keep it consistent.
- Image inputs: media type must be detected from **magic bytes**, not the file extension (commits `4ea9dbc`, `4262218` — users upload `.png` files that are really JPEGs). Images are sent base64-encoded.
- Multi-file input is supported (image + document combo) — `parsed_contents` list in the request model.
- Every AI endpoint is quota-gated: `check_ai_limit()` before the call, `increment_ai_usage()` after success. Never add an AI call without the quota pair.
- Prompts include VolleyPacket branding guidance — keep prompt text in the service, not scattered.

---

## Stripe (international billing)

**Hard-won rules (all from production fixes — commits `9208dde`, `345ca24`, `7532883`):**
- **Webhook payloads are parsed as plain JSON dicts**, not SDK objects. Verify the signature with `STRIPE_WEBHOOK_SECRET`, then `json.loads` the payload and access fields with `.get()` — defensive at every level.
- **Never trust a stored `stripe_customer_id`.** Validate it against Stripe before use; if it's stale/deleted (test-mode wipes, env switches), recreate the customer and update the row.
- Checkout: create a Checkout Session with the tier's price ID (`STRIPE_PRICE_CLASSIC` / `STRIPE_PRICE_PRO`), `success_url`/`cancel_url` built from `FRONTEND_URL`.
- Subscription lifecycle: `/billing/cancel` sets `cancel_at_period_end`, `/billing/resume` clears it; webhook events update `subscriptions` + `users.tier`. Tier changes happen **only server-side from webhook/API verification**, never from a client claim.
- Customer Portal (`/billing/portal`) handles payment-method/invoice management — don't rebuild that UI.

## Paystack (Nigeria billing)

- Thin REST wrapper in `app/services/paystack.py`: initialize transaction, verify transaction, fetch/disable subscription. Plan codes from `PAYSTACK_PLAN_CLASSIC` / `PAYSTACK_PLAN_PRO`.
- Region routing: `users.region == "NG"` → Paystack + NGN prices; else Stripe + USD. The `TIERS` dict carries both currencies — UI gets prices from `/billing/tiers?region=…`.
- Webhook at `/billing/webhook/paystack`, verified with `PAYSTACK_WEBHOOK_SECRET`.
- Amounts are in **kobo** (₦ × 100) on the wire.

---

## boto3 / S3 (Railway object store)

All access goes through `app/services/storage.py` — **never import boto3 anywhere else.**

- Backend auto-detects: `BUCKET` env present (Railway-injected) → S3; else local. Force with `STORAGE_BACKEND`.
- Env fallback chain accepts Railway names (`BUCKET`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `ENDPOINT`, `REGION`) and `S3_*`/`AWS_*` variants. Custom `ENDPOINT` makes it work with Railway/MinIO.
- Write = local file + upload (failures logged, not raised). Read = local cache first, download on miss (`ensure_local`). Serve = presigned URL (1h expiry) when not cached locally.
- Railway disk is ephemeral: if a file matters after a redeploy, it must be in S3. PDFs additionally get zipped and the **zip** uploaded — restore prefers the zip (1 download) over N individual files.

---

## SQLAlchemy

- Plain ORM, no Alembic. **`_auto_migrate()`** in `database.py` adds missing columns on startup by diffing model metadata vs the live schema — additive only, safe defaults for NOT NULL, "already exists" races between workers are ignored.
- Therefore: schema changes = add the column to the model class, done. Renames/drops/type-changes need a manual, deliberate migration — don't improvise one.
- `postgres://` URLs are rewritten to `postgresql://` (Railway/Heroku style). `pool_pre_ping=True` handles dropped connections.
- JSON-in-text columns (`tasks_json`, `paused_json`, `stop_flags_json`, `columns_json`, `config_json`) are always `json.loads`-ed defensively with fallbacks — rows can predate columns.
- SQLite locally / Postgres in prod: avoid Postgres-only SQL in app code; `/debug/db` already handles both dialects.

---

## Email providers (Resend / SendGrid / SMTP)

- Abstraction in `app/services/email_providers/`: `base.py` defines `EmailProvider` + `EmailMessage`; `__init__.py` has the `create_provider()` factory and SMTP presets (Gmail, Outlook, Zoho, Yahoo, custom).
- Per-user config in `email_settings` row; credentials are a **Fernet-encrypted JSON blob** (`app/services/encryption.py`, key = `ENCRYPTION_KEY`). Decrypt only at send time; never log decrypted values.
- Adding a provider = new file implementing the base interface + register in the factory + frontend preset in settings/email. Nothing else changes — email_tasks talks to the interface.
- Gmail SMTP needs an **app password** (not the account password) — user-facing copy should say so.

## BulkSMS Nigeria

- `app/services/sms_tasks.py` → `BULKSMS_API_URL` with `BULKSMS_API_TOKEN`. **Fail fast** if the token is missing (don't burn through rows failing one by one — commit `df91e67`).
- Phone normalization: strings only (see pandas rule), `0`-prefixed local numbers → `234…`, handle duplicates/splits. SMS counters track sent/failed/skipped separately.

---

## Photo handling (Google Drive / Dropbox / OneDrive / direct)

- Share links are converted to direct-download URLs (Drive: extract file id → `uc?export=download`). Conversion helpers live in `generator.py` / `photo_tasks.py`.
- Downloads run in a `ThreadPoolExecutor(max_workers=4)` inside the photos task thread.
- Every image is post-processed with Pillow: EXIF auto-rotate, resize to max 800px, JPEG quality 85 — protects WeasyPrint render time and zip size.
- Failures are per-row (logged to the photo CSV), never fatal to the batch.

## Document parsing (PyPDF2 / python-docx / BeautifulSoup)

- `document_parser.py` routes by type: PDF → PyPDF2 text, DOCX → python-docx, HTML → BeautifulSoup, TXT → raw. Output feeds the AI template generator.
- Image-based PDFs return empty text — guard for "empty or too short" and tell the user to upload a different file.

---

## Google OAuth (frontend + backend)

- Frontend `GoogleSignIn.tsx` uses Google Identity Services to obtain an **id_token**, POSTs it to `/auth/google-login`.
- Backend verifies the id_token against Google's tokeninfo endpoint and checks `aud == GOOGLE_CLIENT_ID`. No client secret needed for this flow.
- Google users have `password_hash = NULL`, `auth_provider = "google"` — password login must reject them gracefully.

## Framer Motion / Tailwind v4 (frontend)

- Tailwind v4: configured via `@import "tailwindcss"` + `@theme inline` in `globals.css`. **No `tailwind.config.js`** — add tokens in `@theme`.
- Framer Motion is used for landing-page polish (logo, orbits) — not required for app pages; prefer CSS transitions (`transition-colors`) in the app shell.
- Next 16 + React 19: check `node_modules/next/dist/docs/` before using Next APIs — conventions moved (e.g. proxy vs middleware patterns differ from training data).
