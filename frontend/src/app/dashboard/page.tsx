"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import StatCard from "@/components/StatCard";
import TemplateCard from "@/components/TemplateCard";
import RecentJobs from "@/components/RecentJobs";
import NewJobModal from "@/components/NewJobModal";
import { getTemplates, getJobs, Template, Job } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

export default function Dashboard() {
  const router = useRouter();
  const { toast } = useToast();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewJob, setShowNewJob] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [t, j] = await Promise.all([getTemplates(), getJobs()]);
        setTemplates(t);
        setJobs(j);
      } catch (err) {
        toast(friendlyError(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const totalJobs = jobs.length;
  const runningJobs = jobs.filter((j) => j.status === "running" || j.tasks?.emails?.status === "running" || j.tasks?.pdfs?.status === "running").length;
  const completedJobs = jobs.filter((j) => j.status === "complete" || j.status === "completed").length;
  const failedJobs = jobs.filter((j) => j.status === "failed" || j.status === "cancelled").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1 text-sm">Generate, send, and track exam invitations with ease.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowNewJob(true)}
            className="flex items-center gap-2 px-4 sm:px-5 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New Job
          </button>
          <Link
            href="/templates"
            className="flex items-center gap-2 px-4 sm:px-5 py-2.5 bg-white text-gray-700 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            Templates
          </Link>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <StatCard title="Total Jobs" value={totalJobs} subtitle="All time" highlighted />
        <StatCard title="Completed" value={completedJobs} subtitle="Successfully finished" />
        <StatCard title="Running" value={runningJobs} subtitle="Currently active" />
        <StatCard title="Failed / Cancelled" value={failedJobs} />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Jobs — spans 2 cols */}
        <div className="lg:col-span-2">
          <RecentJobs jobs={jobs} />
        </div>

        {/* Templates */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Templates</h2>
            <Link href="/templates" className="text-sm text-green-700 font-medium hover:text-green-800">
              View All
            </Link>
          </div>

          {templates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                <path d="M14 2v6h6" />
              </svg>
              <p className="mt-3 text-sm">No templates</p>
            </div>
          ) : (
            <div className="space-y-4">
              {templates.map((t) => (
                <TemplateCard key={t.id} template={t} />
              ))}
            </div>
          )}
        </div>
      </div>

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
