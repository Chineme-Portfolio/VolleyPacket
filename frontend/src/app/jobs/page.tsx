"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getJobs, cancelJob, Job } from "@/lib/api";
import { statusBadge } from "@/lib/status";
import NewJobModal from "@/components/NewJobModal";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

function taskSummary(job: Job): string {
  const parts: string[] = [];
  const t = job.tasks;
  if (t?.pdfs?.pdfs_generated) parts.push(`${t.pdfs.pdfs_generated} PDFs`);
  if (t?.emails?.emails_sent) parts.push(`${t.emails.emails_sent} emails`);
  if (t?.sms?.sms_sent) parts.push(`${t.sms.sms_sent} SMS`);
  if (t?.photos?.photos_downloaded) parts.push(`${t.photos.photos_downloaded} photos`);
  return parts.length > 0 ? parts.join(" · ") : "No tasks run";
}

export default function JobsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewJob, setShowNewJob] = useState(false);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      const data = await getJobs();
      setJobs(data);
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleCancel(jobId: string) {
    setCancellingId(jobId);
    try {
      await cancelJob(jobId);
      await loadJobs();
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setCancellingId(null);
    }
  }

  const running = jobs.filter(
    (j) => j.status === "running" || Object.values(j.tasks || {}).some((t) => t.status === "running")
  ).length;
  const completed = jobs.filter((j) => j.status === "complete" || j.status === "completed").length;

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Jobs</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {jobs.length} total · {running} running · {completed} completed
          </p>
        </div>
        <button
          onClick={() => setShowNewJob(true)}
          className="flex items-center gap-2 px-4 sm:px-5 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors self-start"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New Job
        </button>
      </div>

      {/* Jobs list */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M12 8v8M8 12h8" />
            </svg>
            <p className="mt-4 text-sm font-medium">No jobs yet</p>
            <p className="text-xs mt-1">Create your first job to get started</p>
            <button
              onClick={() => setShowNewJob(true)}
              className="mt-4 px-5 py-2 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors"
            >
              Create Job
            </button>
          </div>
        ) : (
          <>
          {/* Mobile: card layout */}
          <div className="lg:hidden divide-y divide-gray-100">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="p-4 hover:bg-gray-50/50 transition-colors cursor-pointer"
                onClick={() => router.push(`/jobs/${job.job_id}`)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{job.candidate_file || "Untitled"}</p>
                      <p className="text-xs text-gray-400 truncate">{job.candidate_count} candidates</p>
                    </div>
                  </div>
                  <span className={`text-xs font-medium px-2.5 py-1 rounded-lg capitalize flex-shrink-0 ${statusBadge(job.status)}`}>
                    {job.status}
                  </span>
                </div>
                <div className="mt-2 ml-12 flex items-center justify-between">
                  <p className="text-xs text-gray-500">{taskSummary(job)}</p>
                  {(job.status === "created" || job.status === "running") && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCancel(job.job_id);
                      }}
                      disabled={cancellingId === job.job_id}
                      className="text-xs font-medium text-red-600 hover:text-red-700 px-2 py-1 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
                    >
                      {cancellingId === job.job_id ? "..." : "Cancel"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop: table layout */}
          <table className="w-full hidden lg:table">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">File</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">Candidates</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">Template</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">Progress</th>
                <th className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">Status</th>
                <th className="text-right text-xs font-semibold text-gray-400 uppercase tracking-wider px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.job_id}
                  className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors cursor-pointer"
                  onClick={() => router.push(`/jobs/${job.job_id}`)}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-green-50 flex items-center justify-center flex-shrink-0">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                          <path d="M14 2v6h6" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{job.candidate_file || "Untitled"}</p>
                        <p className="text-xs text-gray-400">{job.job_id}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700">{job.candidate_count}</td>
                  <td className="px-6 py-4 text-sm text-gray-700">{job.template_id || "—"}</td>
                  <td className="px-6 py-4 text-xs text-gray-500">{taskSummary(job)}</td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-lg capitalize ${statusBadge(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {(job.status === "created" || job.status === "running") && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancel(job.job_id);
                        }}
                        disabled={cancellingId === job.job_id}
                        className="text-xs font-medium text-red-600 hover:text-red-700 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
                      >
                        {cancellingId === job.job_id ? "Cancelling..." : "Cancel"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </>
        )}
      </div>

      {/* New Job Modal */}
      {showNewJob && (
        <NewJobModal
          onClose={() => setShowNewJob(false)}
          onCreated={(jobId) => {
            setShowNewJob(false);
            router.push(`/jobs/${jobId}`);
          }}
        />
      )}
    </div>
  );
}
