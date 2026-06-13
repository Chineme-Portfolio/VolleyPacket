# Project Overview

## About the Project

VolleyPacket is a full-stack platform for **generating and distributing personalized documents in bulk**. A user uploads a spreadsheet of recipients (e.g. exam candidates), chooses or AI-generates an HTML template, and the system renders a personalized PDF for every row using WeasyPrint. It then delivers those documents to recipients by **email and SMS**, tracking every send and producing a delivery report. It can also collect and optimize recipient photos from cloud links — to embed into the documents or hand back as a downloadable bundle.

The original and primary use case is **exam/candidate packet distribution**: an administrator has a list of candidates in Excel, needs to produce a personalized slip or packet for each one, and email and/or text it to them, then download proof of delivery.

The whole platform is **multi-user with strict per-user data isolation** — each account is its own tenant. Users sign in, configure their own email provider, and work within their own subscription tier; no user can see another's jobs, templates, or settings. There are no organizations, teams, or SSO (Google login is social sign-in, not SAML/SSO) — org-level accounts are a future roadmap item.

---

## The Problem It Solves

Distributing personalized documents to hundreds or thousands of people is painful and error-prone. The data is messy (typo'd emails, phone numbers stored as numbers, photo links from Google Drive). Mail-merge tools stop at the document and don't send anything. Email tools don't generate documents. Nothing handles the full pipeline — clean the data, build the document, send it, and prove it was sent.

VolleyPacket owns the entire pipeline: it ingests a messy spreadsheet, repairs the data, renders a document per recipient, sends it over the right channel, and reports exactly who received what — with the ability to pause, resume, and cancel long-running batches at any point.

---

## Architecture at a Glance

VolleyPacket is **two applications** in one repository:

```
app/         → Python / FastAPI backend  (API, jobs, tasks, AI, billing, storage)
frontend/    → Next.js 16 frontend       (UI, auth, dashboards, job control)
```

The backend is the brain (all business logic, all long-running work); the frontend is a thin client that calls the API and renders live progress. They are deployed separately. See `architecture.md` for the full structural contract.

---

## Pages (frontend routes)

```
/                    → Landing page (marketing, demo, CTAs)
/login               → Email/password + Google OAuth sign-in
/signup              → Account creation
/dashboard           → Overview: stats, recent jobs, quick start
/jobs                → Job list + "new job" flow
/jobs/[id]           → Job detail: template, column mapping, task panels, downloads
/templates           → Browse templates (all / mine / public / system)
/settings            → Settings hub
/settings/email      → Configure email provider (Resend / SendGrid / SMTP presets)
/settings/billing    → Subscription management (Stripe / Paystack)
/guides              → Help documentation
/blog                → SEO blog index
/blog/[slug]         → Individual blog post
```

---

## Core Concepts

### A "Job"
A job is one batch of work built around a single uploaded recipient file. It owns:
- the **candidate data** (the parsed spreadsheet)
- a **template** (attached or AI-generated)
- a **job mode** (see below)
- **email/SMS content** (with `{Placeholder}` merge fields)
- four independent **tasks**: `pdfs`, `emails`, `sms`, `photos`

Each task runs asynchronously with its own live status (progress, counters, errors) and can be paused, resumed, or cancelled independently.

### Job Modes
| Mode | Meaning |
| --- | --- |
| `dynamic_pdf` | Generate a personalized PDF per recipient and attach it to their email |
| `static_attachment` | Attach the same uploaded file to every recipient |
| `email_only` | Send email/SMS with no attachment |

### Tasks
| Task | What it does |
| --- | --- |
| `pdfs` | Render a PDF per row from the template (WeasyPrint), zip them, persist to storage |
| `emails` | Send per-recipient email via the user's configured provider, with attachment per mode |
| `sms` | Send SMS via BulkSMS (Nigeria), with phone-number normalization |
| `photos` | Download + optimize recipient photos (Google Drive / Dropbox / direct URLs), zip them |

---

## Core User Flow

1. **Sign up / sign in** — email+password or Google. JWT stored client-side.
2. **Configure email provider** — under Settings → Email; credentials are encrypted at rest.
3. **Create a job** — upload a candidate Excel/CSV. The backend auto-detects the header row, reads cells as strings (to preserve phone numbers and dates), and normalizes column names.
4. **Choose a job mode** and **attach a template** — pick an existing template or AI-generate one from an uploaded document/image.
5. **Map columns to placeholders** — the system auto-matches spreadsheet columns to template `{Placeholders}`; the user confirms or overrides via the column mapper.
6. **Compose email / SMS content** — with `{Placeholder}` merge fields; an AI assistant can draft subject + body.
7. **Run tasks** — start PDF generation, email send, SMS send, or photo download. Each streams live progress to the UI and can be paused/resumed/cancelled.
8. **Download outputs** — PDF zip, photo zip, and a multi-sheet delivery report (sent / not-sent / invalid / failed).

Tier limits are enforced throughout (active job count, row count, AI message quota, template access).

---

## Data Architecture

Three sources of truth, kept deliberately separate:

| What | Where it lives | Notes |
| --- | --- | --- |
| **Job + user state** | PostgreSQL (prod) / SQLite (local) | `JobRow` is the authority for status and task progress |
| **Files** (spreadsheets, PDFs, zips, logs) | S3 (Railway) or local filesystem | Abstracted behind the storage layer; must survive redeploys |
| **Live task progress** | `tasks_json` on `JobRow` | Written by background threads; read by the SSE stream |

Key principle: **the database is the source of truth, not process memory.** Every API request loads a fresh job from the DB. Background threads hold their own reference. This matters because the app runs **multiple workers** — see `architecture.md` and `failure-modes.md`.

---

## Subscription Tiers

| Tier | Active jobs | Rows (no photos) | Rows (with photos) | AI messages/mo | Templates |
| --- | --- | --- | --- | --- | --- |
| **Free** | 3 | 5,000 | 3,000 | 10 | Free only |
| **Classic** | ∞ | 10,000 | 7,000 | 100 | All |
| **Pro** | ∞ | ∞ | ∞ | ∞ | All + publish |

Billing is region-routed: **Stripe** for international (USD), **Paystack** for Nigeria (NGN).

*(Verify exact limits against `app/services/billing.py` when refining — these reflect the current read of the code.)*

---

## Current State

VolleyPacket is **~halfway built and in a stabilization phase**, not greenfield. The core pipeline (upload → template → PDF → delivery by email/SMS, plus photo collection and delivery reports) works end to end. Active branch is `v2.0`.

Recent work has concentrated almost entirely on **reliability of the async job system** under real deployment conditions:
- multi-worker task-state consistency (DB-backed state, `tasks_json` merging)
- background-thread durability (no silent thread death, stale-task recovery on boot)
- file persistence across Railway redeploys (S3 round-tripping of PDFs/data)
- live progress correctness (SSE reading from DB, pause/resume/cancel across workers)
- data-ingestion robustness (header detection, strings-not-floats, email repair)

The recurring failure modes from this work are catalogued in `failure-modes.md`. That file — not a feature roadmap — is the center of gravity for this project right now.

---

## In Scope

- Per-user accounts + auth (email/password + Google OAuth), with every resource scoped per user
- Candidate file upload + parsing (Excel/CSV) with messy-data repair
- Template library (system + user templates, public/private, tier-gated)
- AI template generation from uploaded documents/images (Claude)
- AI email drafting (Claude)
- Personalized PDF generation (WeasyPrint), three job modes
- Multi-channel distribution: email (Resend/SendGrid/SMTP), SMS (BulkSMS)
- Photo download + optimization from cloud links
- Live task progress with pause/resume/cancel (SSE)
- Delivery reporting (multi-sheet Excel)
- Subscription tiers + billing (Stripe + Paystack), region routing
- Local + S3 storage, surviving redeploys

## Out of Scope (for now)

*(To be confirmed with you — drafted from what the code does NOT do.)*
- WhatsApp or push-notification channels
- Scheduled / recurring job runs (jobs are manually triggered)
- Real-time collaboration / multi-user shared jobs
- In-app document editor (templates are HTML, AI- or hand-authored)
- Non-Nigerian SMS providers
- Analytics dashboards beyond the basic stat cards

---

## Target User

An administrator or operations person who needs to **send personalized documents to many people from a spreadsheet** — for example:
- exam boards / schools issuing candidate slips or result packets
- organizations issuing certificates, invitations, or notices
- anyone doing personalized bulk mail-merge + send + proof-of-delivery

They have messy real-world data, need it to "just work," and need to see exactly what was sent and what failed.

---

## Success Criteria

- A user can go from spreadsheet upload to first batch of sent documents without hand-editing data.
- Messy emails and phone numbers are repaired or clearly flagged as invalid — never silently dropped.
- Long-running tasks show accurate live progress and can be paused/resumed/cancelled reliably.
- Task state stays correct across multiple workers and across redeploys — no "stuck at 28%," no false "running," no lost PDFs.
- Generated files survive redeploys and remain downloadable.
- Tier limits are enforced consistently on every relevant endpoint.
- The delivery report accurately reflects who received what.
