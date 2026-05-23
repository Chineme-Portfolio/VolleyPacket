"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import JobLogViewer from "@/components/JobLogViewer";
import JobModeSelector from "@/components/JobModeSelector";
import EmailComposer from "@/components/EmailComposer";
import {
  getJob,
  cancelJob,
  deleteJob,
  allocateJob,
  startPdfs,
  startEmails,
  startSms,
  startPhotos,
  pauseTask,
  resumeTask,
  reuploadData,
  setJobMode,
  getPdfDownloadUrl,
  getReportUrl,
  Job,
  TaskStatus,
} from "@/lib/api";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

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

const TASK_META: Record<string, { label: string; icon: string; startLabel: string }> = {
  pdfs: { label: "PDF Generation", icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6", startLabel: "Generate PDFs" },
  emails: { label: "Email Sending", icon: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2ZM22 6l-10 7L2 6", startLabel: "Send Emails" },
  sms: { label: "SMS Sending", icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z", startLabel: "Send SMS" },
  photos: { label: "Photo Download", icon: "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2zM12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z", startLabel: "Download Photos" },
};

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const jobId = params.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [smsDetailed, setSmsDetailed] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollActiveRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadJob = useCallback(async () => {
    try {
      const data = await getJob(jobId);
      setJob(data);

      // Manage polling based on whether any task is running
      const hasRunning = Object.values(data.tasks || {}).some((t) => t.status === "running");
      if (hasRunning && !pollActiveRef.current) {
        pollActiveRef.current = true;
        pollRef.current = setInterval(async () => {
          try {
            const fresh = await getJob(jobId);
            setJob(fresh);
            const stillRunning = Object.values(fresh.tasks || {}).some((t) => t.status === "running");
            if (!stillRunning) {
              clearInterval(pollRef.current!);
              pollRef.current = null;
              pollActiveRef.current = false;
            }
          } catch { /* ignore poll errors */ }
        }, 2000);
      } else if (!hasRunning && pollActiveRef.current) {
        clearInterval(pollRef.current!);
        pollRef.current = null;
        pollActiveRef.current = false;
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadJob();
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        pollActiveRef.current = false;
      }
    };
  }, [loadJob]);

  async function doAction(key: string, fn: () => Promise<unknown>) {
    setActionLoading(key);
    setError("");
    try {
      await fn();
      await loadJob();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReupload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    await doAction("reupload", () => reuploadData(jobId, file));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400">
        <p className="text-lg font-medium">Job not found</p>
        <Link href="/jobs" className="mt-3 text-sm text-green-700 hover:text-green-800 font-medium">
          Back to Jobs
        </Link>
      </div>
    );
  }

  const isTerminal = job.status === "cancelled" || job.status === "failed";
  const jobMode = job.job_mode || "dynamic_pdf";
  const hasExamDate = job.columns?.includes("ExamDate");
  const canAllocate = hasExamDate && !job.is_allocated && !isTerminal;
  const canStartPdfs = job.template_id && job.tasks?.pdfs?.status !== "running";
  const pdfsComplete = job.tasks?.pdfs?.status === "complete";
  const emailsComplete = job.tasks?.emails?.status === "complete";
  const hasRunning = Object.values(job.tasks || {}).some((t) => t.status === "running");

  return (
    <div>
      {/* Back + Header */}
      <Link href="/jobs" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        Back to Jobs
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 truncate">{job.candidate_file || "Untitled Job"}</h1>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-lg capitalize flex-shrink-0 ${statusColor(job.status)}`}>
              {job.status}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {job.candidate_count} recipients{job.is_allocated ? " · Allocated" : ""}
          </p>
          <p className="text-xs text-gray-400 mt-0.5 truncate">ID: {job.job_id}</p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Re-upload */}
          <input type="file" ref={fileInputRef} onChange={handleReupload} accept=".xlsx,.xls,.csv" className="hidden" />
          {!isTerminal && (
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={actionLoading === "reupload"}
              className="px-3 sm:px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Re-upload
            </button>
          )}

          {/* Cancel */}
          {!isTerminal && (
            <button
              onClick={() => doAction("cancel", () => cancelJob(jobId))}
              disabled={actionLoading === "cancel"}
              className="px-3 sm:px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {actionLoading === "cancel" ? "Cancelling..." : "Cancel"}
            </button>
          )}

          {/* Delete */}
          <button
            onClick={async () => {
              if (!confirm("Delete this job and all its files? This cannot be undone.")) return;
              await doAction("delete", async () => {
                await deleteJob(jobId);
                router.push("/jobs");
              });
            }}
            disabled={actionLoading === "delete" || hasRunning}
            className="px-3 sm:px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50"
            title={hasRunning ? "Stop running tasks before deleting" : "Delete job and all files"}
          >
            {actionLoading === "delete" ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 px-4 py-3 rounded-xl mb-6">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
          {error}
        </div>
      )}

      {/* Allocate banner */}
      {canAllocate && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-blue-50 border border-blue-100 rounded-2xl px-4 sm:px-5 py-4 mb-6">
          <div>
            <p className="text-sm font-medium text-blue-900">Data needs allocation</p>
            <p className="text-xs text-blue-700 mt-0.5">Assign combinations and time slots to recipients before generating PDFs.</p>
          </div>
          <button
            onClick={() => doAction("allocate", () => allocateJob(jobId))}
            disabled={actionLoading === "allocate"}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 self-start sm:self-auto flex-shrink-0"
          >
            {actionLoading === "allocate" ? "Allocating..." : "Allocate Now"}
          </button>
        </div>
      )}

      {/* Job mode selector */}
      {!isTerminal && (
        <div className="mb-6">
          <JobModeSelector
            currentMode={jobMode}
            onModeChange={async (mode, file) => {
              await setJobMode(jobId, mode, file);
              await loadJob();
            }}
            disabled={hasRunning}
          />
        </div>
      )}

      {/* Email composer */}
      {!isTerminal && (
        <div className="mb-6">
          <EmailComposer
            jobId={jobId}
            columns={job.columns}
            initialSubject={job.email_subject || ""}
            initialBody={job.email_body || ""}
            onSaved={() => loadJob()}
          />
        </div>
      )}

      {/* Task panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        {(["pdfs", "emails", "sms", "photos"] as const).map((taskKey) => {
          const task: TaskStatus | undefined = job.tasks?.[taskKey];
          const meta = TASK_META[taskKey];
          if (!task) return null;

          const isRunning = task.status === "running";
          const isPaused = task.phase === "paused";
          const isComplete = task.status === "complete";
          const progressPct = task.total > 0 ? Math.round((task.progress / task.total) * 100) : 0;

          // Skip PDF panel if not in dynamic_pdf mode
          if (taskKey === "pdfs" && jobMode !== "dynamic_pdf") return null;

          let canStart = false;
          if (taskKey === "pdfs") canStart = !!canStartPdfs && !isRunning && !isComplete;
          if (taskKey === "emails") {
            if (jobMode === "dynamic_pdf") {
              canStart = !!pdfsComplete && !isRunning && !isComplete;
            } else {
              // email_only or static_attachment: can start immediately
              canStart = !isRunning && !isComplete;
            }
          }
          if (taskKey === "sms") canStart = !isRunning && !isComplete;
          if (taskKey === "photos") canStart = !isRunning && !isComplete;

          return (
            <div key={taskKey} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
              {/* Task header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isComplete ? "bg-green-50" : isRunning ? "bg-yellow-50" : "bg-gray-50"}`}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isComplete ? "#047857" : isRunning ? "#b45309" : "#6b7280"} strokeWidth="2">
                      <path d={meta.icon} />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">{meta.label}</h3>
                    <p className="text-xs text-gray-500 capitalize">{isPaused ? "Paused" : task.status}{task.error ? ` — ${task.error}` : ""}</p>
                  </div>
                </div>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-lg capitalize ${statusColor(isPaused ? "running" : task.status)}`}>
                  {isPaused ? "Paused" : task.status}
                </span>
              </div>

              {/* Progress bar */}
              {(isRunning || isPaused || isComplete) && task.total > 0 && (
                <div className="mb-4">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                    <span>{task.progress} / {task.total}</span>
                    <span>{progressPct}%</span>
                  </div>
                  <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${isComplete ? "bg-green-500" : isPaused ? "bg-yellow-400" : "bg-green-600"}`}
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Stats */}
              <TaskStats taskKey={taskKey} task={task} />

              {/* Actions */}
              <div className="flex items-center gap-2 mt-4">
                {canStart && !isTerminal && (
                  <>
                    {taskKey === "sms" && (
                      <label className="flex items-center gap-1.5 text-xs text-gray-600 mr-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={smsDetailed}
                          onChange={(e) => setSmsDetailed(e.target.checked)}
                          className="w-3.5 h-3.5 rounded border-gray-300 text-green-700"
                        />
                        Detailed
                      </label>
                    )}
                    <button
                      onClick={() => doAction(`start-${taskKey}`, () => {
                        if (taskKey === "pdfs") return startPdfs(jobId);
                        if (taskKey === "emails") return startEmails(jobId);
                        if (taskKey === "sms") return startSms(jobId, smsDetailed);
                        return startPhotos(jobId);
                      })}
                      disabled={!!actionLoading}
                      className="flex-1 px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === `start-${taskKey}` ? "Starting..." : meta.startLabel}
                    </button>
                  </>
                )}

                {isRunning && !isPaused && (
                  <button
                    onClick={() => doAction(`pause-${taskKey}`, () => pauseTask(jobId, taskKey))}
                    disabled={!!actionLoading}
                    className="flex-1 px-4 py-2 text-sm font-medium text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-xl hover:bg-yellow-100 transition-colors disabled:opacity-50"
                  >
                    Pause
                  </button>
                )}

                {isPaused && (
                  <button
                    onClick={() => doAction(`resume-${taskKey}`, () => resumeTask(jobId, taskKey))}
                    disabled={!!actionLoading}
                    className="flex-1 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors disabled:opacity-50"
                  >
                    Resume
                  </button>
                )}

                {taskKey === "pdfs" && isComplete && (
                  <a
                    href={getPdfDownloadUrl(jobId)}
                    className="flex-1 text-center px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors"
                  >
                    Download ZIP
                  </a>
                )}

                {taskKey === "pdfs" && (isRunning || isPaused) && task.progress > 0 && (
                  <a
                    href={getPdfDownloadUrl(jobId) + "?partial=true"}
                    className="flex-1 text-center px-4 py-2 text-sm font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    Download {task.progress} PDFs so far
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Report section */}
      {emailsComplete && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                  <path d="M14 2v6h6" />
                  <path d="M16 13H8M16 17H8M10 9H8" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Delivery Report</h3>
                <p className="text-xs text-gray-500">Excel report with sent, missing, bad emails, and failed rows</p>
              </div>
            </div>
            <a
              href={getReportUrl(jobId)}
              className="px-5 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors text-center flex-shrink-0"
            >
              Download Report
            </a>
          </div>
        </div>
      )}

      {/* Job Logs */}
      <div className="mt-6">
        <JobLogViewer jobId={jobId} />
      </div>
    </div>
  );
}

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
