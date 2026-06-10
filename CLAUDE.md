# VolleyPacket — Agent Instructions

VolleyPacket is a FastAPI (`app/`) + Next.js (`frontend/`) platform for bulk personalized-document generation and distribution. It is **half-built and in a stabilization phase** — prefer minimal, root-cause fixes over rewrites.

## Context system (read before working)

All project knowledge lives in `context/`. Reading order by task type:

**Always (any task):**
1. `context/project-overview.md` — what this is, current state, scope
2. `context/progress-tracker.md` — where we are, active issues, settled decisions

**Fixing a bug:** 3. `context/failure-modes.md` ★ — check the symptom index FIRST; most bugs here are a known class → 4. `context/architecture.md` (especially the Async Task Execution Model if job/task related)

**Building/changing backend code:** `context/architecture.md` (boundaries + invariants) → `context/code-standards.md` → relevant section of `context/library-docs.md`

**Building/changing UI:** `context/ui-registry.md` (match an existing component first) → `context/ui-guidelines.md` → `context/code-standards.md` (frontend section)

**Planning work:** `context/roadmap.md`

## Hard rules

- Never violate the **Invariants** at the end of `context/architecture.md` — each one exists because of a real production bug.
- This app runs **2 gunicorn workers** on an **ephemeral filesystem** (Railway). Before touching job/task/storage code, ask: "other worker?" and "after a redeploy?"
- Spreadsheet cells are read as strings. The DB is the source of truth for task state. All file access goes through the storage layer. All frontend API calls go through `frontend/src/lib/api.ts`.
- Verify changes per the checklist in `context/code-standards.md`, then update `context/progress-tracker.md` (and `context/failure-modes.md` when a failure class opens/closes).

## Quick commands

```bash
# Backend (repo root, .venv active, .env filled — SECRET_KEY required)
uvicorn app.main:app --reload --port 8000
# Reproduce multi-worker concurrency bugs:
gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2

# Frontend
cd frontend && npm run dev      # lint: npm run lint · build: npm run build
```
