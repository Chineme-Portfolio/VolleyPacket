"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import TemplateCard from "@/components/TemplateCard";
import {
  getTemplates,
  uploadDocument,
  generateTemplate,
  saveTemplate,
  previewGeneratedTemplate,
  Template,
  UploadResponse,
} from "@/lib/api";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  attachmentName?: string;
  previewUrl?: string;
  templateData?: Record<string, unknown>;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "mine", label: "My Templates" },
  { key: "public", label: "Community" },
  { key: "system", label: "VolleyPacket" },
];

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState("all");

  // AI builder state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Hi! I can help you create a professional template. You can:\n\n• **Describe** the template you want (organization name, colors, style)\n• **Upload** an existing document (PDF, DOCX, HTML) and I'll convert it\n\nTell me what columns your data has (e.g. Name, Email, Score) and I'll create a template with those placeholders.",
    },
  ]);
  const [input, setInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState<UploadResponse | null>(null);
  const [generatedTemplate, setGeneratedTemplate] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { toast } = useToast();

  function loadTemplates(filter?: string) {
    setLoading(true);
    getTemplates(filter || activeFilter)
      .then(setTemplates)
      .catch((err: unknown) => toast(friendlyError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTemplates();
  }, [activeFilter]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function addMessage(msg: Omit<ChatMessage, "id">) {
    const id = Date.now().toString() + Math.random().toString(36).slice(2);
    setMessages((prev) => [...prev, { ...msg, id }]);
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    addMessage({ role: "user", text: `Uploaded **${file.name}**`, attachmentName: file.name });

    try {
      addMessage({ role: "system", text: "Parsing document..." });
      const result = await uploadDocument(file);
      setUploadedDoc(result);
      setMessages((prev) =>
        prev.filter((m) => m.text !== "Parsing document...").concat({
          id: Date.now().toString(),
          role: "assistant",
          text: `I've parsed **${result.filename}**. I found content like company name, subject, and body text.\n\nWould you like me to generate a template from this? You can also add instructions like "use blue colors" or "make it more formal".`,
        })
      );
    } catch (err) {
      setMessages((prev) =>
        prev.filter((m) => m.text !== "Parsing document...").concat({
          id: Date.now().toString(),
          role: "assistant",
          text: `Sorry, I couldn't parse that file. ${friendlyError(err)}`,
        })
      );
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || generating) return;
    setInput("");

    addMessage({ role: "user", text });

    if (generatedTemplate && (text.toLowerCase().includes("save") || text.toLowerCase().includes("yes"))) {
      await handleSaveTemplate();
      return;
    }

    setGenerating(true);
    addMessage({ role: "system", text: "Generating template with AI..." });

    try {
      const parsedContent = uploadedDoc
        ? { raw_text: uploadedDoc.raw_text, ...uploadedDoc.detected_fields }
        : { raw_text: text, detected_fields: {} };

      const instructions = uploadedDoc ? text : undefined;
      const template = await generateTemplate(parsedContent, instructions);
      setGeneratedTemplate(template);

      let previewUrl: string | undefined;
      try {
        previewUrl = await previewGeneratedTemplate(template);
      } catch {
        // preview generation failed — still show the template
      }

      setMessages((prev) =>
        prev.filter((m) => m.text !== "Generating template with AI...").concat({
          id: Date.now().toString(),
          role: "assistant",
          text: `Here's your template: **${(template as { name?: string }).name || "Generated Template"}**\n\nYou can:\n• Type **"save"** to add it to your library\n• Describe changes and I'll regenerate\n• Upload a different document to start over`,
          previewUrl,
          templateData: template,
        })
      );
      setUploadedDoc(null);
    } catch (err) {
      setMessages((prev) =>
        prev.filter((m) => m.text !== "Generating template with AI...").concat({
          id: Date.now().toString(),
          role: "assistant",
          text: `Template generation failed. ${friendlyError(err)}`,
        })
      );
    } finally {
      setGenerating(false);
    }
  }

  async function handleSaveTemplate() {
    if (!generatedTemplate || saving) return;
    setSaving(true);
    try {
      await saveTemplate(generatedTemplate);
      addMessage({
        role: "assistant",
        text: `Template saved! It's now available in your library. You can preview it or use it in a new job.`,
      });
      setGeneratedTemplate(null);
      loadTemplates();
    } catch (err) {
      addMessage({
        role: "assistant",
        text: `Failed to save template. ${friendlyError(err)}`,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Templates</h1>
          <p className="text-gray-500 mt-1 text-sm">Manage and create document templates.</p>
        </div>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 px-4 sm:px-5 py-2.5 bg-white text-gray-700 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors self-start"
        >
          Dashboard
        </Link>
      </div>

      {/* Template Gallery */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Templates</h2>
          <span className="text-sm text-gray-400">{templates.length} template{templates.length !== 1 ? "s" : ""}</span>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 mb-5 border-b border-gray-100 pb-0 overflow-x-auto -mx-2 px-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setActiveFilter(f.key)}
              className={`px-3 sm:px-4 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap ${
                activeFilter === f.key
                  ? "bg-green-50 text-green-800 border-b-2 border-green-700"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
              <path d="M14 2v6h6" />
            </svg>
            <p className="mt-3 text-sm">No templates yet</p>
            <p className="text-xs mt-1">Use the AI builder below to create your first template</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {templates.map((t) => (
              <TemplateCard key={t.id} template={t} onUpdate={() => loadTemplates()} />
            ))}
          </div>
        )}
      </div>

      {/* AI Template Builder */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {/* Builder header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-100">
          <div className="w-9 h-9 rounded-xl bg-green-800 flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4Z" />
              <path d="M6 10v2a6 6 0 0 0 12 0v-2" />
              <path d="M12 18v4" />
              <path d="M8 22h8" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">AI Template Builder</h2>
            <p className="text-xs text-gray-500">Describe your template or upload a document to get started</p>
          </div>
        </div>

        {/* Chat area */}
        <div className="h-[320px] sm:h-[420px] overflow-y-auto px-4 sm:px-6 py-4 space-y-4 bg-gray-50/50">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "system" ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 italic">
                  <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
                  {msg.text}
                </div>
              ) : (
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-green-800 text-white rounded-br-md"
                      : "bg-white border border-gray-200 text-gray-800 rounded-bl-md"
                  }`}
                >
                  <ChatMessageText text={msg.text} />
                  {msg.previewUrl && (
                    <div className="mt-3 rounded-xl overflow-hidden border border-gray-200">
                      <iframe src={msg.previewUrl} className="w-full h-64" title="Template preview" />
                    </div>
                  )}
                  {msg.templateData && (
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => {
                          setGeneratedTemplate(msg.templateData!);
                          handleSaveTemplate();
                        }}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-700 text-white hover:bg-green-800 transition-colors"
                      >
                        Save Template
                      </button>
                      {msg.previewUrl && (
                        <a
                          href={msg.previewUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                        >
                          Open Preview
                        </a>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input area */}
        <div className="px-6 py-4 border-t border-gray-100 bg-white">
          <div className="flex items-center gap-3">
            <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf,.doc,.docx,.html,.htm,.txt" className="hidden" />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center hover:bg-gray-200 transition-colors"
              title="Upload document"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder={uploadedDoc ? "Add instructions for the template..." : "Describe your template..."}
              className="flex-1 bg-gray-100 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 transition-shadow"
              disabled={generating}
            />
            <button
              onClick={handleSend}
              disabled={generating || !input.trim()}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-green-800 flex items-center justify-center hover:bg-green-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatMessageText({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return (
    <div>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        const lines = part.split("\n");
        return lines.map((line, j) => (
          <span key={`${i}-${j}`}>
            {j > 0 && <br />}
            {line}
          </span>
        ));
      })}
    </div>
  );
}
