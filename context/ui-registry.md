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

### Topbar — `components/Topbar.tsx`
Header bar for app pages. The user block (shared `Avatar` + display name) is a `<Link>` to `/profile`; "Sign out" sits beneath it. White bar over the gray app background. (The dead placeholder search box was removed.)

### Logo — `components/Logo.tsx` (73 lines)
Brand logo with optional animation variants (`logo-spin-z`, `logo-float` keyframes from globals.css). Used in Sidebar, landing hero, auth pages.

### Avatar — `components/Avatar.tsx`
Shared user-avatar primitive. Renders, in priority: a **preset** (`preset:<id>` → bundled SVG at `/avatars/<id>.svg`), an **uploaded** image (`upload:<ver>` → public `GET /auth/avatar/{userId}?v=<ver>`), or **initials** (from `name`, else "VP"). Props `{avatar, name, userId, size, className}`. Preset ids/labels live in `lib/avatars.ts` (animals + alien from Twemoji SVGs in `public/avatars/`; 3 original silhouettes). Used by Topbar, dashboard, profile, TemplateCard.

---

## Dashboard

### StatCard — `components/StatCard.tsx` (35 lines)
Single metric card: label, value, optional icon. Standard white card (`bg-white rounded-2xl border border-gray-100 shadow-sm`). Used in a responsive grid on /dashboard.

### RecentJobs — `components/RecentJobs.tsx` (64 lines)
Compact list of the latest jobs with status badges (`statusBadge()`) linking to `/jobs/[id]`. Dashboard widget.

---

## Jobs flow

