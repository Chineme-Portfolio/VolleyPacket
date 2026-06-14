"use client";

import { useState, useEffect, useCallback } from "react";
import dynamic from "next/dynamic";
import {
  setEmailContent,
  getJobAiChats,
  setJobAiChat,
  aiDraftEmail,
  type JobTemplateChatMessage,
} from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";
import AskVolleyChat, { type ChatMsg, msgId } from "@/components/AskVolleyChat";
import RichTextEditor from "@/components/RichTextEditor";

const HtmlCodeEditor = dynamic(() => import("@/components/HtmlCodeEditor"), {
  ssr: false,
  loading: () => (
    <div className="h-full flex items-center justify-center">
      <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
    </div>
  ),
});

interface EmailComposerProps {
  jobId: string;
  columns: string[];
  initialSubject: string;
  initialBody: string;
  onSaved?: () => void;
}

type Tab = "askvolley" | "richtext" | "html";

const WELCOME: ChatMsg = {
  id: "welcome",
  role: "assistant",
  text:
    "Ask Volley to draft or refine this email — e.g. \"a formal invitation to the oral interview\" or \"make the tone warmer and add the venue\". I'll use your spreadsheet columns as placeholders, and apply changes here immediately.",
};

const GENERATING_TEXT = "Drafting the email…";

function toChatMsgs(transcript: JobTemplateChatMessage[] | undefined): ChatMsg[] {
  if (!transcript || transcript.length === 0) return [WELCOME];
  return transcript.map((m) => ({ id: msgId(), role: m.role, text: m.content }));
}

export default function EmailComposer({ jobId, columns, initialSubject, initialBody, onSaved }: EmailComposerProps) {
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("askvolley");

  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [savedSubject, setSavedSubject] = useState(initialSubject);
  const [savedBody, setSavedBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);

  // Ask Volley
  const [messages, setMessages] = useState<ChatMsg[]>([WELCOME]);
  const [chatInput, setChatInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [chatLoaded, setChatLoaded] = useState(false);

  useEffect(() => {
    setSubject(initialSubject);
    setSavedSubject(initialSubject);
  }, [initialSubject]);
  useEffect(() => {
    setBody(initialBody);
    setSavedBody(initialBody);
  }, [initialBody]);

  const loadChat = useCallback(async () => {
    try {
      const chats = await getJobAiChats(jobId);
      setMessages(toChatMsgs(chats.email));
    } catch {
      setMessages([WELCOME]);
    } finally {
      setChatLoaded(true);
    }
  }, [jobId]);

  useEffect(() => {
    if (expanded && !chatLoaded) loadChat();
  }, [expanded, chatLoaded, loadChat]);

  const dirty = subject !== savedSubject || body !== savedBody;
  // {tokens} in the subject/body that don't match any spreadsheet column → would send literally.
  const unmatched = Array.from(
    new Set(
      [...(subject.match(/\{[^{}]+\}/g) || []), ...(body.match(/\{[^{}]+\}/g) || [])].map((t) => t.slice(1, -1))
    )
  ).filter((t) => !columns.includes(t));

  async function handleSave() {
    setSaving(true);
    try {
      await setEmailContent(jobId, subject, body);
      setSavedSubject(subject);
      setSavedBody(body);
      onSaved?.();
      toast("Email content saved", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleAskVolley() {
    const text = chatInput.trim();
    if (!text || generating) return;
    setChatInput("");

    const transcript: JobTemplateChatMessage[] = messages
      .filter((m) => m.id !== "welcome" && (m.role === "user" || m.role === "assistant") && m.text)
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.text }));
    transcript.push({ role: "user", content: text });

    setMessages((prev) => [...prev, { id: msgId(), role: "user", text }]);
    setMessages((prev) => [...prev, { id: msgId(), role: "system", text: GENERATING_TEXT }]);
    setGenerating(true);
    try {
      const res = await aiDraftEmail(jobId, transcript);
      // AI applied + saved server-side — sync local editors + baseline.
      setSubject(res.subject);
      setBody(res.body);
      setSavedSubject(res.subject);
      setSavedBody(res.body);
      onSaved?.();
      setMessages((prev) =>
        prev.filter((m) => m.text !== GENERATING_TEXT).concat({ id: msgId(), role: "assistant", text: res.summary || "Updated the email." })
      );
    } catch (err) {
      setMessages((prev) =>
        prev.filter((m) => m.text !== GENERATING_TEXT).concat({ id: msgId(), role: "assistant", text: `Draft failed. ${friendlyError(err)}` })
      );
    } finally {
      setGenerating(false);
    }
  }

  async function handleClearChat() {
    setMessages([WELCOME]);
    try {
      await setJobAiChat(jobId, "email", []);
    } catch {}
  }

  function insertPlaceholder(token: string) {
    if (activeTab === "richtext") document.execCommand("insertText", false, token);
    else if (activeTab === "html") setBody((b) => b + token);
  }

  const tabBtn = (tab: Tab, label: string) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
        activeTab === tab ? "bg-green-50 text-green-800 border-b-2 border-green-700" : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Collapsible header */}
      <button type="button" onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#15803d" strokeWidth="2">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="M22 7l-10 6L2 7" />
            </svg>
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-gray-900">Email Content</h3>
            <p className="text-xs text-gray-500">{savedSubject ? savedSubject : "Not configured"}</p>
          </div>
        </div>
        <svg
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2"
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 pb-5">
          {/* Subject */}
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Subject Line</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Your document for {Name}"
              className="w-full px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
            />
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-100 mb-4">
            {tabBtn("askvolley", "Ask Volley")}
            {tabBtn("richtext", "Rich text")}
            {tabBtn("html", "HTML")}
          </div>

          {activeTab === "askvolley" && (
            <AskVolleyChat
              messages={messages}
              input={chatInput}
              onInput={setChatInput}
              onSend={handleAskVolley}
              onClear={handleClearChat}
              generating={generating}
              placeholder="Ask Volley to draft or change this email…"
            />
          )}

          {activeTab === "richtext" && <RichTextEditor value={body} onChange={setBody} />}

          {activeTab === "html" && (
            <div className="flex flex-col h-[420px]">
              <div className="flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white focus-within:ring-2 focus-within:ring-green-700/20 focus-within:border-green-300">
                <HtmlCodeEditor value={body} onChange={setBody} />
              </div>
            </div>
          )}

          {/* Placeholder chips (not on the chat tab) */}
          {activeTab !== "askvolley" && (
            <div className="mt-3 bg-gray-50 rounded-xl p-3">
              <p className="text-xs font-medium text-gray-600 mb-2">Insert placeholder</p>
              <div className="flex flex-wrap gap-1.5">
                {columns.map((col) => (
                  <button
                    key={col}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => insertPlaceholder(`{${col}}`)}
                    className="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-md font-mono hover:bg-amber-100 transition-colors"
                  >
                    {`{${col}}`}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Unmatched placeholder warning (subject + body) */}
          {activeTab !== "askvolley" && unmatched.length > 0 && (
            <div className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
              These placeholders don&apos;t match a spreadsheet column and will send literally:{" "}
              <span className="font-mono">{unmatched.map((u) => `{${u}}`).join(", ")}</span>
            </div>
          )}

          {/* Footer: manual save (Ask Volley applies immediately) */}
          {activeTab !== "askvolley" && (
            <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-100">
              <button
                onClick={handleSave}
                disabled={saving || !dirty}
                className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save Email Content"}
              </button>
              {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
