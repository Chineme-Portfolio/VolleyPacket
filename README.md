# VolleyPacket

**Turn one spreadsheet into thousands of personalized documents — PDFs, emails, and SMS — without doing it by hand.**

> 🚀 The product this grew into is live at **[volleypacket.com](https://volleypacket.com)**.

---

## It started as a Python script on my terminal

I was working with the Rivers State Government. They needed to send thousands of personalized exam invitation letters — PDF generation, email delivery, SMS notifications, photo downloads. All from a spreadsheet.

Sounds simple, right?

Until you're staring at 3,000 rows and realizing:

- 47 emails have typos like `x @gmail.com` or `Q` instead of `@`
- You need each PDF personalized with different names, dates, venues
- Some candidates don't have emails, just phone numbers
- You need to track who received what and who didn't
- And someone asks for the report halfway through

That's the thing about "simple" tasks at scale. They're not simple. They're tedious, error-prone, and nobody wants to do them twice.

So I built a CLI tool. It worked. But every time there was a new batch, I was the bottleneck — someone had to run the commands, watch the logs, re-run the failures.

That's when I decided to turn it into a product.

---

## This repo: where it began

This repository is the origin of VolleyPacket — a command-line tool that takes one spreadsheet and turns each row into a personalized document, then delivers it.

What the CLI does:

- **Allocate** — assign each row to exam slots / centres (the original use case)
- **Generate** — render a personalized PDF per row
- **Send** — email each recipient their document, dispatch SMS, download photos
- **Log** — a per-row CSV of what generated, what sent, and every error, so a re-run can pick up only the failures

### The two branches tell the story

- **`main`** (you are here) — the original **CLI** tool.
- **[`local`](https://github.com/Chineme-Portfolio/VolleyPacket/tree/local)** — the CLI **plus a simple self-host dashboard** (a FastAPI backend + a Next.js UI) that wrapped the script so a team could run batches without touching the terminal.

From there it became the full hosted product at **[volleypacket.com](https://volleypacket.com)**.

### Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd cli
python main.py /path/to/data.xlsx              # allocate, generate PDFs, and send
python main.py /path/to/data.xlsx --dry-run    # generate PDFs only, don't send
python main.py /path/to/data.xlsx --allocated  # skip the allocator (already allocated)
```

Sending email/SMS needs your provider credentials (set them in a `.env`); use `--dry-run` to try PDF generation without sending anything.

---

## Where it went

The bottleneck — me running commands for every batch — is exactly what turned this script into a product. **VolleyPacket** is now a full web platform:

- Upload a spreadsheet, pick a template, generate thousands of personalized PDFs
- **AI-powered template generation** — describe what you want, get a professional document
- Batch email with your own provider (Resend, SendGrid, Gmail, Outlook, Zoho, or custom SMTP)
- SMS dispatch, photo downloads, real-time progress tracking
- Smart email cleanup that catches the typos humans miss
- Delivery reports, pause/resume on any task, multiple concurrent jobs

The whole platform is **column-driven**: whatever columns are in your spreadsheet become your merge fields. It's not locked to exams — it's offer letters, event invitations, certificates, onboarding packets, anything where you go from spreadsheet to personalized documents at scale.

**→ [volleypacket.com](https://volleypacket.com)**

---

## Tech

Python · pandas · ReportLab (PDF generation) · smtplib (email) — with the [`local`](https://github.com/Chineme-Portfolio/VolleyPacket/tree/local) branch adding FastAPI and Next.js.

---

<sub>This repository is a portfolio snapshot of the project's origins. The commercial platform is closed-source.</sub>
