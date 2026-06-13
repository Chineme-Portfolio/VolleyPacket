# Code Standards

Implementation rules and conventions for both halves of VolleyPacket. The AI agent follows these in every session without exception. They exist to prevent pattern drift across sessions — and, because this project is in a **stabilization phase**, to keep changes small and safe.

---

## Engineering Mindset

The AI agent on this project operates as a senior engineer maintaining a production system with real users:

- **Stabilization first** — this codebase is being hardened, not rebuilt. Prefer the minimal diff that fixes the root cause. Never refactor surrounding code while fixing a bug.
- **Diagnose before changing** — reproduce or fully explain the failure before writing the fix. Check `failure-modes.md` first: most bugs here are repeat offenders of a known class.
- **Respect the invariants** — `architecture.md` ends with the project's invariants. A fix that violates one is not a fix; it's the next bug.
- **Multi-worker brain** — before touching job/task code, ask: "what happens when the other gunicorn worker handles the next request?" and "what happens when Railway redeploys mid-run?"
- **Every change must be verifiable** — state how you verified it (ran it, hit the endpoint, watched the SSE stream, checked the DB). Failing tests or builds are reported, not hidden.
- **Scope is sacred** — fix what was asked. New ideas go to `roadmap.md`, not into the diff.
- **One thing at a time** — one bug or one feature per session/commit.

---

## Design Principles & Patterns

The design lens for the codebase. These are **guides for new and refactored code, not a mandate to restructure working code.** In a stabilization phase the priority order is: correctness → respects the `architecture.md` invariants → minimal diff → SOLID/clean design. A "more SOLID" rewrite that touches code unrelated to the task is out of scope (see *Scope is sacred*).

### SOLID

The best modules already follow SOLID — `app/services/storage.py` and `app/services/email_providers/` are the reference implementations. Make new code look like them.

- **S — Single Responsibility.** One module/class/component, one reason to change. This is already the service layout: `pdf_tasks` renders, `email_tasks` sends, `storage` persists, `billing` gates. Keep routes thin (HTTP only); one React component per file. If a function does two unrelated things, split it.
- **O — Open/Closed.** Extend by adding an implementation, not by editing a growing `if/elif`. A new email provider = a new class + a factory registration; you don't touch `email_tasks`. New storage backend, same story.
- **L — Liskov Substitution.** Every `EmailProvider` / `StorageBackend` subclass must be a drop-in: same signatures, same return shapes, same error contract. A provider that throws where the base returns, or returns a different shape, breaks callers that only know the interface.
- **I — Interface Segregation.** Keep base interfaces small and focused (`EmailProvider` exposes essentially `send`; `StorageBackend` only the storage verbs). Don't add a method to a base class that only one implementation needs.
- **D — Dependency Inversion.** Depend on abstractions, never concretions. Code calls `store` and the provider interface — never `boto3` or the Resend SDK directly (already an architecture invariant: "never import boto3 outside storage.py"). New third-party integrations get a thin service wrapper (like `paystack.py`) that the rest of the app depends on.

The boundary **Invariants** in `architecture.md` are the structural enforcement of S and D — treat them as the non-negotiable floor; SOLID here is the broader spirit.

### Software Design Patterns

Reach for a pattern when it **removes real duplication or coupling** — never to demonstrate the pattern. The wrong pattern adds indirection a maintainer has to unwind, which is the opposite of stabilization.

- **Match what's already here.** When you need new structure, copy the pattern the codebase already uses for that shape (table below) so the code stays uniform.
- **Earn the abstraction.** Two concrete cases justify an interface; one does not. Don't pre-abstract for a hypothetical future provider.
- **Never introduce a pattern mid-bugfix.** Patterns land in dedicated `refactor:` commits with their own verification — never smuggled into a `fix:`.
- **Clean over clever.** Simple, readable code a junior can follow beats an elegant pattern they can't. If a plain function does the job, use the plain function.

**Patterns already in VolleyPacket** — the in-house vocabulary; prefer these and extend them the existing way:

| Pattern | Where | Reach for it when |
| --- | --- | --- |
| Strategy | `email_providers/` (Resend/SendGrid/SMTP), `storage` (Local/S3) | interchangeable implementations behind one interface |
| Factory method | `create_provider()`, `get_storage()` | selecting an implementation at runtime from config/region |
| Adapter | each email provider wrapping a third-party SDK into `EmailProvider` | fitting an external API onto our interface |
| Facade | `paystack.py`, the service layer over libraries | one simple entry point into a messy subsystem |
| Singleton | `get_storage()` lazy singleton, the SQLAlchemy session factory | exactly one shared, lazily-created instance |
| Proxy | `_StorageProxy` (the `store` object) | deferring or wrapping access to the real object |
| Template method | the `run_*` task skeleton (fixed lifecycle, varying body) | a fixed process with one or two pluggable steps |

Adding a provider, a storage backend, or another long-running task means **extending one of these** — do it the existing way, not a new way.

**Full GoF reference** — for when a genuinely new structural problem appears (★ = already used here):