### NewJobModal — `components/NewJobModal.tsx`
Job creation flow in a modal (standard overlay pattern): candidate file upload (Excel/CSV) + template select → `createJob()` → `attachTemplate()` → routes to the new job. Optional `initialTemplateId` prop preselects the template (used by a card's "Use Template"). Handles upload validation errors (tier limits surface here as friendly messages from `detail`).

### JobModeSelector — `components/JobModeSelector.tsx` (107 lines)
Choose `dynamic_pdf` / `static_attachment` / `email_only`. Static mode includes the static-attachment file input. Calls `setJobMode()`.

### TaskPanel — `components/TaskPanel.tsx` (354 lines) ★
The most important component. Self-contained panel for ONE task (pdfs / emails / sms / photos) on the job detail page: status badge, progress bar, per-task counters (sent/failed/skipped…), error display, and the Start / Pause / Resume / Cancel buttons wired to `startX()` / `pauseTask()` / `resumeTask()` / `cancelTask()`. Receives live `TaskStatus` from the job-detail page's SSE subscription — it does not poll itself (extracted as self-contained in commit `c53ec31` after polling-lifecycle bugs; keep it presentation-driven).

### ColumnMapper — `components/ColumnMapper.tsx` (152 lines)
Maps template `{Placeholders}` to spreadsheet columns. Shows auto-matched pairs, lets the user fix unmatched ones, confirms via `applyColumnMapping()`. Disappears once `column_mapping_confirmed` (bug fixed in `e6e149a` — it must not reappear after confirm).

### JobLogViewer — `components/JobLogViewer.tsx` (234 lines)
Tabular viewer for per-run CSV logs (email/sms/photo): fetches `getJobLogs()` / `getJobLog()` with pagination, renders headers + rows, per-log download via `downloadJobLog()`.

### EmailComposer — `components/EmailComposer.tsx`
Accordion with a subject input + **Ask Volley / Rich text / HTML** tabs over `email_body`. Ask Volley (`aiDraftEmail`) applies subject+body immediately and persists; Rich text (`RichTextEditor`) + HTML (lazy `HtmlCodeEditor`) share the same body and save via `setEmailContent`. Server-persisted chat via `getJobAiChats`/`setJobAiChat`. Amber column chips. Warns when the subject/body contain `{placeholders}` that don't match a column.

### SmsComposer — `components/SmsComposer.tsx`
Accordion with **Edit / Ask Volley** tabs. Plain text only — SMS can't render HTML/rich text. Edit = textarea + amber chips + char/segment count → `setSmsContent`; Ask Volley (`aiDraftSms`) applies the body immediately + persists. Server-persisted chat. Live first-recipient preview (via `getJobSampleRow`, mirroring `render_sms`) + unmatched-placeholder warning.

### AskVolleyChat — `components/AskVolleyChat.tsx`
The shared **Ask Volley** chat panel for the template/email/SMS composers — presentational + controlled (the parent owns messages/input/persistence + what each turn does). User bubbles green-800, assistant white, a `system` role renders the spinner line; amber notice bar with a Clear button. The input is an **auto-growing `<textarea>`** (word-wraps, grows ~6 lines then scrolls, **Enter sends / Shift+Enter newline**) via the `useAutoResize` hook (`lib/useAutoResize.ts`, also used by the Templates-tab builder input). Exports `ChatMsg` + `msgId`.

### RichTextEditor — `components/RichTextEditor.tsx`
Lightweight fragment WYSIWYG: a `contenteditable` div + `execCommand` toolbar (bold/italic/underline/lists/align/link/clear) for HTML *fragments* like the email body. `value`/`onChange` (HTML string); pushes an external `value` into the DOM only when unfocused so typing isn't interrupted. (Full HTML *documents* use the iframe approach in JobTemplateEditor instead.)

### JobTemplateEditor — `components/JobTemplateEditor.tsx`
Accordion (SmsComposer collapsible-header pattern) for editing a job's **forked** template, shown on the job page for `dynamic_pdf` jobs. Three tabs (EmailComposer tab pattern): **Ask Volley** (shared `AskVolleyChat` → `aiEditJobTemplate()`, server-persisted via `getJobAiChats`/`ai_chats_json`), **HTML** (CodeMirror via lazy-loaded `HtmlCodeEditor` → `saveJobTemplate()`; base64 images hidden as `{EMBEDDED_IMAGE_N}` via `lib/templateImages.ts`, re-injected on save), **Rich text** (iframe `sandbox="allow-same-origin"` + `contenteditable` body + `execCommand` toolbar; edits visible text while preserving `<style>`/`@page`/images). Side **preview** iframe via `getJobTemplatePreviewUrl()` (Blob URL — revoke on replace). **Reset to original** re-forks via `resetJobTemplate()`. Lazy-loads on first expand; locked (`disabled`) while a task runs; `onChanged` → parent `loadJob()`. Otherwise reuses the house card / primary+subtle buttons / tabs / spinner / input-focus-ring patterns from `ui-guidelines.md`.
- **Document/preview "mat":** an iframe'd page floats on a tinted backdrop so it reads like paper in a viewer. On-screen `@page` margins are emulated (browsers ignore `@page`): preview via the backend's `add_preview_page_margins`, rich-text via an injected, save-stripped `@media screen` style. Now documented in `ui-guidelines.md` § Document / preview viewer.
- Placeholder chips use the standard **amber** merge-field chip per `ui-guidelines.md`. (Resolved 2026-06-13: SmsComposer's green chips were aligned to amber and the guideline corrected from blue → amber. The blue `{sender_*}` chips were later removed entirely with the sender fields.)

### HtmlCodeEditor — `components/HtmlCodeEditor.tsx`
Thin CodeMirror 6 wrapper (`@uiw/react-codemirror` + `@codemirror/lang-html`) for the JobTemplateEditor HTML tab — syntax highlighting + line numbers + line wrapping. No own visual styling beyond `h-full text-[13px]`; sized by its parent's `flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-green-700/20`. Always lazy-loaded via `next/dynamic({ ssr: false })` (CodeMirror needs the DOM; keeps it off the initial bundle). New approved frontend deps — see `code-standards.md`.

---

## Templates

### TemplateSelector — `components/TemplateSelector.tsx` (110 lines)
Browse/pick a template to attach to a job (calls `attachTemplate()`). Tier-gated templates surface the backend's access error. Changing an already-attached template re-forks the job copy, so it now `confirm()`s first (in-job edits would be discarded — see JobTemplateEditor).

### TemplateCard — `components/TemplateCard.tsx`
Single template card on /templates: name, description, owner (shared `Avatar` from `template.owner_avatar` + "by {owner_name}"), visibility/tier marker, preview + download + delete + publish/unpublish actions (`downloadTemplatePdf()`, `updateTemplateVisibility()`, `deleteTemplate()`). The "Use Template" button fires the optional `onUseTemplate(id)` callback (parent opens `NewJobModal` preselected).

### TemplateBuilder — `components/TemplateBuilder.tsx`
The "Create" tab on /templates — builds a NEW library template. One shared draft (`{id, name, description, html_content}`) edited via three tabs (mirrors `JobTemplateEditor`): **Ask Volley** (`AskVolleyChat`; empty draft → `generateTemplate`, existing draft → `aiEditTemplate` refine; optional doc/image attach feeds `parsedContents`), **HTML** (lazy `HtmlCodeEditor` + `lib/templateImages` strip/inject; seeds an A4 skeleton for from-scratch), **Rich text** (iframe `srcDoc` + `execCommand`, full-doc safe). Switching tabs commits the editor into the draft; side **preview** via `previewGeneratedTemplate`; one **Save to library** (`saveTemplate`, backend re-extracts placeholders) → `onSaved`. Chat persists in `localStorage` (`vp_template_chat`).

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
- `app/templates/page.tsx` — two full-width top-level tabs: **Templates** (gallery with all/mine/public/system filter pills; cards' "Use Template" opens a page-owned `NewJobModal` preselected) and **Create** (`TemplateBuilder`).
- `app/settings/billing/page.tsx` — tier cards from `getTiers(region)`, checkout/portal/cancel/resume flows.
- `app/settings/email/page.tsx` — provider presets (Resend, SendGrid, Gmail, Outlook, Zoho, custom SMTP) + credential form.
- `app/settings/page.tsx` — settings hub (Profile, Email, SMS, Billing). Static server component; the delete-account Danger Zone moved to `/profile`.
- `app/profile/page.tsx` — profile customization: display-name editor (`updateProfile`), avatar upload (`uploadAvatar`) + preset picker grid (`lib/avatars.ts` + `Avatar`), and the account Danger Zone (delete account). Reached from the Topbar user block and the Settings hub.
- `app/page.tsx` — landing page (hero with demo.mp4, animated logo, feature sections, SEO JSON-LD in layout).

---

## Maintenance protocol

When you touch a component:
1. Keep its entry's purpose/props/pattern notes current.
2. If you established a new reusable pattern (a new badge variant, a new modal layout), promote it to `ui-guidelines.md`.
3. If you extracted inline page UI into a component, move/add its entry here.
