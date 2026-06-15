"use client";

import { useState } from "react";
import { statusBadge, statusLabel, MANUAL_STATUSES } from "@/lib/status";
import { setJobStatus } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

interface JobStatusControlProps {
  job: { job_id: string; status: string; status_manual?: string | null };
  onChanged?: () => void;
  className?: string;
}

/** A clickable status badge that lets the user manually set a job's status (or revert to Automatic). */
export default function JobStatusControl({ job, onChanged, className = "" }: JobStatusControlProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const isManual = !!job.status_manual;

  async function pick(value: string | null) {
    setOpen(false);
    if (value === (job.status_manual ?? null)) return; // no change
    setSaving(true);
    try {
      await setJobStatus(job.job_id, value);
      toast(value ? `Status set to ${statusLabel(value)}` : "Status set to automatic", "success");
      onChanged?.();
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`relative inline-block text-left ${className}`}>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); }}
        disabled={saving}
        title={isManual ? "Status set manually — click to change" : "Click to set status"}
        className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg hover:opacity-90 disabled:opacity-50 ${statusBadge(job.status)}`}
      >
        {isManual && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />}
        {saving ? "…" : statusLabel(job.status)}
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <>
          {/* click-away backdrop */}
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(false); }}
            className="fixed inset-0 z-10 cursor-default"
          />
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute right-0 mt-1 z-20 bg-white rounded-xl shadow-lg border border-gray-100 py-1 min-w-[170px]"
          >
            <button
              type="button"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); pick(null); }}
              className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 ${!isManual ? "text-green-700 font-semibold" : "text-gray-700"}`}
            >
              {!isManual ? "✓ " : ""}Automatic
            </button>
            <div className="my-1 border-t border-gray-100" />
            {MANUAL_STATUSES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); pick(s.value); }}
                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-50 flex items-center gap-2 ${job.status_manual === s.value ? "text-green-700 font-semibold" : "text-gray-700"}`}
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusBadge(s.value).split(" ")[0]}`} />
                {s.label}
                {job.status_manual === s.value ? <span className="ml-auto">✓</span> : null}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
