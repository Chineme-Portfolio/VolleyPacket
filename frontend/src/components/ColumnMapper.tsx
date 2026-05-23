"use client";

import { useEffect, useState } from "react";
import { getColumnMapping, applyColumnMapping, ColumnMapping } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

interface ColumnMapperProps {
  jobId: string;
  columns: string[];
  onMapped?: () => void;
}

export default function ColumnMapper({ jobId, columns, onMapped }: ColumnMapperProps) {
  const [mapping, setMapping] = useState<ColumnMapping | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [userMapping, setUserMapping] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    setLoading(true);
    // Don't reset confirmed — if user already confirmed, keep it hidden
    getColumnMapping(jobId)
      .then((m) => {
        setMapping(m);
        // Pre-fill with auto-matched values
        const initial: Record<string, string> = { ...m.auto_matched };
        m.unmatched.forEach((ph) => { initial[ph] = ""; });
        setUserMapping(initial);
      })
      .catch((err) => {
        // If no template attached, this will 400 — just hide the component
        if (String(err).includes("No template")) {
          setMapping(null);
        } else {
          setError(friendlyError(err));
        }
      })
      .finally(() => setLoading(false));
  }, [jobId, columns.join(",")]);

  async function handleConfirm() {
    // Only send mappings where column !== placeholder (actual renames needed)
    const toApply: Record<string, string> = {};
    for (const [ph, col] of Object.entries(userMapping)) {
      if (col && col !== ph) {
        toApply[ph] = col;
      }
    }

    setSaving(true);
    setError("");
    try {
      await applyColumnMapping(jobId, toApply);
      setConfirmed(true);
      onMapped?.();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading || !mapping) return null;

  // If everything auto-matched perfectly (all placeholders are already column names), hide
  const allMatched = mapping.unmatched.length === 0 &&
    Object.entries(mapping.auto_matched).every(([ph, col]) => ph === col);
  if (allMatched || confirmed) return null;

  const hasUnmatched = mapping.unmatched.length > 0;
  const unmappedCount = Object.entries(userMapping).filter(([, col]) => !col).length;

  return (
    <div className={`rounded-2xl border shadow-sm p-5 ${hasUnmatched ? "bg-amber-50 border-amber-100" : "bg-white border-gray-100"}`}>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${hasUnmatched ? "bg-amber-100" : "bg-blue-50"}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={hasUnmatched ? "#b45309" : "#2563eb"} strokeWidth="2">
            <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Column Mapping</h3>
          <p className="text-xs text-gray-500">
            {hasUnmatched
              ? `${mapping.unmatched.length} placeholder${mapping.unmatched.length > 1 ? "s" : ""} could not be auto-matched`
              : "Review auto-matched columns before generating PDFs"}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {mapping.placeholders.map((ph) => {
          const isAutoMatched = ph in mapping.auto_matched && mapping.auto_matched[ph] === ph;
          const currentCol = userMapping[ph] || "";

          // Skip placeholders that exactly match a column (no mapping needed)
          if (isAutoMatched) return null;

          return (
            <div key={ph} className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-1 rounded">
                  {`{${ph}}`}
                </span>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" className="flex-shrink-0">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
              <select
                value={currentCol}
                onChange={(e) => setUserMapping((prev) => ({ ...prev, [ph]: e.target.value }))}
                className={`flex-1 px-3 py-2 rounded-xl border text-sm outline-none transition-shadow ${
                  !currentCol
                    ? "border-amber-300 bg-amber-50 text-amber-800"
                    : "border-gray-200 bg-white text-gray-800 focus:ring-2 focus:ring-green-700/20"
                }`}
              >
                <option value="">-- Select column --</option>
                {columns.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-3 mt-4">
        <button
          onClick={handleConfirm}
          disabled={saving || unmappedCount > 0}
          className="px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
        >
          {saving ? "Applying..." : "Confirm Mapping"}
        </button>
        {unmappedCount > 0 && (
          <span className="text-xs text-amber-700">{unmappedCount} unmatched</span>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600 mt-2">{error}</p>
      )}
    </div>
  );
}
