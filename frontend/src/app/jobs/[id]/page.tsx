"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import JobLogViewer from "@/components/JobLogViewer";
import JobModeSelector from "@/components/JobModeSelector";
import EmailComposer from "@/components/EmailComposer";
import SmsComposer from "@/components/SmsComposer";
import ColumnMapper from "@/components/ColumnMapper";
import TemplateSelector from "@/components/TemplateSelector";
import JobTemplateEditor from "@/components/JobTemplateEditor";
import TaskPanel from "@/components/TaskPanel";
import {
  getJob,
  deleteJob,
  reuploadData,
  setJobMode,
  getReportUrl,
  downloadFile,
  getEmailProviderStatus,
  Job,
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

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const jobId = params.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [emailConfigured, setEmailConfigured] = useState<boolean | null>(null);
  const [availableLogs, setAvailableLogs] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadJob = useCallback(async () => {
    try {
      const data = await getJob(jobId);
      setJob(data);
      return data;
    } catch (err) {
      setError(friendlyError(err));
      return null;
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  // Initial load
  useEffect(() => {
    loadJob();
    getEmailProviderStatus()
      .then((status) => setEmailConfigured(status.is_configured))
      .catch(() => setEmailConfigured(false));
  }, [loadJob]);

  // SSE stream for live task updates and log availability
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("vp_token") : null;
    if (!token) return;

    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let abortController = new AbortController();
    let reconnectTimer: ReturnType<typeof setTimeout>;

    async function connect() {
      try {
        const res = await fetch(`${apiBase}/jobs/${jobId}/stream`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: abortController.signal,
        });
        if (!res.ok || !res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(line.slice(6));
              if (event.error) continue;

              setJob((prev) => {
                if (!prev) return prev;
                return { ...prev, status: event.job_status, tasks: event.tasks };
              });
              setAvailableLogs(event.available_logs || []);
            } catch {
              // ignore malformed SSE lines
            }
          }
        }
      } catch (err) {
        if (abortController.signal.aborted) return;
      }
      // Reconnect after 5s on disconnect
      if (!abortController.signal.aborted) {
        reconnectTimer = setTimeout(connect, 5000);
      }
    }

    connect();

    return () => {
      abortController.abort();
      clearTimeout(reconnectTimer);
    };
  }, [jobId]);

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
            {job.candidate_count} recipients
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

      {/* Email provider warning */}
      {emailConfigured === false && !isTerminal && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-amber-50 border border-amber-100 rounded-2xl px-4 sm:px-5 py-4 mb-6">
          <div className="flex items-center gap-3">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#b45309" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <path d="M12 9v4M12 17h.01" />
            </svg>
            <div>
              <p className="text-sm font-medium text-amber-900">Email provider not configured</p>
              <p className="text-xs text-amber-700 mt-0.5">Set up an email provider before sending emails.</p>
            </div>
          </div>
          <Link
            href="/settings/email"
            className="px-4 py-2 text-sm font-medium text-amber-800 bg-white border border-amber-200 rounded-xl hover:bg-amber-50 transition-colors self-start sm:self-auto flex-shrink-0"
          >
            Configure Email
          </Link>
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

      {/* Column mapping (shows only when template has unmatched placeholders) */}
      {!isTerminal && job.template_id && (
        <div className="mb-6">
          <ColumnMapper
            jobId={jobId}
            columns={job.columns}
            onMapped={() => loadJob()}
          />
        </div>
      )}

      {/* Template selector */}
      {!isTerminal && (
        <div className="mb-6">
          <TemplateSelector
            jobId={jobId}
            currentTemplateId={job.template_id}
            disabled={hasRunning}
            onChanged={() => loadJob()}
          />
        </div>
      )}

      {/* In-job template editor (dynamic PDF jobs only — the template is what gets rendered) */}
      {!isTerminal && job.template_id && jobMode === "dynamic_pdf" && (
        <div className="mb-6">
          <JobTemplateEditor
            jobId={jobId}
            columns={job.columns}
            templateId={job.template_id}
            disabled={hasRunning}
            onChanged={() => loadJob()}
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

      {/* SMS composer */}
      {!isTerminal && (
        <div className="mb-6">
          <SmsComposer
            jobId={jobId}
            columns={job.columns}
            initialBody={job.sms_body || ""}
            onSaved={() => loadJob()}
          />
        </div>
      )}

      {/* Task panels — each manages its own polling and state */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        {(["pdfs", "emails", "sms", "photos"] as const).map((taskKey) => {
          const task = job.tasks?.[taskKey];
          if (!task) return null;
          if (taskKey === "pdfs" && jobMode !== "dynamic_pdf") return null;

          let canStart = false;
          if (taskKey === "pdfs") canStart = !!job.template_id;
          if (taskKey === "emails") canStart = jobMode !== "dynamic_pdf" || job.tasks?.pdfs?.status === "complete";
          if (taskKey === "sms") canStart = true;
          if (taskKey === "photos") canStart = true;

          return (
            <TaskPanel
              key={taskKey}
              jobId={jobId}
              taskKey={taskKey}
              initialTask={task}
              canStart={canStart}
              isTerminal={isTerminal}
            />
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
            <button
              onClick={() => doAction("download-report", () => downloadFile(getReportUrl(jobId), `report_${jobId}.xlsx`))}
              disabled={actionLoading === "download-report"}
              className="px-5 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors text-center flex-shrink-0 disabled:opacity-50"
            >
              {actionLoading === "download-report" ? "Downloading..." : "Download Report"}
            </button>
          </div>
        </div>
      )}

      {/* Job Logs */}
      <div className="mt-6">
        <JobLogViewer jobId={jobId} availableLogs={availableLogs} />
      </div>
    </div>
  );
}