| Pattern | Use it when you want to… |
| --- | --- |
| Abstract factory | create families of related objects while hiding which family from the client |
| Adapter ★ | convert one interface into another |
| Bridge | vary a stable client interface and its implementation independently |
| Builder | build something via different processes and step orders |
| Chain of responsibility | pass a request along handlers when the right handler isn't known in advance |
| Command | execute operations flexibly — queue, schedule, log, undo/redo |
| Composite | treat part-whole tree structures through one uniform interface |
| Decorator | add or remove responsibilities on objects dynamically |
| Facade ★ | present a simple interface over a web of components |
| Factory method ★ | let config/subclass decide which product is created |
| Flyweight | share many fine-grained objects economically |
| Interpreter | evaluate rules/grammar that change frequently |
| Iterator | traverse a collection without exposing its structure |
| Mediator | decouple objects whose interactions are complex |
| Memento | capture and restore an object's private state |
| Observer | decouple handlers from an event source; add/remove them dynamically |
| Prototype | clone existing objects to avoid creation cost |
| Proxy ★ | control access — remote, lazy, guarded, or tracked |
| Singleton ★ | guarantee one (or a few) shared instance(s) |
| State | implement a state machine at low complexity |
| Strategy ★ | swap interchangeable algorithms differing in non-functional aspects |
| Template method ★ | vary individual steps of a fixed process |
| Visitor | decouple type-dependent operations from the classes they act on |

**Rarely a fit here** — Visitor, Interpreter, Composite, Flyweight, Memento, Prototype, Bridge. VolleyPacket is a mostly-functional Python service app with a thin React UI, not a deep class hierarchy. If you find yourself reaching for one of these, stop and confirm it's genuinely warranted before adding it.

---

## Python (backend)

### Style
- Python 3.11. Modern typing: `str | None`, `list[str]`, `dict[str, int]` — not `Optional`/`List` from typing.
- `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` module constants.
- Module docstring at the top of every file explaining its responsibility (existing files all do this).
- Logging, never print: `logger = logging.getLogger(__name__)` per module. Logs go to stdout — Railway captures them.
- f-strings for formatting. No bare `except:` — catch `Exception` at minimum, and log what you swallow.

### DB session pattern
Every DB touch uses this exact shape — sessions are short-lived, per-operation:

```python
from app.database import get_session, JobRow

session = get_session()
try:
    row = session.get(JobRow, job_id)
    # ... mutate ...
    session.commit()
except Exception as e:
    session.rollback()
    logger.error(f"Failed to <do thing> for {job_id}: {e}")
    raise  # or return a safe default for read paths
finally:
    session.close()
```

Never hold a session across a network call, a render, or a sleep. Never share a session between threads.

### Route handlers
- Thin: auth dependency → validate → call service → shape response.
- Protected routes take `user: UserRow = Depends(get_current_user)` and scope every lookup by `user.id`.
- Errors are `raise HTTPException(status_code=…, detail="Human-readable message")`. The `detail` string is shown to users by the frontend — write it for them, not for a stack trace.
- Job lookups: `get_job_for_user(job_id, user.id)` (or `_light` for read-only) → 404 if None. Never `get_job()` alone in a route.
- Pick the right loader: `get_job_light_for_user` for status/metadata reads (fast, **must not save**); full `get_job_for_user` for anything that mutates or needs the DataFrame.

### Background tasks
New or modified task code copies the established pattern exactly (see `pdf_tasks.py`):

```python
def run_my_task(job: Job):
    task = job.tasks["mytask"]
    try:
        task.status = "running"
        task.total = len(data)
        job.save()
        for idx, row in enumerate(data):
            if job.should_stop("mytask"):
                task.status = "cancelled"; task.phase = "cancelled"
                job.save(); return
            # ... do the row ...
            task.progress = idx + 1
            if (idx + 1) % 10 == 0 or (idx + 1) == task.total:
                job.save()
        task.status = "complete"; task.phase = "complete"
        job.save()
    except Exception as e:
        logger.exception(f"mytask failed for job {job.job_id}")
        task.status = "failed"; task.error = str(e)
        job.save()

def start_my_task(job: Job):
    job._clear_stop_flag("mytask")  # clear stale flags before starting
    thread = threading.Thread(target=run_my_task, args=(job,), daemon=True)
    thread.start()
```

Non-negotiables: full-body try/except that persists `failed`; `should_stop()` every iteration; save every 10 rows; clear stale pause/stop flags before start; status changes only through TaskStatus fields + `save()`.

### Files
- All reads: `store.ensure_local(key)`. All writes: write locally → `store.save_local_file(path)`. Build keys from `config.*_FOLDER` paths + `_key_from_local()`.
- Filenames derived from user data go through `safe_filename()`.

---

## TypeScript / Next.js (frontend)

