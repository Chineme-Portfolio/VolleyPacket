"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { getJobLogs, getJobLog, downloadJobLog, LogMeta, LogData } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

interface JobLogViewerProps {
  jobId: string;
  availableLogs: string[];
}

export default function JobLogViewer({ jobId, availableLogs }: JobLogViewerProps) {
  const { toast } = useToast();
  const [tabs, setTabs] = useState<LogMeta[]>([]);
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const [logData, setLogData] = useState<LogData | null>(null);
  const [loading, setLoading] = useState(true);
  const [logLoading, setLogLoading] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;
  const prevLogsRef = useRef<string>("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const key = availableLogs.slice().sort().join(",");
    if (key === prevLogsRef.current && tabs.length > 0) return;
    prevLogsRef.current = key;

    if (availableLogs.length === 0) {
      setLoading(false);
      return;
    }

    getJobLogs(jobId)
      .then((logs) => {
        setTabs(logs);
        if (logs.length > 0 && !activeTab) setActiveTab(logs[0].key);
      })
      .catch((err: unknown) => toast(friendlyError(err)))
      .finally(() => setLoading(false));
  }, [jobId, availableLogs]);

  const loadLog = useCallback(
    async (key: string, offset: number) => {
      setLogLoading(true);
      try {
        const data = await getJobLog(jobId, key, PAGE_SIZE, offset);
        setLogData(data);
      } catch (err) {
        toast(friendlyError(err));
        setLogData(null);
      } finally {
        setLogLoading(false);
      }
    },
    [jobId]
  );

  useEffect(() => {
    if (activeTab) {
      setPage(0);
      loadLog(activeTab, 0);
    }
  }, [activeTab, loadLog]);

  function handlePageChange(newPage: number) {
    setPage(newPage);
    if (activeTab) loadLog(activeTab, newPage * PAGE_SIZE);
  }

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
          Loading logs...
        </div>
      </div>
    );
  }

  if (tabs.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Job Logs</h3>
        <p className="text-sm text-gray-400">No logs generated for this job yet.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      {/* Header + Tabs */}
      <div className="px-6 pt-5 pb-0">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Job Logs</h3>
          {activeTab && (
            <button
              onClick={async () => {
                setDownloading(true);
                try {
                  await downloadJobLog(jobId, activeTab);
                } catch (err) {
                  toast(friendlyError(err));
                } finally {
                  setDownloading(false);
                }
              }}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-sm font-medium text-green-800 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors disabled:opacity-50"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              {downloading ? "Downloading..." : "Download"}
            </button>
          )}
        </div>
        <div className="flex gap-1 border-b border-gray-100">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab.key
                  ? "bg-green-50 text-green-800 border-b-2 border-green-700"
                  : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        {logLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-6 h-6 border-2 border-green-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : logData && logData.rows.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {logData.headers.map((h) => (
                  <th
                    key={h}
                    className="text-left text-xs font-semibold text-gray-400 uppercase tracking-wider px-4 py-3 whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logData.rows.map((row, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                  {logData.headers.map((h) => (
                    <td key={h} className="px-4 py-2.5 text-gray-700 whitespace-nowrap max-w-[300px] truncate">
                      <CellValue header={h} value={row[h]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
            No log entries
          </div>
        )}
      </div>

      {/* Pagination */}
      {logData && logData.rows.length > 0 && (
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + logData.rows.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handlePageChange(page - 1)}
              disabled={page === 0}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => handlePageChange(page + 1)}
              disabled={logData.rows.length < PAGE_SIZE}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CellValue({ header, value }: { header: string; value: string }) {
  if (!value || value === "None") {
    return <span className="text-gray-300">—</span>;
  }

  const lower = header.toLowerCase();
  const valLower = value.toLowerCase();

  if (lower.includes("sent") || lower.includes("downloaded") || lower === "pdfgenerated") {
    if (valLower === "true") {
      return <span className="inline-flex items-center gap-1 text-green-700 font-medium">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
        Yes
      </span>;
    }
    if (valLower === "false") {
      return <span className="inline-flex items-center gap-1 text-red-600 font-medium">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12"/></svg>
        No
      </span>;
    }
  }

  if (lower === "error" && value) {
    return <span className="text-red-600">{value}</span>;
  }

  return <>{value}</>;
}
