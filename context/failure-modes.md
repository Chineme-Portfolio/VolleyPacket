# Failure Modes

The diagnostic backbone of this project. VolleyPacket's hard bugs are not random — they cluster into a small number of recurring classes, all documented here with their symptoms, root causes, the invariant that prevents them, and where the defense lives in code.

**How to use this file:** when something breaks, scan the symptom column first. Most "new" bugs in this codebase are a known class wearing a new outfit. When you fix a genuinely new class of failure, add it here — this file is a living document and the most valuable one in `context/`.

---

## Quick Symptom Index

| Symptom | Likely class |
| --- | --- |
| Progress jumps backwards / "complete" reverts to a % | [1] Cross-worker state regression |
| Task stuck "running" forever, nothing happening | [2] Silent thread death / [3] Stale running after redeploy |
| Cancel or pause button "doesn't work" | [4] Control signal lost |
| Downloads empty / 404 / "data file lost" after a deploy | [5] Ephemeral filesystem |
| Job list slow, or candidate_count suddenly 0 | [6] Lightweight-job misuse |
| UI progress frozen but task is actually advancing | [7] Stale SSE / unpersisted progress |
| Garbled phone numbers, dates, or exam numbers in PDFs/SMS | [8] Type coercion on ingest |
| Emails "sent" to obviously broken addresses, or valid ones rejected | [9] Email cleaning edge cases |
| Checkout/webhook 500s, tier not updating after payment | [10] Stripe integration drift |
| PDF generation crashes instantly in prod but works locally | [11] Missing WeasyPrint system libs |
| Task won't start, or starts already-paused | [12] Stale control flags at start |
| AI rejects an uploaded image | [13] Media-type mismatch |
| Feature empty/wrong when opened later but fine during the run | [14] Runtime-only attribute lost after DB load |
| Downloaded log/report is garbled binary ("gibberish"), esp. after redeploy | [15] Corrupt download via presigned redirect |
| Edited a template but regenerated PDFs don't change (old barcode/QR/content) | [16] Stale rendered PDFs after template edit |

---

## [1] Cross-worker task-state regression

- **Symptoms:** task progress visibly jumps backwards; a completed task reverts to "running 28%"; status flaps between values on refresh.
- **Root cause:** production runs **2 gunicorn workers**. The background thread lives in worker A and saves progress; an unrelated request (e.g. saving email content) on worker B loads a stale Job snapshot and its `save()` overwrites worker A's newer `tasks_json`.
- **Defense:** `Job.save()` **merges** `tasks_json` instead of blind-writing (`app/services/jobs.py` — terminal states win; higher progress wins; fresh restart at progress 0 with total>0 may override). Commit `ade869b`.
- **Invariant:** never write `tasks_json` around the merge logic; never reintroduce blind overwrites.
- **Verify:** run a PDF task; mid-run, save email content repeatedly from the UI; progress must never regress.

## [2] Silent thread death

- **Symptoms:** task shows "running" forever; counters frozen; no errors anywhere; restarting the task works.
- **Root cause:** an unhandled exception inside a daemon-thread task body kills the thread. Nothing catches it, so the DB status stays "running".
- **Defense:** every `run_*` body is wrapped in try/except that sets `status="failed"`, `error=str(e)`, and calls `job.save()` (commit `346e6b6`). `logger.exception` records the traceback.
- **Invariant:** no task code path can exit the thread without persisting a terminal status.
- **Verify:** raise inside a task body in dev → status must become "failed" with the message visible in the UI.

## [3] Stale "running" after restart/redeploy

- **Symptoms:** after a deploy, old tasks show "running" but nothing is happening (their threads died with the old process).
- **Root cause:** Railway redeploys kill processes; threads don't survive; the DB still says running.
- **Defense:** `mark_stale_running_tasks()` runs **once at startup** (from `init_db()`) and marks DB-running tasks as `interrupted`.
- **Critical anti-pattern (already happened):** doing this check on every job load. In multi-worker, worker B loading a job would mark a task *legitimately running on worker A* as interrupted, corrupting live state. Startup-only, never per-load.
- **Verify:** start a task, kill the server, restart → task shows "interrupted", restartable.

## [4] Cancel/pause signals lost across workers

