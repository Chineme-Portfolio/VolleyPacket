"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  getJobTemplate,
  saveJobTemplate,
  aiEditJobTemplate,
  resetJobTemplate,
  getJobTemplatePreviewUrl,
  getJobAiChats,
  setJobAiChat,
  type JobTemplate,
} from "@/lib/api";
import { stripImages, injectImages } from "@/lib/templateImages";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";
import AskVolleyChat, { type ChatMsg, msgId } from "@/components/AskVolleyChat";

interface JobTemplateEditorProps {
  jobId: string;
  columns: string[];
  templateId: string | null;
  /** True while a task is running — editing is locked. */
  disabled?: boolean;
  /** Called after a successful edit so the parent can reload the job (placeholders/mapping change). */
  onChanged?: () => void;
}

type Tab = "prompt" | "html" | "richtext";

const WELCOME: ChatMsg = {
  id: "welcome",
  role: "assistant",
  text:
    'Ask Volley to change this template — e.g. "make the header navy", "add a signature line under the body", or "increase the body font size". Your columns and a few sample rows are sent as context, and embedded images (logo, signature, letterhead) are always preserved.',
};

const GENERATING_TEXT = "Editing the template…";

// CodeMirror needs the DOM and is sizeable — lazy-load it so it only ships
// when the HTML tab is actually opened.
const HtmlCodeEditor = dynamic(() => import("@/components/HtmlCodeEditor"), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

const PAGE_MARGIN_RE = /@page\b[^{]*\{[^}]*?\bmargin\s*:\s*([^;}]+)/i;
const EDITOR_MARGIN_STYLE_ID = "vp-editor-margin";

/** The template's @page margin (browsers ignore @page on screen; mirrors the backend's add_preview_page_margins). */
function extractPageMargin(html: string): string {
  const m = html.match(PAGE_MARGIN_RE);
  return m ? m[1].trim() : "15mm 20mm";
}

export default function JobTemplateEditor({
  jobId,
  columns,
  templateId,
  disabled = false,
  onChanged,
}: JobTemplateEditorProps) {
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("prompt");
  const [insertAs, setInsertAs] = useState<"text" | "qr" | "barcode">("text");

  const [template, setTemplate] = useState<JobTemplate | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Preview (object URL — revoked on replace/unmount)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewUrlRef = useRef<string | null>(null);

  // HTML tab — works on placeholdered HTML; images held in a sidecar map.
  const [htmlDraft, setHtmlDraft] = useState("");
  const [savedHtml, setSavedHtml] = useState("");
  const imageMapRef = useRef<Record<string, string>>({});

  // Rich-text tab
  const editIframeRef = useRef<HTMLIFrameElement>(null);

  // Ask Volley tab
  const [messages, setMessages] = useState<ChatMsg[]>([WELCOME]);
  const [chatInput, setChatInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [chatLoaded, setChatLoaded] = useState(false);

  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  const applyTemplate = useCallback((t: JobTemplate) => {
    setTemplate(t);
    const { html, map } = stripImages(t.html_content);
    imageMapRef.current = map;
    setHtmlDraft(html);
    setSavedHtml(html);
  }, []);

  const refreshPreview = useCallback(async () => {
    setPreviewLoading(true);
    try {
      const url = await getJobTemplatePreviewUrl(jobId);
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = url;
      setPreviewUrl(url);
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setPreviewLoading(false);
    }
  }, [jobId, toast]);

  const loadTemplate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const t = await getJobTemplate(jobId);
      applyTemplate(t);
      await refreshPreview();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, [jobId, applyTemplate, refreshPreview]);

  // Lazy-load the template the first time the section is opened.
  useEffect(() => {
    if (expanded && !disabled && !loaded && !loading) loadTemplate();
  }, [expanded, disabled, loaded, loading, loadTemplate]);

  // Re-fetch if the attached template changes (re-fork discards prior edits).
  useEffect(() => {
    setLoaded(false);
    setTemplate(null);
  }, [templateId]);

  // Load the server-persisted Ask Volley transcript on first open.
  const loadChat = useCallback(async () => {
    try {
      const chats = await getJobAiChats(jobId);
      const t = chats.template;
      setMessages(t && t.length ? t.map((m) => ({ id: msgId(), role: m.role, text: m.content })) : [WELCOME]);
    } catch {
      setMessages([WELCOME]);
    } finally {
      setChatLoaded(true);
    }
  }, [jobId]);

  useEffect(() => {
    if (expanded && !chatLoaded) loadChat();
  }, [expanded, chatLoaded, loadChat]);

  // Revoke the preview object URL on unmount.
  useEffect(
    () => () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    []
  );

  const htmlDirty = htmlDraft !== savedHtml;

  async function handleSaveHtml() {
    if (!template) return;
    setSaving(true);
    try {
      const inline = injectImages(htmlDraft, imageMapRef.current);
      const t = await saveJobTemplate(jobId, inline);
      applyTemplate(t);
      await refreshPreview();
      onChanged?.();
      toast("Template saved", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveRichText() {
    const doc = editIframeRef.current?.contentDocument;
    if (!doc) return;
    setSaving(true);
    try {
      const body = doc.body;
      // Strip editing-only affordances so they never persist into the saved HTML / PDF:
      // the contenteditable flag and the on-screen page-margin style.
      body?.removeAttribute("contenteditable");
      doc.getElementById(EDITOR_MARGIN_STYLE_ID)?.remove();
      const html = "<!DOCTYPE html>\n" + doc.documentElement.outerHTML;
      handleEditIframeLoad(); // restore editing chrome in case the save fails
      const t = await saveJobTemplate(jobId, html);
      applyTemplate(t);
      await refreshPreview();
      onChanged?.();
      toast("Template saved", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  function handleEditIframeLoad() {
    const doc = editIframeRef.current?.contentDocument;
    if (!doc) return;
    if (doc.body) doc.body.setAttribute("contenteditable", "true");
    // Reproduce the template's @page margin on screen (browsers ignore @page; WeasyPrint
    // honors it in the PDF). Marked by id + wrapped in @media screen so it's stripped
    // before save and is inert in WeasyPrint anyway — never persisted into the template.
    if (doc.head && !doc.getElementById(EDITOR_MARGIN_STYLE_ID)) {
      const style = doc.createElement("style");
      style.id = EDITOR_MARGIN_STYLE_ID;
      const margin = template ? extractPageMargin(template.html_content) : "15mm 20mm";
      style.textContent = `@media screen{html{box-sizing:border-box;padding:${margin};background:#fff}}`;
      doc.head.appendChild(style);
    }
  }

  function exec(command: string, value?: string) {
    const doc = editIframeRef.current?.contentDocument;
    if (!doc) return;
    try {
      doc.execCommand(command, false, value);
    } catch {}
  }

  async function handleAiSend() {
    const text = chatInput.trim();
    if (!text || generating || !template) return;
    setChatInput("");

    // Build the API transcript from prior turns BEFORE adding the new message.
    const transcript = messages
      .filter((m) => (m.role === "user" || m.role === "assistant") && m.id !== "welcome" && m.text)
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.text }));
    transcript.push({ role: "user", content: text });

    setMessages((prev) => [...prev, { id: msgId(), role: "user", text }]);
    setMessages((prev) => [...prev, { id: msgId(), role: "system", text: GENERATING_TEXT }]);
    setGenerating(true);

    try {
      const result = await aiEditJobTemplate(jobId, transcript);
      applyTemplate(result.template);
      await refreshPreview();
      onChanged?.();
      setMessages((prev) =>
        prev
          .filter((m) => m.text !== GENERATING_TEXT)
          .concat({ id: msgId(), role: "assistant", text: result.summary || "Done." })
      );
    } catch (err) {
      setMessages((prev) =>
        prev
          .filter((m) => m.text !== GENERATING_TEXT)
          .concat({ id: msgId(), role: "assistant", text: `Edit failed. ${friendlyError(err)}` })
      );
    } finally {
      setGenerating(false);
    }
  }

  async function handleClearChat() {
    setMessages([WELCOME]);
    try {
      await setJobAiChat(jobId, "template", []);
    } catch {}
  }

  async function handleReset() {
    if (
      !window.confirm(
        "Reset this job's template to the original library version? Your in-job edits will be lost."
      )
    )
      return;
    setResetting(true);
    try {
      const t = await resetJobTemplate(jobId);
      applyTemplate(t);
      await refreshPreview();
      onChanged?.();
      toast("Template reset to original", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setResetting(false);
    }
  }

  const tabBtn = (tab: Tab, label: string) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
        activeTab === tab
          ? "bg-green-50 text-green-800 border-b-2 border-green-700"
          : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#15803d" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
            </svg>
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-gray-900">Edit Template</h3>
            <p className="text-xs text-gray-500">
              {template
                ? `${template.name} · ${template.placeholders.length} placeholder${
                    template.placeholders.length === 1 ? "" : "s"
                  }`
                : "Tailor this job's copy by prompt, HTML, or rich text"}
            </p>
          </div>
        </div>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#9ca3af"
          strokeWidth="2"
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 pb-5">
          {disabled ? (
            <p className="text-sm text-gray-500 bg-gray-50 rounded-xl p-4">
              Editing is locked while a task is running. Pause or wait for it to finish, then edit the
              template here.
            </p>
          ) : loading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500 py-6">
              <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
              Loading template…
            </div>
          ) : error ? (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl p-4">
              {error}
              <button onClick={loadTemplate} className="ml-2 underline hover:no-underline">
                Retry
              </button>
            </div>
          ) : template ? (
            <>
              {/* Tabs */}
              <div className="flex gap-1 border-b border-gray-100 mb-4">
                {tabBtn("prompt", "Ask Volley")}
                {tabBtn("html", "HTML")}
                {tabBtn("richtext", "Rich text")}
              </div>

              <div className="grid lg:grid-cols-2 gap-4">
                {/* Editor column */}
                <div className="min-h-[420px] flex flex-col">
                  {/* Ask Volley tab */}
                  {activeTab === "prompt" && (
                    <AskVolleyChat
                      messages={messages}
                      input={chatInput}
                      onInput={setChatInput}
                      onSend={handleAiSend}
                      onClear={handleClearChat}
                      generating={generating}
                      placeholder="Ask Volley to change this template…"
                      notice="Edits apply immediately and are saved with the job."
                    />
                  )}

                  {/* HTML tab */}
                  {activeTab === "html" && (
                    <div className="flex flex-col h-[420px]">
                      <p className="text-[11px] text-gray-500 mb-1.5">
                        Embedded images are shown as{" "}
                        <code className="font-mono text-gray-600">{"{EMBEDDED_IMAGE_N}"}</code> and restored
                        on save.
                      </p>
                      <div className="flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-green-700/20 focus-within:border-green-300">
                        <HtmlCodeEditor value={htmlDraft} onChange={setHtmlDraft} />
                      </div>
                      <div className="flex items-center gap-3 mt-3">
                        <button
                          onClick={handleSaveHtml}
                          disabled={saving || !htmlDirty}
                          className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
                        >
                          {saving ? "Saving…" : "Save HTML"}
                        </button>
                        {htmlDirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
                      </div>
                    </div>
                  )}

                  {/* Rich text tab */}
                  {activeTab === "richtext" && (
                    <div className="flex flex-col h-[420px]">
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
                          ref={editIframeRef}
                          title="Rich text editor"
                          srcDoc={template.html_content}
                          sandbox="allow-same-origin"
                          onLoad={handleEditIframeLoad}
                          className="w-full h-full rounded-md bg-white shadow-sm border-0"
                        />
                      </div>
                      <div className="flex items-center gap-3 mt-3">
                        <button
                          onClick={handleSaveRichText}
                          disabled={saving}
                          className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
                        >
                          {saving ? "Saving…" : "Save changes"}
                        </button>
                        <span className="text-xs text-gray-400">
                          Edits visible text only; layout & styles are preserved. Switching tabs discards
                          unsaved changes.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Column / code chips — shared helper for HTML & rich text */}
                  {activeTab !== "prompt" && columns.length > 0 && (
                    <div className="mt-3 bg-gray-50 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-medium text-gray-600">
                          Insert {insertAs === "text" ? "placeholder" : insertAs === "qr" ? "QR code" : "barcode"}
                        </p>
                        <div className="flex gap-1">
                          {([["text", "Text"], ["qr", "QR"], ["barcode", "Barcode"]] as const).map(([m, label]) => (
                            <button
                              key={m}
                              type="button"
                              onClick={() => setInsertAs(m)}
                              className={`px-2 py-0.5 text-[11px] rounded-md border transition-colors ${
                                insertAs === m ? "bg-green-700 text-white border-green-700" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {columns.map((col) => {
                          const token = insertAs === "qr" ? `{QR:${col}}` : insertAs === "barcode" ? `{BARCODE:${col}}` : `{${col}}`;
                          return (
                            <button
                              key={col}
                              type="button"
                              onMouseDown={(e) => e.preventDefault()}
                              onClick={() => {
                                if (activeTab === "html") setHtmlDraft((h) => h + token);
                                else exec("insertText", token);
                              }}
                              className="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-md font-mono hover:bg-amber-100 transition-colors"
                            >
                              {token}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Preview column */}
                <div className="min-h-[420px] flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium text-gray-600">Preview (first data row)</p>
                    {previewLoading && (
                      <div className="w-3.5 h-3.5 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                    )}
                  </div>
                  <div className="flex-1 rounded-xl border border-gray-200 bg-green-50 p-3 sm:p-4 overflow-auto">
                    {previewUrl ? (
                      <iframe
                        title="Template preview"
                        src={previewUrl}
                        sandbox="allow-same-origin"
                        className="w-full h-full rounded-md bg-white shadow-sm border-0"
                      />
                    ) : (
                      <div className="w-full h-full rounded-md bg-white shadow-sm" />
                    )}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                <p className="text-xs text-gray-400">
                  Edits affect only this job — your saved library template is untouched.
                </p>
                <button
                  onClick={handleReset}
                  disabled={resetting}
                  className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  {resetting ? "Resetting…" : "Reset to original"}
                </button>
              </div>
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
