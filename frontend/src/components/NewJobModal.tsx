"use client";

import { useEffect, useRef, useState } from "react";
import { Template, createJob, attachTemplate, getTemplates } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

interface NewJobModalProps {
  onClose: () => void;
  onCreated: (jobId: string) => void;
}

export default function NewJobModal({ onClose, onCreated }: NewJobModalProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isAllocated, setIsAllocated] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getTemplates()
      .then((t) => {
        setTemplates(t);
        if (t.length > 0) setSelectedTemplate(t[0].id);
      })
      .catch((err: unknown) => setError(friendlyError(err)))
      .finally(() => setLoadingTemplates(false));
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Please upload a candidate data sheet.");
      return;
    }
    if (!selectedTemplate) {
      setError("Please select a template.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const job = await createJob(file, isAllocated);
      await attachTemplate(job.job_id, selectedTemplate);
      onCreated(job.job_id);
    } catch (err) {
      setError(friendlyError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-[90vw] max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">New Job</h2>
            <p className="text-xs text-gray-500 mt-0.5">Upload candidate data and select a template</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {/* File upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Candidate Data Sheet</label>
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setError("");
              }}
              accept=".xlsx,.xls,.csv"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-dashed border-gray-200 hover:border-green-300 hover:bg-green-50/50 transition-colors text-left"
            >
              <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                  <path d="M14 2v6h6" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                {file ? (
                  <>
                    <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
                    <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-gray-500">Click to upload</p>
                    <p className="text-xs text-gray-400">.xlsx, .xls, or .csv</p>
                  </>
                )}
              </div>
              {file && (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              )}
            </button>
          </div>

          {/* Pre-allocated checkbox */}
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={isAllocated}
              onChange={(e) => setIsAllocated(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-green-700 focus:ring-green-700"
            />
            <div>
              <span className="text-sm font-medium text-gray-700">Data is pre-allocated</span>
              <p className="text-xs text-gray-400">Check if halls/times are already assigned</p>
            </div>
          </label>

          {/* Template select */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Template</label>
            {loadingTemplates ? (
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
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300 transition-shadow appearance-none"
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-xl">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !file || !selectedTemplate}
              className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {submitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Job"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
