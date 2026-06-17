# VolleyPacket — CLI + self-host dashboard (v1)

This branch is the second chapter of the story told on [`main`](https://github.com/Chineme-Portfolio/VolleyPacket/tree/main): the original command-line tool **plus a simple web dashboard** that wrapped it — so a team could run batches without living in the terminal.

> 🚀 The polished, multi-tenant product this became is live at **[volleypacket.com](https://volleypacket.com)** (closed-source).

## What's here

- **`cli/`** — the original command-line tool (see [`main`](https://github.com/Chineme-Portfolio/VolleyPacket/tree/main) for the full story of how it began)
- **`app/`** — a FastAPI backend that runs the generate → send pipeline as background jobs
- **`frontend/`** — a Next.js dashboard: upload a spreadsheet, pick a template, watch progress, download results

Same idea as the CLI — spreadsheet in, personalized PDFs + emails + SMS out — with a UI on top and jobs you can start, watch, and re-run from the browser.

## Run it

**Backend** (from the repo root):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

## Tech

Python · pandas · ReportLab · FastAPI · Next.js

---

<sub>Portfolio snapshot of the self-host stage. The commercial platform at [volleypacket.com](https://volleypacket.com) is closed-source.</sub>
