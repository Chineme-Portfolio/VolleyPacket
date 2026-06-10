# UI Guidelines

Design tokens and assembly rules for the VolleyPacket frontend, extracted from the components as built. There is no Figma source of truth — **the existing components are the design system.** Match them exactly before inventing anything new; check `ui-registry.md` for the closest existing component first.

---

## Brand & Theme

- **Brand color: green.** Dark green (`green-800`/`green-900`) for primary actions and the sidebar identity; light greens (`green-50`–`green-100`) for tinted backgrounds and secondary actions.
- App chrome is light: page background `#f3f4f6` (gray-100), content on white cards.
- Font: **Inter** via `next/font/google` (`--font-inter`), applied on `<body>` in the root layout.

### Tokens (Tailwind v4 — `@theme inline` in `frontend/src/app/globals.css`)

```css
--color-green-950: #022c22;  --color-green-500: #10b981;
--color-green-900: #064e3b;  --color-green-400: #34d399;
--color-green-800: #065f46;  --color-green-300: #6ee7b7;
--color-green-700: #047857;  --color-green-200: #a7f3d0;
--color-green-600: #059669;  --color-green-100: #d1fae5;
                             --color-green-50:  #ecfdf5;
```

Grays/blues/reds/ambers use Tailwind's built-in scales (this project does NOT ban built-in colors — unlike a token-locked system, the green scale is the only custom palette). Body: `background-color: #f3f4f6; color: #1f2937`.

**Tailwind v4 rule:** no `tailwind.config.js`. New tokens go in `@theme` in globals.css.

---

## Layout

- Root composition: `AuthProvider → ToastProvider → AppShell`. AppShell renders **Sidebar + Topbar** around app pages, and bare layouts for public pages (landing, login, signup, blog).
- App pages: content area on `bg-gray-100`, padded, sections stacked with `space-y-*` (4–6).
- Landing/marketing pages are the only place for Framer Motion flourishes (logo spin/float, orbit animations defined in globals.css).

---

## Core Patterns (the house style)

### Cards
Every content block is a white rounded card:

```
bg-white rounded-2xl border border-gray-100 shadow-sm p-6   (p-5 for compact)
```

Card header row: `flex items-center justify-between mb-4` with title `text-lg font-semibold text-gray-900`. Modal/card section dividers: `px-6 py-4 border-b border-gray-100`.

### Buttons

| Kind | Classes |
| --- | --- |
| Primary | `px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50` |
| Secondary (green tint) | `px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors disabled:opacity-50` |
| Danger | `px-4 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-xl hover:bg-red-100 transition-colors disabled:opacity-50` |
| Subtle/utility | `px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed` |
| Icon button | `w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 transition-colors` |

Full-width action variants add `flex-1`. Every async button gets `disabled` while pending plus the spinner.

### Loading spinner

```
w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin
```

### Modals

```
overlay: fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm
panel:   bg-white rounded-2xl (border header px-6 py-4 border-b border-gray-100)
```

### Status badges
Always via `statusBadge(status)` from `lib/status.ts` — never inline the mapping:

| Status | Classes |
| --- | --- |
| created | `bg-blue-100 text-blue-700` |
| running | `bg-yellow-100 text-yellow-700` |
| complete/completed | `bg-green-100 text-green-700` |
| cancelled / failed | `bg-red-100 text-red-700` |
| interrupted | `bg-orange-100 text-orange-700` |
| (unknown) | `bg-gray-100 text-gray-600` |

### Placeholder chips (merge fields)
`{Column}` tokens render as mono chips: `px-2 py-0.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-md font-mono`.

### Progress bars
Slim rounded track `bg-gray-200 rounded-full` with a colored fill whose width is driven by `style={{ width: \`${pct}%\` }}`.

---

## Typography Hierarchy

| Role | Classes |
| --- | --- |
| Card/section title | `text-lg font-semibold text-gray-900` |
| Sub-heading / item title | `text-sm font-semibold text-gray-900` |
| Body | `text-sm text-gray-600` (or `text-gray-700`) |
| Muted / meta / timestamps | `text-xs text-gray-500` (lighter: `text-gray-400`) |
| Inline error | `text-xs text-red-600 mt-2` |
| Inline warning | `text-xs text-amber-600` |
| Link / inline action | `text-green-700 font-medium hover:text-green-800` |

---

## Radius scale (as used)

- `rounded-xl` — buttons, inputs, inner panels (the workhorse)
- `rounded-2xl` — cards and modals
- `rounded-lg` — small/utility buttons, chips' larger cousins
- `rounded-full` — pills, dots, spinners, progress tracks
- `rounded-md` — tiny chips (placeholder tokens)

---

## Feedback rules

- All transient feedback goes through the **Toast system** (`components/Toast.tsx` ToastProvider) — never `alert()`, never console-only.
- Error strings come pre-humanized from `lib/api.ts`/`lib/errors.ts` — render `err.message` as-is; don't re-wrap or expose raw JSON.
- Every async action shows a pending state (disabled + spinner) and a terminal state (toast or inline error).
- Empty states: short muted text (`text-sm text-gray-400 py-2`), optional icon, CTA when there's an obvious next step.

---

## Do Nots

- Don't bypass `statusBadge()` for status colors.
- Don't introduce a second primary color — green is the brand; blue/yellow/red/orange are reserved for status semantics, blue additionally for placeholder chips.
- Don't hand-roll modals, toasts, or progress bars — reuse the patterns above.
- Don't add a `tailwind.config.js` — Tailwind v4 `@theme` only.
- Don't put Framer Motion in app (non-landing) pages without reason — CSS `transition-colors` is the house default.
- Don't render raw backend errors or status strings without the badge/humanizing helpers.
- Don't break the card idiom: content sits on white `rounded-2xl border border-gray-100 shadow-sm` surfaces, color lives *inside* (badges, buttons, bars), not on card backgrounds.