- **Symptoms:** user clicks cancel/pause; UI confirms; the task keeps going. Or: cancel "sticks" only after a long delay.
- **Root cause (two halves):**
  1. The cancel request lands on worker B, but the thread runs in worker A — memory flags don't cross processes.
  2. If the signal were written via `save()`'s full-row write, the thread's own periodic `save()` could overwrite it a second later.
- **Defense:** control flags live in **dedicated columns** (`stop_flags_json`, `paused_json`) written directly by `cancel_task()` / `pause_task()` / `resume_task()` — never through the merge path. The running thread re-reads flags from the DB every **3s** inside `should_stop()`; `save()` also honors externally-set stop flags before writing. Commits `0f583d2`, `f5fbf1a`.
- **Invariant:** control signals always bypass `save()`; every loop iteration calls `should_stop(task)`.
- **Verify:** with 2 local workers (`gunicorn -w 2`), start a task and cancel from the UI — it must stop within ~3s regardless of which worker took the request.

## [5] Ephemeral filesystem — files lost on redeploy

- **Symptoms:** PDF/photo downloads return empty zips or 404 after a deploy; "data file lost" errors; report generation fails for old jobs.
- **Root cause:** Railway containers get a fresh disk on every deploy. Anything written only locally is gone.
- **Defense:** dual-write through the storage layer — write locally, sync with `store.save_local_file()`; read with `store.ensure_local()` which re-downloads from S3 on miss. PDFs are zipped and the **zip** uploaded; `_restore_pdfs_from_storage()` restores zip-first, individual-files fallback. Job data (`data.xlsx` etc.) is synced on every `save(include_data=True)`. Commits `e8f0686`, `6aacd92`, `3a3a71e`.
- **Invariant:** any file a user may need later must be in storage at creation time; never `open()` a path you haven't `ensure_local()`-ed.
- **Watch out:** storage auto-detect — if `BUCKET` isn't set in prod, the backend silently runs local (a loud warning is logged). Check the boot log line `Storage backend: …` first when files vanish.

## [6] Lightweight-job misuse

- **Symptoms:** `candidate_count` becomes 0; job data appears wiped after a harmless-looking endpoint ran; list endpoints suddenly slow (3s+ each).
- **Root cause:** full job loads download + parse the Excel from storage (~3s). `get_job_light*()` skips that for read-only paths — but a light job has an **empty DataFrame**, so calling `save()` on it writes `candidate_count=0` and can cascade.
- **Defense/Invariant:** light loads for read-only endpoints only; any endpoint that mutates loads the full job. The docstring on `_load_job_light_from_db` says exactly this. Commit `c71b7cf`.
- **Verify:** after touching any endpoint, check whether it can reach a `save()`; if yes, it must use the full loader.

## [7] Stale or frozen live progress (SSE)

- **Symptoms:** UI progress frozen while work continues; progress visible only after refresh; SSE shows different numbers than the DB.
- **Root cause (multiple historical):** SSE reading from process memory (wrong worker); thread advancing without persisting (e.g. the fast "skip existing PDFs" loop saved nothing — commit `2c494bb`); frontend polling lifecycle bugs (fixed by extracting TaskPanel, decoupling polling — commits `c53ec31`, `51df5eb`).
- **Defense:** SSE handler (`app/routes/jobs.py:162`) loads fresh light jobs from the DB each tick (fast cadence while running, slow when idle); tasks save at least every 10 rows *including* skip loops.
- **Invariant:** progress that isn't saved doesn't exist; SSE never reads memory.

## [8] Type coercion destroying data on ingest

- **Symptoms:** phone numbers like `08065140173` arrive as `8065140173.0`; leading zeros gone; dates render as `2026-05-19 00:00:00`; exam numbers as floats in PDFs/SMS.
- **Root cause:** pandas/openpyxl type inference.
- **Defense:** read every cell **as a string** at ingest (`read_data.py`), `.fillna("")` everywhere. Commit `88f0883`.
- **Invariant:** no code path reads the spreadsheet with type inference on. When adding a new reader/round-trip, preserve strings.

## [9] Email cleaning edge cases

