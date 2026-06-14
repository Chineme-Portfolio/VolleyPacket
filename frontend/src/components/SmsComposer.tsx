"use client";

import { useState, useEffect, useCallback } from "react";
import {
  setSmsContent,
  getJobAiChats,
  setJobAiChat,
  aiDraftSms,
  getJobSampleRow,
  type JobTemplateChatMessage,
} from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";
import AskVolleyChat, { type ChatMsg, msgId } from "@/components/AskVolleyChat";

interface SmsComposerProps {
  jobId: string;
  columns: string[];
  initialBody: string;
  onSaved?: () => void;
}

type Tab = "edit" | "askvolley";

const SMS_CHAR_LIMIT = 160;

const WELCOME: ChatMsg = {
  id: "welcome",
  role: "assistant",
  text:
    "Ask Volley to draft or refine this SMS — e.g. \"remind them of the interview date\" or \"make it shorter\". Plain text only; I'll use your spreadsheet columns as placeholders and apply changes here immediately.",
};

const GENERATING_TEXT = "Drafting the SMS…";

function toChatMsgs(transcript: JobTemplateChatMessage[] | undefined): ChatMsg[] {
  if (!transcript || transcript.length === 0) return [WELCOME];
  return transcript.map((m) => ({ id: msgId(), role: m.role, text: m.content }));
}

/** Fill {Column} tokens with a data row — mirrors the backend's render_sms exactly
 * (sequential exact-name replace, so columns with spaces like {Serial Number} work). */
function renderSmsPreview(text: string, row: Record<string, string>): string {
  let out = text;
  for (const [k, v] of Object.entries(row)) out = out.split(`{${k}}`).join(v ?? "");
  return out;
}

export default function SmsComposer({ jobId, columns, initialBody, onSaved }: SmsComposerProps) {
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("edit");

  const [body, setBody] = useState(initialBody);
  const [savedBody, setSavedBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);
  const [sampleRow, setSampleRow] = useState<Record<string, string>>({});

  const [messages, setMessages] = useState<ChatMsg[]>([WELCOME]);
  const [chatInput, setChatInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [chatLoaded, setChatLoaded] = useState(false);

  useEffect(() => {
    setBody(initialBody);
    setSavedBody(initialBody);
  }, [initialBody]);

  const loadChat = useCallback(async () => {
    try {
      const chats = await getJobAiChats(jobId);
      setMessages(toChatMsgs(chats.sms));
    } catch {
      setMessages([WELCOME]);
    } finally {
      setChatLoaded(true);
    }
  }, [jobId]);

  useEffect(() => {
    if (expanded && !chatLoaded) loadChat();
  }, [expanded, chatLoaded, loadChat]);

  // First recipient's data, for the live preview.
  useEffect(() => {
    if (expanded) getJobSampleRow(jobId).then(setSampleRow).catch(() => {});
  }, [expanded, jobId]);

  const dirty = body !== savedBody;
  const charCount = body.length;
  const smsSegments = Math.ceil(charCount / SMS_CHAR_LIMIT) || 1;
  const hasSample = Object.keys(sampleRow).length > 0;
  // {tokens} in the body that don't match any spreadsheet column → would send literally.
  const unmatched = Array.from(
    new Set((body.match(/\{[^{}]+\}/g) || []).map((t) => t.slice(1, -1)))
  ).filter((t) => !columns.includes(t));

  async function handleSave() {
    setSaving(true);
    try {
      await setSmsContent(jobId, body);
      setSavedBody(body);
      onSaved?.();
      toast("SMS content saved", "success");
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
      const res = await aiDraftSms(jobId, transcript);
      setBody(res.body);
      setSavedBody(res.body);
      onSaved?.();
      setMessages((prev) =>
        prev.filter((m) => m.text !== GENERATING_TEXT).concat({ id: msgId(), role: "assistant", text: res.summary || "Updated the SMS." })
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
      await setJobAiChat(jobId, "sms", []);
    } catch {}
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
          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-gray-900">SMS Content</h3>
            <p className="text-xs text-gray-500">
              {savedBody ? `${savedBody.length} chars · ${Math.ceil(savedBody.length / SMS_CHAR_LIMIT) || 1} segment${(Math.ceil(savedBody.length / SMS_CHAR_LIMIT) || 1) > 1 ? "s" : ""}` : "Not configured"}
            </p>
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
          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-100 mb-4">
            {tabBtn("edit", "Edit")}
            {tabBtn("askvolley", "Ask Volley")}
          </div>

          {activeTab === "edit" && (
            <div className="space-y-4">
              {/* Placeholder chips */}
              <div>
                <p className="text-xs text-gray-500 mb-2">Insert placeholder:</p>
                <div className="flex flex-wrap gap-1.5">
                  {columns.map((col) => (
                    <button
                      key={col}
                      type="button"
                      onClick={() => setBody((prev) => prev + `{${col}}`)}
                      className="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-md font-mono hover:bg-amber-100 transition-colors"
                    >
                      {`{${col}}`}
                    </button>
                  ))}
                </div>
              </div>

              {/* SMS body */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Message</label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={5}
                  placeholder="Dear {Name}, you have been selected for..."
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300 transition-shadow resize-none"
                />
                <div className="flex items-center justify-between mt-1.5">
                  <p className="text-xs text-gray-400">{charCount} / {SMS_CHAR_LIMIT} chars per segment</p>
                  {smsSegments > 1 && <p className="text-xs text-amber-600">Will send as {smsSegments} SMS segments</p>}
                </div>
              </div>

              {/* Unmatched placeholder warning */}
              {unmatched.length > 0 && (
                <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                  These placeholders don&apos;t match a spreadsheet column and will send literally:{" "}
                  <span className="font-mono">{unmatched.map((u) => `{${u}}`).join(", ")}</span>
                </div>
              )}

              {/* Preview (first recipient) */}
              {body.trim() && (
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-1.5">Preview (first recipient)</p>
                  <div className="text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 whitespace-pre-wrap">
                    {renderSmsPreview(body, sampleRow)}
                  </div>
                  {!hasSample && (
                    <p className="text-[11px] text-gray-400 mt-1">No recipient data loaded yet — showing placeholders.</p>
                  )}
                </div>
              )}

              {/* Save */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleSave}
                  disabled={saving || !dirty}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
                >
                  {saving ? "Saving…" : "Save SMS Content"}
                </button>
                {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
              </div>
            </div>
          )}

          {activeTab === "askvolley" && (
            <AskVolleyChat
              messages={messages}
              input={chatInput}
              onInput={setChatInput}
              onSend={handleAskVolley}
              onClear={handleClearChat}
              generating={generating}
              placeholder="Ask Volley to draft or change this SMS…"
              className="h-[360px]"
            />
          )}
        </div>
      )}
    </div>
  );
}
