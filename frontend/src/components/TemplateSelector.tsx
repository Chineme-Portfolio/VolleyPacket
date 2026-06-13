"use client";

import { useEffect, useState } from "react";
import { getTemplates, attachTemplate, Template } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

interface TemplateSelectorProps {
  jobId: string;
  currentTemplateId: string | null;
  disabled?: boolean;
  onChanged?: () => void;
}

export default function TemplateSelector({ jobId, currentTemplateId, disabled, onChanged }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedId, setSelectedId] = useState(currentTemplateId || "");
  const [error, setError] = useState("");

  useEffect(() => {
    getTemplates()
      .then((t) => {
        setTemplates(t);
        if (!selectedId && t.length > 0) setSelectedId(t[0].id);
      })
      .catch((err) => setError(friendlyError(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setSelectedId(currentTemplateId || "");
  }, [currentTemplateId]);

  async function handleChange() {
    if (!selectedId || selectedId === currentTemplateId) return;
    // Re-attaching re-forks the job's template, discarding any in-job edits.
    if (
      currentTemplateId &&
      !window.confirm(
        "Switch templates? Any edits you made to this job's template will be replaced by the new one."
      )
    )
      return;
    setSaving(true);
    setError("");
    try {
      await attachTemplate(jobId, selectedId);
      onChanged?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  const currentName = templates.find((t) => t.id === currentTemplateId)?.name;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center flex-shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <path d="M3 9h18M9 21V9" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Template</h3>
          <p className="text-xs text-gray-500">
            {currentTemplateId ? currentName || currentTemplateId : "No template attached"}
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
          <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
          Loading templates...
        </div>
      ) : templates.length === 0 ? (
        <p className="text-sm text-gray-400 py-2">
          No templates available.{" "}
          <a href="/templates" className="text-green-700 font-medium hover:text-green-800">
            Create one first
          </a>
        </p>
      ) : (
        <div className="flex items-center gap-3">
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            disabled={disabled || saving}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300 transition-shadow appearance-none disabled:opacity-50"
          >
            {!currentTemplateId && <option value="">Select a template...</option>}
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleChange}
            disabled={disabled || saving || !selectedId || selectedId === currentTemplateId}
            className="px-4 py-2.5 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50 flex-shrink-0"
          >
            {saving ? "Saving..." : currentTemplateId ? "Change" : "Attach"}
          </button>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 mt-2">{error}</p>
      )}
    </div>
  );
}
