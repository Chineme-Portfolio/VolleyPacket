"use client";

import { useState, useRef } from "react";

interface JobModeSelectorProps {
  currentMode: string;
  onModeChange: (mode: string, file?: File) => Promise<void>;
  disabled?: boolean;
}

const MODES = [
  {
    key: "email_only",
    label: "Email Only",
    desc: "Send personalized emails without any attachments",
    icon: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2ZM22 6l-10 7L2 6",
  },
  {
    key: "static_attachment",
    label: "Static Attachment",
    desc: "Same file attached to every email",
    icon: "M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48",
  },
  {
    key: "dynamic_pdf",
    label: "Dynamic PDF",
    desc: "Generate a unique PDF per recipient from a template",
    icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6",
  },
];

export default function JobModeSelector({ currentMode, onModeChange, disabled }: JobModeSelectorProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [pendingMode, setPendingMode] = useState<string | null>(null);

  async function handleSelect(mode: string) {
    if (mode === currentMode || disabled) return;

    if (mode === "static_attachment") {
      setPendingMode(mode);
      fileRef.current?.click();
      return;
    }

    setLoading(mode);
    try {
      await onModeChange(mode);
    } finally {
      setLoading(null);
    }
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !pendingMode) return;

    setLoading(pendingMode);
    try {
      await onModeChange(pendingMode, file);
    } finally {
      setLoading(null);
      setPendingMode(null);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Job Mode</h3>
      <p className="text-xs text-gray-500 mb-4">Choose how emails are sent for this job.</p>

      <input type="file" ref={fileRef} onChange={handleFileSelected} className="hidden" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {MODES.map((mode) => {
          const isActive = currentMode === mode.key;
          const isLoading = loading === mode.key;
          return (
            <button
              key={mode.key}
              onClick={() => handleSelect(mode.key)}
              disabled={disabled || isLoading}
              className={`text-left p-4 rounded-xl border-2 transition-all disabled:opacity-50 ${
                isActive
                  ? "border-green-700 bg-green-50"
                  : "border-gray-100 hover:border-gray-200"
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? "bg-green-800" : "bg-gray-100"}`}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={isActive ? "white" : "#6b7280"} strokeWidth="2">
                    <path d={mode.icon} />
                  </svg>
                </div>
                <span className="text-sm font-semibold text-gray-900">
                  {isLoading ? "Setting..." : mode.label}
                </span>
              </div>
              <p className="text-xs text-gray-500">{mode.desc}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
