"use client";

import { useState, useRef, useEffect } from "react";
import { setEmailContent, generateEmailAI } from "@/lib/api";

interface EmailComposerProps {
  jobId: string;
  columns: string[];
  initialSubject: string;
  initialBody: string;
  onSaved?: () => void;
}

interface ChatMsg {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  subject?: string;
  body?: string;
}

export default function EmailComposer({
  jobId,
  columns,
  initialSubject,
  initialBody,
  onSaved,
}: EmailComposerProps) {
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [activeTab, setActiveTab] = useState<"editor" | "ai">("editor");

  // AI chat state
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Describe the email you want to send and I'll generate the subject and body for you. I'll use your spreadsheet columns as placeholders.\n\nExample: \"A formal invitation to a training workshop on March 15th\"",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await setEmailContent(jobId, subject, body);
      setSaved(true);
      onSaved?.();
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  }

  async function handleAIGenerate() {
    const text = chatInput.trim();
    if (!text || generating) return;
    setChatInput("");

    const msgId = () => Date.now().toString() + Math.random().toString(36).slice(2);

    setMessages((prev) => [...prev, { id: msgId(), role: "user", text }]);
    setMessages((prev) => [...prev, { id: msgId(), role: "system", text: "Generating email content..." }]);
    setGenerating(true);

    try {
      const lastAI = messages.filter((m) => m.body).pop();
      const result = await generateEmailAI(text, columns, lastAI?.body || "");

      setMessages((prev) =>
        prev
          .filter((m) => m.text !== "Generating email content...")
          .concat({
            id: msgId(),
            role: "assistant",
            text: `Here's your email:\n\n**Subject:** ${result.subject}\n\nYou can use it as-is or describe changes.`,
            subject: result.subject,
            body: result.body,
          })
      );
    } catch (err) {
      setMessages((prev) =>
        prev
          .filter((m) => m.text !== "Generating email content...")
          .concat({
            id: msgId(),
            role: "assistant",
            text: `Generation failed. ${err instanceof Error ? err.message : "Please try again."}`,
          })
      );
    } finally {
      setGenerating(false);
    }
  }

  function handleUseGenerated(s: string, b: string) {
    setSubject(s);
    setBody(b);
    setActiveTab("editor");
  }

  // Preview: replace placeholders with sample data
  function previewHtml() {
    let html = body;
    columns.forEach((col) => {
      html = html.replace(new RegExp(`\\{${col}\\}`, "g"), `<span style="background:#fef3c7;padding:1px 4px;border-radius:3px;">${col}</span>`);
    });
    html = html.replace(/\{sender_name\}/g, '<span style="background:#dbeafe;padding:1px 4px;border-radius:3px;">Sender Name</span>');
    html = html.replace(/\{sender_title\}/g, '<span style="background:#dbeafe;padding:1px 4px;border-radius:3px;">Sender Title</span>');
    return html;
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header with tabs */}
      <div className="px-5 pt-4 pb-0">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900">Email Content</h3>
          <div className="flex items-center gap-1.5">
            {saved && (
              <span className="text-xs text-green-600 font-medium mr-2">Saved!</span>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 text-xs font-medium bg-green-800 text-white rounded-lg hover:bg-green-900 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
        <div className="flex gap-1 border-b border-gray-100">
          <button
            onClick={() => setActiveTab("editor")}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
              activeTab === "editor"
                ? "bg-green-50 text-green-800 border-b-2 border-green-700"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Editor
          </button>
          <button
            onClick={() => setActiveTab("ai")}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-1.5 ${
              activeTab === "ai"
                ? "bg-green-50 text-green-800 border-b-2 border-green-700"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
              <path d="M6 10v2a6 6 0 0 0 12 0v-2" />
              <path d="M12 18v4M8 22h8" />
            </svg>
            AI Compose
          </button>
        </div>
      </div>

      {/* Editor tab */}
      {activeTab === "editor" && (
        <div className="p-5 space-y-4">
          {/* Subject */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Subject Line</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Invitation for {Name} — {ExamNo}"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
            />
          </div>

          {/* Body */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-gray-700">Email Body (HTML)</label>
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="text-xs text-green-700 font-medium hover:text-green-800"
              >
                {showPreview ? "Edit" : "Preview"}
              </button>
            </div>
            {showPreview ? (
              <div
                className="w-full min-h-[200px] p-4 rounded-xl border border-gray-200 bg-gray-50 text-sm prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: previewHtml() }}
              />
            ) : (
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={10}
                placeholder="<p>Dear {Name},</p><p>Your message here...</p>"
                className="w-full px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300 font-mono"
              />
            )}
          </div>

          {/* Placeholders help */}
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs font-medium text-gray-600 mb-2">Available Placeholders</p>
            <div className="flex flex-wrap gap-1.5">
              {columns.map((col) => (
                <button
                  key={col}
                  onClick={() => {
                    if (!showPreview) setBody((b) => b + `{${col}}`);
                  }}
                  className="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-md font-mono hover:bg-amber-100 transition-colors"
                >
                  {`{${col}}`}
                </button>
              ))}
              <span className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-md font-mono">
                {"{sender_name}"}
              </span>
              <span className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded-md font-mono">
                {"{sender_title}"}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* AI tab */}
      {activeTab === "ai" && (
        <div className="flex flex-col" style={{ height: 420 }}>
          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 bg-gray-50/50">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "system" ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 italic">
                    <div className="w-3 h-3 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                    {msg.text}
                  </div>
                ) : (
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-green-800 text-white rounded-br-md"
                        : "bg-white border border-gray-200 text-gray-800 rounded-bl-md"
                    }`}
                  >
                    <BoldText text={msg.text} />
                    {msg.subject && msg.body && (
                      <button
                        onClick={() => handleUseGenerated(msg.subject!, msg.body!)}
                        className="mt-3 px-3 py-1.5 text-xs font-medium rounded-lg bg-green-700 text-white hover:bg-green-800 transition-colors"
                      >
                        Use This Email
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="px-5 py-3 border-t border-gray-100 bg-white">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleAIGenerate()}
                placeholder="Describe the email you want..."
                className="flex-1 bg-gray-100 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 transition-shadow"
                disabled={generating}
              />
              <button
                onClick={handleAIGenerate}
                disabled={generating || !chatInput.trim()}
                className="flex-shrink-0 w-10 h-10 rounded-xl bg-green-800 flex items-center justify-center hover:bg-green-900 transition-colors disabled:opacity-50"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M22 2L11 13" />
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function BoldText({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return (
    <div>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        return part.split("\n").map((line, j) => (
          <span key={`${i}-${j}`}>
            {j > 0 && <br />}
            {line}
          </span>
        ));
      })}
    </div>
  );
}
