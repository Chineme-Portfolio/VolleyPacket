"use client";

import { useState, useEffect } from "react";
import { setSmsContent } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

interface SmsComposerProps {
  jobId: string;
  columns: string[];
  initialBody: string;
  onSaved?: () => void;
}

const SMS_CHAR_LIMIT = 160;

export default function SmsComposer({ jobId, columns, initialBody, onSaved }: SmsComposerProps) {
  const { toast } = useToast();
  const [body, setBody] = useState(initialBody);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setBody(initialBody);
  }, [initialBody]);

  const hasChanges = body !== initialBody;
  const charCount = body.length;
  const smsSegments = Math.ceil(charCount / SMS_CHAR_LIMIT) || 1;

  async function handleSave() {
    setSaving(true);
    try {
      await setSmsContent(jobId, body);
      toast("SMS content saved", "success");
      onSaved?.();
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  function insertPlaceholder(col: string) {
    setBody((prev) => prev + `{${col}}`);
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm">
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div className="text-left">
            <h3 className="text-sm font-semibold text-gray-900">SMS Content</h3>
            <p className="text-xs text-gray-500">
              {body ? `${charCount} chars · ${smsSegments} segment${smsSegments > 1 ? "s" : ""}` : "Not configured"}
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
        <div className="px-5 pb-5 space-y-4">
          {/* Placeholder tokens */}
          <div>
            <p className="text-xs text-gray-500 mb-2">Insert placeholder:</p>
            <div className="flex flex-wrap gap-1.5">
              {columns.map((col) => (
                <button
                  key={col}
                  type="button"
                  onClick={() => insertPlaceholder(col)}
                  className="px-2 py-1 text-xs font-mono text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
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
              rows={4}
              placeholder="Dear {Name}, you have been selected for..."
              className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300 transition-shadow resize-none"
            />
            <div className="flex items-center justify-between mt-1.5">
              <p className="text-xs text-gray-400">
                {charCount} / {SMS_CHAR_LIMIT} chars per segment
              </p>
              {smsSegments > 1 && (
                <p className="text-xs text-amber-600">
                  Will send as {smsSegments} SMS segments
                </p>
              )}
            </div>
          </div>

          {/* Save */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save SMS Content"}
            </button>
            {hasChanges && (
              <span className="text-xs text-amber-600">Unsaved changes</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
