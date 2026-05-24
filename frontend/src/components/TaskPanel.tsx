"use client";

/**
 * Self-contained panel for a single task (pdfs, emails, sms, photos).
 * Each panel manages its own polling via GET /jobs/{id}/{task}/status.
 */

import { useEffect, useState, useCallback, useRef } from "react";
import {
  startPdfs,
  startEmails,
  startSms,
  startPhotos,
  pauseTask,
  resumeTask,
  getPdfDownloadUrl,
  downloadFile,
  TaskStatus,
} from "@/lib/api";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

// Base URL for direct fetch calls (polling endpoint)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Types ──────────────────────────────────────────────────────────────────

interface TaskPanelProps {
  jobId: string;
  taskKey: "pdfs" | "emails" | "sms" | "photos";
  initialTask: TaskStatus;   // Passed from parent's job data
  canStart: boolean;          // Whether prerequisites are met (e.g. template attached for PDFs)
  isTerminal: boolean;        // Job is cancelled/failed — no actions allowed
}

// ─── Constants ──────────────────────────────────────────────────────────────

/** Display metadata for each task type — label, SVG icon path, and start button text */
const TASK_META: Record<string, { label: string; icon: string; startLabel: string }> = {
  pdfs: { label: "PDF Generation", icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6", startLabel: "Generate PDFs" },
  emails: { label: "Email Sending", icon: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2ZM22 6l-10 7L2 6", startLabel: "Send Emails" },
  sms: { label: "SMS Sending", icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z", startLabel: "Send SMS" },
  photos: { label: "Photo Download", icon: "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2zM12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z", startLabel: "Download Photos" },
};

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Map task status string to Tailwind badge classes */
function statusColor(status: string) {
  const map: Record<string, string> = {
    created: "bg-blue-100 text-blue-700",
    running: "bg-yellow-100 text-yellow-700",
    complete: "bg-green-100 text-green-700",
    completed: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
    failed: "bg-red-100 text-red-700",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}

/**
 * Fetch the latest status for a single task from the lightweight endpoint.
 * This does NOT reload the entire job — just one task's progress/status.
 */
async function fetchTaskStatus(jobId: string, taskKey: string): Promise<TaskStatus> {
  const token = typeof window !== "undefined" ? localStorage.getItem("vp_token") : null;
  const res = await fetch(`${API_BASE}/jobs/${jobId}/${taskKey}/status`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) throw new Error("Failed to fetch status");

  return res.json();
}

// ─── Component ──────────────────────────────────────────────────────────────

export default function TaskPanel({ jobId, taskKey, initialTask, canStart, isTerminal }: TaskPanelProps) {
  const { toast } = useToast();

  // ── State ──
  const [task, setTask] = useState<TaskStatus>(initialTask);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const hasStartedRef = useRef(initialTask.status === "running" || initialTask.status === "complete");

  const meta = TASK_META[taskKey];

  // ── SYNC from parent when initialTask changes ──
  useEffect(() => {
    setTask(initialTask);

    if (initialTask.status === "running" || initialTask.status === "complete") {
      hasStartedRef.current = true;
    }
  }, [initialTask.status, initialTask.progress, initialTask.total, initialTask.phase]);

  // ── Derived booleans (computed every render from current task state) ──
  const isRunning = task.status === "running";
  const isPaused = task.phase === "paused";
  const isComplete = task.status === "complete";

  // ── POLLING — self-contained, only this panel re-renders on tick ──
  // Starts when isRunning becomes true, stops when it becomes false.
  // The effect's dependency on `isRunning` means the interval is created/destroyed
  // only when the running state flips — not on every render.
  useEffect(() => {
    if (!isRunning) return;

    const interval = setInterval(async () => {
      try {
        const fresh = await fetchTaskStatus(jobId, taskKey);
        setTask(fresh);

        if (fresh.status !== "running") {
          hasStartedRef.current = true;
        }
      } catch {
        /* ignore — will retry next tick */
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isRunning, jobId, taskKey]);

  // ── ACTION HANDLERS ──

  async function handleStart() {
    setActionLoading("start");
    hasStartedRef.current = true;

    try {
      if (taskKey === "pdfs") await startPdfs(jobId);
      else if (taskKey === "emails") await startEmails(jobId);
      else if (taskKey === "sms") await startSms(jobId);
      else await startPhotos(jobId);

      const fresh = await fetchTaskStatus(jobId, taskKey);
      setTask(fresh);
    } catch (err) {
      toast(friendlyError(err));
      hasStartedRef.current = false;
    } finally {
      setActionLoading(null);
    }
  }

  async function handlePause() {
    setActionLoading("pause");
    try {
      await pauseTask(jobId, taskKey);
      const fresh = await fetchTaskStatus(jobId, taskKey);
      setTask(fresh);
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleResume() {
    setActionLoading("resume");
    try {
      await resumeTask(jobId, taskKey);
      const fresh = await fetchTaskStatus(jobId, taskKey);
      setTask(fresh);
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setActionLoading(null);
    }
  }

  const progressPct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;
  const showStart = canStart && !isRunning && !isComplete && !isTerminal && !hasStartedRef.current;

  // ── JSX ──

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      {/* ── Task header: icon + label + status badge ── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {/* Icon — color changes based on state */}
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isComplete ? "bg-green-50" : isRunning ? "bg-yellow-50" : "bg-gray-50"}`}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isComplete ? "#047857" : isRunning ? "#b45309" : "#6b7280"} strokeWidth="2">
              <path d={meta.icon} />
            </svg>
          </div>
          {/* Label + subtitle */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{meta.label}</h3>
            <p className="text-xs text-gray-500 capitalize">
              {isPaused ? "Paused" : task.status}
              {task.error ? ` — ${task.error}` : ""}
            </p>
          </div>
        </div>
        {/* Status badge (top-right) */}
        <span className={`text-xs font-medium px-2.5 py-1 rounded-lg capitalize ${statusColor(isPaused ? "running" : task.status)}`}>
          {isPaused ? "Paused" : task.status}
        </span>
      </div>

      {/* ── Progress bar — only shown when task is running, paused, or complete ── */}
      {(isRunning || isPaused || isComplete) && task.total > 0 && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
            <span>{task.progress} / {task.total}</span>
            <span>{progressPct}%</span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isComplete ? "bg-green-500" : isPaused ? "bg-yellow-400" : "bg-green-600"
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      {/* ── Stats row — shows counts like "Sent: 5", "Failed: 2" ── */}
      <TaskStats taskKey={taskKey} task={task} />

      {/* ── Action buttons ── */}
      <div className="flex items-center gap-2 mt-4">

        {/* GREEN START BUTTON — only if showStart is true */}
        {showStart && (
          <button
            onClick={handleStart}
            disabled={!!actionLoading}
            className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
          >
            {actionLoading === "start" ? "Starting..." : meta.startLabel}
          </button>
        )}

        {/* PAUSE BUTTON — only while running (not paused) */}
        {isRunning && !isPaused && (
          <button
            onClick={handlePause}
            disabled={!!actionLoading}
            className="flex-1 px-4 py-2 text-sm font-medium text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-xl hover:bg-yellow-100 transition-colors disabled:opacity-50"
          >
            Pause
          </button>
        )}

        {/* RESUME BUTTON — only while paused */}
        {isPaused && (
          <button
            onClick={handleResume}
            disabled={!!actionLoading}
            className="flex-1 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors disabled:opacity-50"
          >
            Resume
          </button>
        )}

        {/* DOWNLOAD ZIP — only for PDFs, only when complete */}
        {taskKey === "pdfs" && isComplete && (
          <button
            onClick={async () => {
              setActionLoading("download");
              try {
                await downloadFile(getPdfDownloadUrl(jobId), `pdfs_${jobId}.zip`);
              } catch (err) {
                toast(friendlyError(err));
              } finally {
                setActionLoading(null);
              }
            }}
            disabled={actionLoading === "download"}
            className="flex-1 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors disabled:opacity-50"
          >
            {actionLoading === "download" ? "Downloading..." : "Download ZIP"}
          </button>
        )}

        {/* DOWNLOAD PARTIAL — for PDFs while running/paused, if some are done */}
        {taskKey === "pdfs" && (isRunning || isPaused) && task.progress > 0 && (
          <button
            onClick={async () => {
              setActionLoading("download-partial");
              try {
                await downloadFile(getPdfDownloadUrl(jobId) + "?partial=true", `pdfs_${jobId}_partial.zip`);
              } catch (err) {
                toast(friendlyError(err));
              } finally {
                setActionLoading(null);
              }
            }}
            disabled={actionLoading === "download-partial"}
            className="flex-1 px-4 py-2 text-sm font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded-xl hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            {actionLoading === "download-partial" ? "Downloading..." : `Download ${task.progress} PDFs so far`}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── TaskStats sub-component ────────────────────────────────────────────────

/**
 * Renders stat counters below the progress bar.
 * Each task type has its own stat fields (e.g. PDFs: generated/filtered,
 * Emails: sent/failed, etc.)
 */
function TaskStats({ taskKey, task }: { taskKey: string; task: TaskStatus }) {
  const stats: { label: string; value: number }[] = [];

  if (taskKey === "pdfs") {
    if (task.pdfs_generated) stats.push({ label: "Generated", value: task.pdfs_generated });
    if (task.filtered_out) stats.push({ label: "Filtered", value: task.filtered_out });
  }
  if (taskKey === "emails") {
    if (task.emails_sent) stats.push({ label: "Sent", value: task.emails_sent });
    if (task.emails_failed) stats.push({ label: "Failed", value: task.emails_failed });
  }
  if (taskKey === "sms") {
    if (task.sms_sent) stats.push({ label: "Sent", value: task.sms_sent });
    if (task.sms_failed) stats.push({ label: "Failed", value: task.sms_failed });
    if (task.sms_skipped) stats.push({ label: "Skipped", value: task.sms_skipped });
  }
  if (taskKey === "photos") {
    if (task.photos_downloaded) stats.push({ label: "Downloaded", value: task.photos_downloaded });
    if (task.photos_failed) stats.push({ label: "Failed", value: task.photos_failed });
  }

  if (stats.length === 0) return null;

  return (
    <div className="flex items-center gap-4">
      {stats.map((s) => (
        <div key={s.label} className="text-center">
          <p className="text-lg font-bold text-gray-900">{s.value}</p>
          <p className="text-xs text-gray-500">{s.label}</p>
        </div>
      ))}
    </div>
  );
}