- **Symptoms:** sends fail for addresses that "look fine"; or a heuristically-repaired address goes to the wrong place; users ask why a recipient was excluded.
- **Root cause:** real-world data is filthy. `clean_email()` (`app/services/jobs.py`) repairs known patterns: `#`/`Q` as `@`, missing `@` before known domains, spaces, duplicate domains, `gmailcom` → `gmail.com`, missing TLDs.
- **Defense:** clean → validate against `EMAIL_RE` → invalid rows split into `invalid_data` with a Reason and exported to `invalid_emails_*.xlsx`; they are excluded from sends, never guessed at send time.
- **Invariant:** repairs happen only in `clean_email()` (one place to audit); invalid rows are always reported, never silently dropped. When a new garbage pattern appears, extend `clean_email()` + note it here.
- **Watch out:** the heuristics CAN over-repair (e.g. inserting `@` into a string that wasn't an email). If a user reports a mis-send, diff raw vs cleaned values from the job's `data.xlsx` vs `valid_data.xlsx`.

## [10] Stripe integration drift

- **Symptoms:** webhook 500s; checkout succeeds but tier never upgrades; "No such customer" errors.
- **Root causes & fixes (commits `9208dde`, `345ca24`, `7532883`):**
  - SDK-object attribute access on webhook payloads broke — **parse the verified payload as plain JSON dicts** with `.get()` everywhere.
  - Stored `stripe_customer_id` can be stale (test-mode wipe, key/env switch) — **validate before use, recreate if invalid**, update the row.
  - Webhook handler hardened with diagnostic logging — keep it; webhook failures are otherwise invisible.
- **Invariant:** tier changes only from verified server-side events; webhook signature always verified; every Stripe object lookup tolerates absence.
- **Verify:** `stripe listen --forward-to localhost:8000/billing/webhook` + a test checkout; confirm `users.tier` and `subscriptions` update.

## [11] Missing WeasyPrint system libraries

- **Symptoms:** PDF task fails instantly in prod (`OSError: cannot load library 'libpango-1.0-0'`); works on your Mac.
- **Root cause:** WeasyPrint needs OS packages that pip doesn't install.
- **Defense:** apt packages pinned in **both** `Dockerfile` and `nixpacks.toml`. If the deploy method changes, port the package list.
- **Verify:** build the Docker image locally and render one PDF inside it.

## [12] Stale control flags at task start

- **Symptoms:** newly-started task immediately shows paused, or refuses to run after a previous cancel.
- **Root cause:** pause/stop flags persisted in the DB outlive the run that set them.
- **Defense:** clear stale pause/stop flags before starting any task (`_clear_stop_flag`, pause-flag clearing — commit `b003d61`); `reset_tasks()` resets all flags for full reruns.
- **Invariant:** every `start_*` clears its task's stale flags first.

## [13] Image media-type mismatch (AI uploads)

- **Symptoms:** Claude rejects an uploaded image; template generation fails only for certain files.
- **Root cause:** files lie — a `.png` that's really a JPEG. Claude validates the declared media type against the actual bytes.
- **Defense:** detect media type from **magic bytes**, verify base64 content matches before sending (commits `4ea9dbc`, `4262218`).
- **Invariant:** never trust file extensions for media types.

## [14] Runtime-only attribute lost after DB load

- **Symptoms:** a feature that reads `job.<attr>` works during the live run but produces empty/wrong output when triggered later (e.g. the delivery report dumped every successful send into "Not Sent").
- **Root cause:** the report read the email log only via `job.log_path`, but `log_path` is a runtime-only attribute set to `None` in `from_db_row` — and every report download loads a fresh Job from the DB. So the log was never read; `sent_emails` stayed empty; all candidates fell into "Not Sent".
- **Defense:** `generate_report` reconstructs log keys from the persisted `job.timestamp` (`logs/{prefix}_{timestamp}.csv`) and reads each task's log directly — never `job.log_path`. The report is now log-driven (the logs are the record of what happened), so it can't re-derive status incorrectly.
- **Invariant:** anything needed after a job is reloaded must come from a persisted column (or be reconstructable from one, like `timestamp`) — never a runtime-only attribute that `from_db_row` resets.
- **Verify:** generate a report with `job.log_path = None` and only the per-task CSVs present → successful sends count as success.

## [15] Corrupt ("gibberish") downloads via presigned redirect

- **Symptoms:** a downloaded log/report is sometimes garbled binary; sharing it shares the garbage. Intermittent — typically after a redeploy or from the other worker.
- **Root cause:** `store.serve()` returns a **redirect to an S3 presigned URL** when the file isn't on the current pod's local disk. The browser download (an authenticated `fetch` that follows the redirect) can save an error/garbled body instead of the file. "Sometimes" = only when not served from local disk.
- **Defense:** for small text/report files, **stream through the API** — `store.ensure_local(key)` then `FileResponse(...)` with `text/csv; charset=utf-8` — never a redirect (`download_job_log`, `get_report` in `app/routes/jobs.py`). Large ZIPs (PDF/photo bundles) keep the presigned path deliberately.
- **Invariant:** logs and reports are streamed with an explicit content-type + charset, never served via redirect.
- **Verify:** download a log when the file isn't local (force `ensure_local` to fetch from storage) → bytes match the original CSV exactly.

---

## [16] Stale rendered PDFs after a template edit

- **Symptoms:** you edit a job's template (HTML / Ask Volley / rich text / switch template), regenerate, and the PDFs are unchanged — a barcode/QR or any edit doesn't update; scanning shows the old value. Looks like the edit "didn't save."
- **Root cause:** PDF generation **skips any row whose PDF already exists** (`pdf_tasks.run_pdf_generation`), and `get_pdf_folder()` **restores the old PDFs from S3 first** — so a re-run renders nothing and serves last time's files. The skip is deliberate (resume partial runs / survive redeploy) but it also masks template changes.
- **Defense:** a template change must **invalidate** the rendered output — `Job.clear_generated_pdfs()` deletes the PDF folder + ZIP (local + S3) and resets the `pdfs` task to idle via a direct `tasks_json` write (bypassing save()'s terminal-wins merge, like `cancel_task`). Called from every template-mutating route — attach / save / ai-edit / reset (`app/routes/jobs.py`).
- **Invariant:** editing a job's template clears its previously generated PDFs so the next run rebuilds from the new template.
- **Verify:** generate PDFs → edit the template → regenerate → the new output reflects the edit (don't open/scan files from before the edit).

---

## Debugging Checklist

When something is wrong and the class isn't obvious:

1. **Where did it run?** Two workers — grab the request logs (RequestLoggingMiddleware prints every request to stdout → Railway logs). A "weird" sequence is often two workers interleaving.
2. **What does the DB actually say?** `GET /debug/db` for table sanity; then inspect the job row directly — `tasks_json`, `stop_flags_json`, `paused_json`, `status`. Compare against what the UI claims before touching code.
3. **Which storage backend is live?** Boot log: `Storage backend: S3 (...)` or `local filesystem`. Wrong backend explains nearly every missing-file report.
4. **Is the file actually in storage?** `store.exists(key)` semantics: local check first, then S3 head. Keys are relative paths from BASE_DIR.
5. **Did the thread die?** Status "running" + frozen counters + no log lines = class [2]/[3]. Check stdout for the `logger.exception` traceback.
6. **Reproduce multi-worker locally:** `gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2` — single-worker `uvicorn --reload` hides classes [1] and [4] entirely.
7. **Check the job's own logs:** per-run CSVs (email/sms/photo) via `/jobs/{id}/logs` or the JobLogViewer — per-row errors live there, not in app logs.
8. **Data bugs:** download the job's `data.xlsx` / `valid_data.xlsx` / `invalid_data.xlsx` from storage and diff — most "wrong content" reports are ingest or cleaning, not rendering.

## Local Reproduction Setup

```bash
# Backend (from repo root)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill SECRET_KEY (+ ENCRYPTION_KEY, ANTHROPIC_API_KEY as needed)
uvicorn app.main:app --reload --port 8000          # single worker — basic dev
# OR, to reproduce concurrency classes [1]/[4]:
gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2

# Frontend
cd frontend && npm install && npm run dev           # http://localhost:3000
```

SQLite DB lands at `data/volleypacket.db`; storage defaults to local folders (`uploads/`, `output/`, `logs/`, `data/jobs/`). A small test spreadsheet with deliberately messy emails/phones is the best fixture — keep one in `test/`.