- App Router, React 19. Most interactive pages/components are client components (`"use client"`); the layout wires `AuthProvider → ToastProvider → AppShell`.
- **All API calls via `src/lib/api.ts`.** New endpoint = new typed function there, plus interface updates. Components never hand-roll `fetch` to the backend, never build API URLs.
- Errors: `try { … } catch (err) { /* err.message is already user-friendly via parseApiError */ }` — surface with the Toast system, never `alert()`, never raw JSON.
- Status display uses `statusBadge(status)` from `lib/status.ts` — never inline status→color mappings.
- localStorage keys are prefixed `vp_` (`vp_token`, `vp_template_chat`, `vp_email_chat_*`). The 401 auto-logout in api.ts clears them — register any new key there.
- Components: PascalCase file = default-exported component, one component per file, props typed inline or as `interface Props`.
- Loading/disabled states on every async button (`disabled:opacity-50` + spinner pattern — see ui-registry.md).
- TypeScript strict; no `any` — type API responses via the interfaces in api.ts.

---

## API Contract (both sides)

- Success: route returns the resource or `{ "message": "..." }` (+ extra fields like `total`).
- Failure: HTTP status + `{ "detail": "human readable" }` — FastAPI default shape. Frontend `parseApiError` reads `detail`.
- Long-running work: POST start endpoint returns immediately (`{message, total}`); progress flows through `/jobs/{id}/stream` (SSE) and `/jobs/{id}/{task}/status` polls.
- Auth: `Authorization: Bearer <jwt>` on everything except `/auth/*`, `/`, webhooks.

---

## Naming

| Thing | Convention | Example |
| --- | --- | --- |
| Python modules | snake_case | `pdf_tasks.py`, `email_settings.py` |
| Task modules | `<noun>_tasks.py` with `start_*` / `run_*` | `start_pdf_generation`, `run_pdf_generation` |
| Routes | plural domain nouns | `/jobs`, `/templates`, `/email-settings` |
| React components | PascalCase.tsx | `TaskPanel.tsx`, `ColumnMapper.tsx` |
| lib files | camelCase.ts | `api.ts`, `status.ts` |
| DB rows | `<Noun>Row` | `JobRow`, `TemplateRow` |
| Storage keys | relative POSIX paths | `output/pdfs_{job_id}.zip` |
| localStorage | `vp_` prefix | `vp_token` |

---

## Error Handling Rules

- No empty catch blocks, ever. Log with context: `logger.error(f"Failed to X for {job_id}: {e}")`.
- Use `logger.exception(...)` inside `except` when the traceback matters (task bodies).
- User-facing messages (HTTPException detail, Toasts) are plain English with a next step where possible ("Could not extract text from this PDF. Please try a different file.").
- Background task errors land in `TaskStatus.error` and per-row errors in the CSV logs — users see them in the JobLogViewer, so keep them readable.
- Best-effort cleanup paths (S3 deletes, log deletes) may catch-and-warn; primary write paths must not swallow errors silently.

---

## Comments

- Comments explain **why**, not what. The existing code comments document concurrency reasoning (e.g. the `tasks_json` merge rationale) — that's the bar.
- When a fix closes a failure mode, the lasting explanation goes in `failure-modes.md`, with at most a short why-comment at the code site.
- No TODO comments in committed code — open items go to `roadmap.md` or `progress-tracker.md`.

---

## Git

- Conventional commits, matching existing history: `feat:`, `fix:`, `perf:`, `refactor:`, `chore:`, `debug:`.
- Subject describes the behavior change, not the file change: `fix: merge tasks_json in save() to prevent cross-worker state regression`.
- One logical change per commit. Working branch is currently `v2.0`; `main` is the default branch for PRs.

---

## Dependencies

Never add a package without checking: does the stdlib, pandas, or an existing dependency already do this?

Approved backend (requirements.txt): fastapi, uvicorn/gunicorn, sqlalchemy, psycopg2-binary, pandas, numpy, openpyxl, weasyprint, pillow, anthropic, stripe, boto3, bcrypt, PyJWT, cryptography, email-validator, resend, requests, beautifulsoup4, PyPDF2, python-docx, python-multipart, python-dotenv, tqdm.

Approved frontend (package.json): next 16, react 19, framer-motion, tailwindcss v4 (+ @tailwindcss/postcss), typescript, eslint, @uiw/react-codemirror + @codemirror/lang-html (syntax-highlighted HTML editor for the in-job template editor's HTML tab — lazy-loaded via `next/dynamic`, kept off the initial bundle).

Adding anything else = update this list in the same commit and state why.

---

## Verification Checklist (before calling anything done)

Backend change:
1. App boots: `uvicorn app.main:app --reload` with a valid `.env` (SECRET_KEY required).
2. Exercise the endpoint(s) (curl/HTTPie or the UI).
3. For task code: start a real task on a small file, watch progress, then **test pause → resume → cancel**.
4. For state code: confirm what's in the DB (`/debug/db` or a direct query) matches what the UI shows.

Frontend change:
1. `npm run lint` and `npm run build` pass in `frontend/`.
2. Exercise the changed page against a running backend.

Both: update `progress-tracker.md` (what changed, decisions, gotchas) — and `failure-modes.md` if a new failure class was discovered or closed.
