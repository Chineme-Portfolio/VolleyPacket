# UI Registry

Living document. The catalog of every component in `frontend/src/components/` — what it does, what it receives, and the patterns it establishes. **Before building any new UI: check here for an existing component or pattern and match it exactly.** After building or meaningfully changing a component, update its entry.

Shared visual patterns (cards, buttons, badges, modals, spinners) are defined once in `ui-guidelines.md` — entries below only note deviations or component-specific patterns.

---

## How to Use

1. Need UI? Find the closest component here and reuse/extend it.
2. Nothing close? Build it following `ui-guidelines.md`, then **add an entry here**.
3. Changed a component's API or pattern? Update its entry in the same commit.

---

## Layout & Chrome

### AppShell — `components/AppShell.tsx` (41 lines)
Layout switchboard wrapped around every page by the root layout. Renders Sidebar + Topbar chrome for app pages, bare children for public routes (landing, login, signup, blog). Decides based on route/auth state.

### Sidebar — `components/Sidebar.tsx` (179 lines)
App navigation: Dashboard, Jobs, Templates, Settings, Guides. Dark-green brand treatment; active item highlighted. Includes logo block and sign-out affordance.

### Topbar — `components/Topbar.tsx` (74 lines)
Header bar for app pages: page context + user menu. White bar over the gray app background.

### Logo — `components/Logo.tsx` (73 lines)
Brand logo with optional animation variants (`logo-spin-z`, `logo-float` keyframes from globals.css). Used in Sidebar, landing hero, auth pages.

---

## Dashboard

### StatCard — `components/StatCard.tsx` (35 lines)
Single metric card: label, value, optional icon. Standard white card (`bg-white rounded-2xl border border-gray-100 shadow-sm`). Used in a responsive grid on /dashboard.

### RecentJobs — `components/RecentJobs.tsx` (64 lines)
Compact list of the latest jobs with status badges (`statusBadge()`) linking to `/jobs/[id]`. Dashboard widget.

---

## Jobs flow

### NewJobModal — `components/NewJobModal.tsx` (203 lines)
Job creation flow in a modal (standard overlay pattern): candidate file upload (Excel/CSV) → calls `createJob()` → routes to the new job. Handles upload validation errors (tier limits surface here as friendly messages from `detail`).

### JobModeSelector — `components/JobModeSelector.tsx` (107 lines)
Choose `dynamic_pdf` / `static_attachment` / `email_only`. Static mode includes the static-attachment file input. Calls `setJobMode()`.

### TaskPanel — `components/TaskPanel.tsx` (354 lines) ★
The most important component. Self-contained panel for ONE task (pdfs / emails / sms / photos) on the job detail page: status badge, progress bar, per-task counters (sent/failed/skipped…), error display, and the Start / Pause / Resume / Cancel buttons wired to `startX()` / `pauseTask()` / `resumeTask()` / `cancelTask()`. Receives live `TaskStatus` from the job-detail page's SSE subscription — it does not poll itself (extracted as self-contained in commit `c53ec31` after polling-lifecycle bugs; keep it presentation-driven).

### ColumnMapper — `components/ColumnMapper.tsx` (152 lines)
Maps template `{Placeholders}` to spreadsheet columns. Shows auto-matched pairs, lets the user fix unmatched ones, confirms via `applyColumnMapping()`. Disappears once `column_mapping_confirmed` (bug fixed in `e6e149a` — it must not reappear after confirm).

### JobLogViewer — `components/JobLogViewer.tsx` (234 lines)
Tabular viewer for per-run CSV logs (email/sms/photo): fetches `getJobLogs()` / `getJobLog()` with pagination, renders headers + rows, per-log download via `downloadJobLog()`.

### EmailComposer — `components/EmailComposer.tsx` (364 lines)
Subject + HTML body editor with `{Placeholder}` chips (mono blue chips per ui-guidelines) and an **AI draft assistant** (calls `generateEmailAI()` with the job's columns; chat state persisted in `localStorage.vp_email_chat_{jobId}`). Saves via `setEmailContent()`.

### SmsComposer — `components/SmsComposer.tsx` (140 lines)
SMS body editor with placeholder chips + character awareness. Saves via `setSmsContent()`.

---

## Templates

### TemplateSelector — `components/TemplateSelector.tsx` (110 lines)
Browse/pick a template to attach to a job (calls `attachTemplate()`). Tier-gated templates surface the backend's access error.

### TemplateCard — `components/TemplateCard.tsx` (244 lines)
Single template card on /templates: name, description, owner, visibility/tier marker, preview + download + delete + publish/unpublish actions (`downloadTemplatePdf()`, `updateTemplateVisibility()`, `deleteTemplate()`).

### PdfPreviewModal — `components/PdfPreviewModal.tsx` (43 lines)
Modal iframe preview of generated template HTML/PDF (data-URL from `previewGeneratedTemplate()`).

---

## Auth & feedback

### GoogleSignIn — `components/GoogleSignIn.tsx` (152 lines)
Google Identity Services button → id_token → `POST /auth/google-login` via auth context. Renders nothing if `GOOGLE_CLIENT_ID` isn't configured.

### Toast — `components/Toast.tsx` (125 lines)
`ToastProvider` + `useToast()` hook — THE feedback mechanism. Success/error variants, auto-dismiss. Mounted in the root layout above AppShell.

---

## Pages with notable inline UI (no extracted component)

- `app/jobs/[id]/page.tsx` — job detail orchestrator: owns the SSE `EventSource` subscription to `/jobs/{id}/stream`, distributes `TaskStatus` to the four TaskPanels, hosts JobModeSelector / TemplateSelector / ColumnMapper / composers / downloads.
- `app/settings/billing/page.tsx` — tier cards from `getTiers(region)`, checkout/portal/cancel/resume flows.
- `app/settings/email/page.tsx` — provider presets (Resend, SendGrid, Gmail, Outlook, Zoho, custom SMTP) + credential form.
- `app/page.tsx` — landing page (hero with demo.mp4, animated logo, feature sections, SEO JSON-LD in layout).

---

## Maintenance protocol

When you touch a component:
1. Keep its entry's purpose/props/pattern notes current.
2. If you established a new reusable pattern (a new badge variant, a new modal layout), promote it to `ui-guidelines.md`.
3. If you extracted inline page UI into a component, move/add its entry here.
