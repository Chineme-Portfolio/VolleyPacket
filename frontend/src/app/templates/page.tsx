"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import TemplateCard from "@/components/TemplateCard";
import TemplateBuilder from "@/components/TemplateBuilder";
import NewJobModal from "@/components/NewJobModal";
import { getTemplates, Template } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { friendlyError } from "@/lib/errors";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "mine", label: "My Templates" },
  { key: "public", label: "Community" },
  { key: "system", label: "VolleyPacket" },
];

type View = "library" | "create";

export default function TemplatesPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [view, setView] = useState<View>("library");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState("all");
  const [useTemplateId, setUseTemplateId] = useState<string | null>(null);
  const [showNewJob, setShowNewJob] = useState(false);

  function loadTemplates(filter?: string) {
    setLoading(true);
    getTemplates(filter || activeFilter)
      .then(setTemplates)
      .catch((err: unknown) => toast(friendlyError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadTemplates();
  }, [activeFilter]);

  function handleUseTemplate(templateId: string) {
    setUseTemplateId(templateId);
    setShowNewJob(true);
  }

  const tabBtn = (v: View, label: string) => (
    <button
      onClick={() => setView(v)}
      className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
        view === v ? "bg-green-50 text-green-800 border-b-2 border-green-700" : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Templates</h1>
          <p className="text-gray-500 mt-1 text-sm">Browse your library or build a new template.</p>
        </div>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 px-4 sm:px-5 py-2.5 bg-white text-gray-700 text-sm font-medium rounded-xl border border-gray-200 hover:bg-gray-50 transition-colors self-start"
        >
          Dashboard
        </Link>
      </div>

      {/* Top-level tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {tabBtn("library", "Templates")}
        {tabBtn("create", "Create")}
      </div>

      {view === "library" ? (
        <>
          {/* Filter pills + count */}
          <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
            <div className="flex gap-1.5 overflow-x-auto -mx-1 px-1">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setActiveFilter(f.key)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-full transition-colors whitespace-nowrap ${
                    activeFilter === f.key ? "bg-green-700 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <span className="text-sm text-gray-400">
              {templates.length} template{templates.length !== 1 ? "s" : ""}
            </span>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : templates.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                <path d="M14 2v6h6" />
              </svg>
              <p className="mt-3 text-sm">No templates yet</p>
              <button
                onClick={() => setView("create")}
                className="mt-3 px-4 py-2 text-sm font-medium text-white bg-green-800 rounded-xl hover:bg-green-900 transition-colors"
              >
                Create your first template
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {templates.map((t) => (
                <TemplateCard key={t.id} template={t} onUpdate={() => loadTemplates()} onUseTemplate={handleUseTemplate} />
              ))}
            </div>
          )}
        </>
      ) : (
        <TemplateBuilder
          onSaved={() => {
            loadTemplates();
            setView("library");
            toast("Template saved to your library", "success");
          }}
        />
      )}

      {showNewJob && (
        <NewJobModal
          initialTemplateId={useTemplateId ?? undefined}
          onClose={() => {
            setShowNewJob(false);
            setUseTemplateId(null);
          }}
          onCreated={(jobId) => {
            setShowNewJob(false);
            setUseTemplateId(null);
            router.push(`/jobs/${jobId}`);
          }}
        />
      )}
    </div>
  );
}
