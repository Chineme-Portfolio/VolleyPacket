"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  generateTemplate,
  aiEditTemplate,
  saveTemplate,
  previewGeneratedTemplate,
  uploadDocument,
  UploadResponse,
} from "@/lib/api";
import { stripImages, injectImages } from "@/lib/templateImages";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";
import AskVolleyChat, { type ChatMsg, msgId } from "@/components/AskVolleyChat";

// CodeMirror needs the DOM and is sizeable — lazy-load so it only ships when the HTML tab opens.
const HtmlCodeEditor = dynamic(() => import("@/components/HtmlCodeEditor"), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

type Tab = "prompt" | "html" | "richtext";

interface Draft {
  id: string;
  name: string;
  description: string;
  html_content: string;
}

interface UploadedFile extends UploadResponse {
  imageIntent?: "embed" | "reference";
}

interface TemplateBuilderProps {
  /** Called after a template is saved to the library. */
  onSaved?: () => void;
}

const WELCOME: ChatMsg = {
  id: "welcome",
  role: "assistant",
  text:
    'Hi! Describe the template you want — organization name, colors, style, and your data columns (e.g. {Name}, {Score}) — or attach a document/image to convert. Once there\'s a draft, ask me to refine it. Prefer to build it yourself? Open the **HTML** tab.',
};

const GENERATING_TEXT = "Working on your template…";
const CHAT_STORAGE_KEY = "vp_template_chat";
const MARGIN_ID = "vp-builder-margin";
const PAGE_MARGIN_RE = /@page\b[^{]*\{[^}]*?\bmargin\s*:\s*([^;}]+)/i;

const SKELETON = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 20mm; }
  body { font-family: Arial, Helvetica, sans-serif; color: #1f2937; line-height: 1.5; }
  h1 { color: #15803d; margin: 0 0 12px; }
</style>
</head>
<body>
  <h1>{Title}</h1>
  <p>Hello {Name},</p>
  <p>Write your template here. Use {ColumnName} anywhere you want data merged in.</p>
</body>
</html>`;

function mintId(): string {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID().slice(0, 8);
  } catch {}
  return Math.random().toString(36).slice(2, 10);
}

function extractPageMargin(html: string): string {
  const m = html.match(PAGE_MARGIN_RE);
  return m ? m[1].trim() : "15mm 20mm";
}

function loadChat(): ChatMsg[] {
  if (typeof window === "undefined") return [WELCOME];
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ChatMsg[];
      const clean = parsed.filter((m) => m.role !== "system");
      if (clean.length) return clean;
    }
  } catch {}
  return [WELCOME];
}

export default function TemplateBuilder({ onSaved }: TemplateBuilderProps) {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<Tab>("prompt");
  const [draft, setDraft] = useState<Draft | null>(null);

  // Ask Volley
  const [messages, setMessages] = useState<ChatMsg[]>(() => loadChat());
  const [input, setInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // HTML tab — placeholdered HTML; images held in a sidecar map.
  const [htmlDraft, setHtmlDraft] = useState("");
  const imageMapRef = useRef<Record<string, string>>({});

  // Rich-text tab
  const richTextRef = useRef<HTMLIFrameElement>(null);

  // Preview (data URL)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages.filter((m) => m.role !== "system")));
    } catch {}
  }, [messages]);

  // ── Rich-text chrome (contenteditable + on-screen @page margin) ──────
  function handleRichTextLoad() {
    const doc = richTextRef.current?.contentDocument;
    if (!doc) return;
    if (doc.body) doc.body.setAttribute("contenteditable", "true");
    if (doc.head && !doc.getElementById(MARGIN_ID)) {
      const style = doc.createElement("style");
      style.id = MARGIN_ID;
      const margin = draft ? extractPageMargin(draft.html_content) : "15mm 20mm";
      style.textContent = `@media screen{html{box-sizing:border-box;padding:${margin};background:#fff}}`;
      doc.head.appendChild(style);
    }
  }

  function exec(command: string, value?: string) {
    const doc = richTextRef.current?.contentDocument;
    try {
      doc?.execCommand(command, false, value);
    } catch {}
  }

  function readRichText(): string | null {
    const doc = richTextRef.current?.contentDocument;
    if (!doc) return null;
    doc.body?.removeAttribute("contenteditable");
    doc.getElementById(MARGIN_ID)?.remove();
    const html = "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
    handleRichTextLoad(); // restore editing chrome
    return html;
  }

  /** Latest HTML for the active tab (commits the in-tab editor's current content). */
  function currentHtml(): string {
    if (!draft) return "";
    if (activeTab === "html") return injectImages(htmlDraft, imageMapRef.current);
    if (activeTab === "richtext") return readRichText() ?? draft.html_content;
    return draft.html_content;
  }

  // ── Tabs: commit the tab we're leaving, then switch ─────────────────
  function go(next: Tab) {
    let d = draft;
    if (d) {
      const html = currentHtml();
      if (html !== d.html_content) {
        d = { ...d, html_content: html };
        setDraft(d);
      }
    } else if (next === "html" || next === "richtext") {
      // Build from scratch — seed a minimal A4 skeleton.
      d = { id: mintId(), name: "Untitled Template", description: "", html_content: SKELETON };
      setDraft(d);
    }
    if (next === "html" && d) {
      const { html, map } = stripImages(d.html_content);
      imageMapRef.current = map;
      setHtmlDraft(html);
    }
    setActiveTab(next);
  }

  async function refreshPreview(d: Draft) {
    setPreviewLoading(true);
    try {
      const url = await previewGeneratedTemplate({
        id: d.id,
        name: d.name,
        description: d.description,
        html_content: d.html_content,
        placeholders: [],
      });
      setPreviewUrl(url);
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setPreviewLoading(false);
    }
  }

  // ── Ask Volley ───────────────────────────────────────────────────────
  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const isImage = [".png", ".jpg", ".jpeg", ".webp"].some((x) => file.name.toLowerCase().endsWith(x));
    setMessages((p) => [...p, { id: msgId(), role: "system", text: isImage ? "Analyzing image…" : "Parsing document…" }]);
    try {
      const result = await uploadDocument(file);
      setUploadedDocs((p) => [...p, isImage ? { ...result, imageIntent: "embed" } : result]);
      setMessages((p) =>
        p.filter((m) => m.role !== "system").concat({
          id: msgId(),
          role: "assistant",
          text: `Attached **${result.filename}**. Add instructions and send, and I'll build from it.`,
        })
      );
    } catch (err) {
      setMessages((p) =>
        p.filter((m) => m.role !== "system").concat({ id: msgId(), role: "assistant", text: `Couldn't read that file. ${friendlyError(err)}` })
      );
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || generating) return;
    setInput("");

    const base = draft ? currentHtml() : "";
    const transcript = messages
      .filter((m) => (m.role === "user" || m.role === "assistant") && m.id !== "welcome" && m.text)
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.text }));
    transcript.push({ role: "user", content: text });

    setMessages((p) => [...p, { id: msgId(), role: "user", text }, { id: msgId(), role: "system", text: GENERATING_TEXT }]);
    setGenerating(true);

    try {
      let html: string;
      let summary: string;
      let name: string | undefined;
      let description: string | undefined;

      if (!base.trim()) {
        const parsedContents = uploadedDocs.length
          ? uploadedDocs.map((d) => ({ raw_text: d.raw_text, ...d.detected_fields, image_intent: d.imageIntent }))
          : [{ raw_text: text, detected_fields: {} }];
        const instructions = uploadedDocs.length ? text : undefined;
        const tpl = (await generateTemplate(parsedContents, instructions)) as Record<string, unknown>;
        html = String(tpl.html_content || "");
        name = (tpl.name as string) || "Untitled Template";
        description = (tpl.description as string) || "";
        summary = `Created **${name}** — see the preview. Refine here, fine-tune in HTML / Rich text, then Save.`;
        setUploadedDocs([]);
      } else {
        const r = await aiEditTemplate(base, transcript);
        html = r.html_content;
        summary = r.summary || "Updated — see the preview.";
      }

      const next: Draft = {
        id: draft?.id || mintId(),
        name: name ?? draft?.name ?? "Untitled Template",
        description: description ?? draft?.description ?? "",
        html_content: html,
      };
      setDraft(next);
      if (activeTab === "html") {
        const { html: stripped, map } = stripImages(html);
        imageMapRef.current = map;
        setHtmlDraft(stripped);
      }
      await refreshPreview(next);
      setMessages((p) => p.filter((m) => m.text !== GENERATING_TEXT).concat({ id: msgId(), role: "assistant", text: summary }));
    } catch (err) {
      setMessages((p) =>
        p.filter((m) => m.text !== GENERATING_TEXT).concat({ id: msgId(), role: "assistant", text: `Sorry — ${friendlyError(err)}` })
      );
    } finally {
      setGenerating(false);
    }
  }

  function handleClear() {
    setMessages([WELCOME]);
    setUploadedDocs([]);
  }

  // ── Preview / Save ──────────────────────────────────────────────────
  async function handleUpdatePreview() {
    if (!draft) return;
    const next = { ...draft, html_content: currentHtml() };
    setDraft(next);
    await refreshPreview(next);
  }

  async function handleSave() {
    if (!draft || saving) return;
    if (!draft.name.trim()) {
      toast("Give your template a name first.", "error");
      return;
    }
    const html = currentHtml();
    setSaving(true);
    try {
      await saveTemplate({
        id: draft.id,
        name: draft.name.trim(),
        description: draft.description,
        html_content: html,
        placeholders: [],
      });
      setDraft({ ...draft, html_content: html });
      toast("Template saved", "success");
      onSaved?.();
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  const tabBtn = (tab: Tab, label: string) => (
    <button
      onClick={() => go(tab)}
      className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
        activeTab === tab ? "bg-green-50 text-green-800 border-b-2 border-green-700" : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-6">
      {/* Name + description + Save */}
      <div className="flex flex-col lg:flex-row lg:items-end gap-3 mb-5">
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-500 mb-1">Template name</label>
          <input
            type="text"
            value={draft?.name ?? ""}
            onChange={(e) => setDraft((d) => (d ? { ...d, name: e.target.value } : { id: mintId(), name: e.target.value, description: "", html_content: "" }))}
            placeholder="Untitled Template"
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs font-medium text-gray-500 mb-1">Description</label>
          <input
            type="text"
            value={draft?.description ?? ""}
            onChange={(e) => setDraft((d) => (d ? { ...d, description: e.target.value } : { id: mintId(), name: "", description: e.target.value, html_content: "" }))}
            placeholder="Optional"
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
          />
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !draft || !draft.html_content.trim()}
          className="px-6 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save to library"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-100 mb-4">
        {tabBtn("prompt", "Ask Volley")}
        {tabBtn("html", "HTML")}
        {tabBtn("richtext", "Rich text")}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Editor column */}
        <div className="min-h-[460px] flex flex-col">
          {activeTab === "prompt" && (
            <div className="flex flex-col h-[460px]">
              <div className="flex items-center gap-2 mb-2">
                <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf,.doc,.docx,.html,.htm,.txt,.png,.jpg,.jpeg,.webp" className="hidden" />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={generating}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                  </svg>
                  Attach document / image
                </button>
                {uploadedDocs.map((d, i) => (
                  <span key={i} className="px-2 py-1 text-[11px] bg-green-50 text-green-700 border border-green-200 rounded-lg max-w-[140px] truncate">
                    {d.filename}
                  </span>
                ))}
              </div>
              <div className="flex-1 min-h-0">
                <AskVolleyChat
                  messages={messages}
                  input={input}
                  onInput={setInput}
                  onSend={handleSend}
                  onClear={handleClear}
                  generating={generating}
                  placeholder={draft ? "Refine the template — e.g. make the header navy…" : "Describe the template you want…"}
                  notice="Chat is saved locally and clears when you log out."
                />
              </div>
            </div>
          )}

          {activeTab === "html" && (
            <div className="flex flex-col h-[460px]">
              <p className="text-[11px] text-gray-500 mb-1.5">
                Write the full HTML document. Use <code className="font-mono text-gray-600">{"{Column}"}</code> for merge fields; embedded images show as{" "}
                <code className="font-mono text-gray-600">{"{EMBEDDED_IMAGE_N}"}</code> and are restored on save.
              </p>
              <div className="flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-green-700/20 focus-within:border-green-300">
                <HtmlCodeEditor value={htmlDraft} onChange={setHtmlDraft} />
              </div>
              <div className="mt-3">
                <button
                  onClick={handleUpdatePreview}
                  className="px-4 py-2 text-sm font-medium text-green-800 bg-green-50 rounded-xl hover:bg-green-100 transition-colors"
                >
                  Update preview
                </button>
              </div>
            </div>
          )}

          {activeTab === "richtext" && (
            <div className="flex flex-col h-[460px]">
              <div className="flex flex-wrap items-center gap-1 mb-2">
                {[
                  { cmd: "bold", label: "B", cls: "font-bold" },
                  { cmd: "italic", label: "I", cls: "italic" },
                  { cmd: "underline", label: "U", cls: "underline" },
                ].map((b) => (
                  <button
                    key={b.cmd}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => exec(b.cmd)}
                    className={`w-8 h-8 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 ${b.cls}`}
                  >
                    {b.label}
                  </button>
                ))}
                <span className="w-px h-5 bg-gray-200 mx-1" />
                {[
                  { cmd: "insertUnorderedList", label: "• List" },
                  { cmd: "insertOrderedList", label: "1. List" },
                ].map((b) => (
                  <button
                    key={b.cmd}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => exec(b.cmd)}
                    className="h-8 px-2 rounded-lg border border-gray-200 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    {b.label}
                  </button>
                ))}
                <span className="w-px h-5 bg-gray-200 mx-1" />
                {[
                  { cmd: "justifyLeft", label: "↤" },
                  { cmd: "justifyCenter", label: "↔" },
                  { cmd: "justifyRight", label: "↦" },
                ].map((b) => (
                  <button
                    key={b.cmd}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => exec(b.cmd)}
                    className="w-8 h-8 rounded-lg border border-gray-200 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    {b.label}
                  </button>
                ))}
                <span className="w-px h-5 bg-gray-200 mx-1" />
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    const url = window.prompt("Link URL:");
                    if (url) exec("createLink", url);
                  }}
                  className="h-8 px-2 rounded-lg border border-gray-200 text-xs text-gray-700 hover:bg-gray-50"
                >
                  Link
                </button>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => exec("removeFormat")}
                  className="h-8 px-2 rounded-lg border border-gray-200 text-xs text-gray-700 hover:bg-gray-50"
                >
                  Clear
                </button>
              </div>
              <div className="flex-1 rounded-xl border border-gray-200 bg-green-50 p-3 sm:p-4 overflow-auto">
                <iframe
                  ref={richTextRef}
                  title="Rich text editor"
                  srcDoc={draft?.html_content ?? ""}
                  sandbox="allow-same-origin"
                  onLoad={handleRichTextLoad}
                  className="w-full h-full rounded-md bg-white shadow-sm border-0"
                />
              </div>
              <div className="flex items-center gap-3 mt-3">
                <button
                  onClick={handleUpdatePreview}
                  className="px-4 py-2 text-sm font-medium text-green-800 bg-green-50 rounded-xl hover:bg-green-100 transition-colors"
                >
                  Update preview
                </button>
                <span className="text-xs text-gray-400">Edits visible text only; layout & styles are preserved.</span>
              </div>
            </div>
          )}
        </div>

        {/* Preview column */}
        <div className="min-h-[460px] flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-gray-600">Preview</p>
            {previewLoading && <div className="w-3.5 h-3.5 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />}
          </div>
          <div className="flex-1 rounded-xl border border-gray-200 bg-green-50 p-3 sm:p-4 overflow-auto">
            {previewUrl ? (
              <iframe title="Template preview" src={previewUrl} sandbox="allow-same-origin" className="w-full h-full rounded-md bg-white shadow-sm border-0" />
            ) : (
              <div className="w-full h-full rounded-md bg-white shadow-sm flex items-center justify-center text-sm text-gray-400 text-center px-6">
                Generate with Ask Volley or start in the HTML tab — your preview appears here.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
