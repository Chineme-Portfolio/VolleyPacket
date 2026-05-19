const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("vp_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchAPI(path: string, options?: RequestInit) {
  const authHeaders = getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...authHeaders,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res;
}

export async function fetchJSON<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetchAPI(path, options);
  return res.json();
}

export interface Template {
  id: string;
  name: string;
  description: string;
}

export interface TaskStatus {
  status: string;
  phase: string;
  progress: number;
  total: number;
  error: string | null;
  pdfs_generated: number;
  emails_sent: number;
  emails_failed: number;
  sms_sent: number;
  sms_failed: number;
  sms_skipped: number;
  photos_downloaded: number;
  photos_failed: number;
  filtered_out: number;
}

export interface Job {
  job_id: string;
  status: string;
  candidate_file: string | null;
  candidate_count: number;
  columns: string[];
  template_id: string | null;
  is_allocated: boolean;
  tasks: Record<string, TaskStatus>;
}

export async function getTemplates(): Promise<Template[]> {
  return fetchJSON("/templates");
}

export async function getJobs(): Promise<Job[]> {
  return fetchJSON("/jobs");
}

export async function getJob(jobId: string): Promise<Job> {
  return fetchJSON(`/jobs/${jobId}`);
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function generateTemplate(
  parsedContent: Record<string, unknown>,
  instructions?: string
): Promise<Record<string, unknown>> {
  return fetchJSON("/generate-template", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parsed_content: parsedContent, instructions }),
  });
}

export async function saveTemplate(
  template: Record<string, unknown>
): Promise<{ message: string; id: string }> {
  return fetchJSON("/templates/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template }),
  });
}

export async function previewGeneratedTemplate(
  template: Record<string, unknown>
): Promise<string> {
  const res = await fetchAPI("/generate-template/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(template),
  });
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  raw_text: string;
  detected_fields: Record<string, unknown>;
}

export async function createJob(file: File, isAllocated = false): Promise<Job> {
  const form = new FormData();
  form.append("candidate_file", file);
  form.append("is_allocated", String(isAllocated));
  const res = await fetch(`${API_BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Failed to create job");
  }
  return res.json();
}

export async function attachTemplate(
  jobId: string,
  templateId: string
): Promise<{ message: string; template_id: string }> {
  return fetchJSON(`/jobs/${jobId}/template`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ template_id: templateId }),
  });
}

export async function cancelJob(jobId: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export async function allocateJob(jobId: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/allocate`, { method: "POST" });
}

export async function startPdfs(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/pdfs/generate`, { method: "POST" });
}

export async function startEmails(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/emails/send`, { method: "POST" });
}

export async function startSms(jobId: string, detailed = false): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/sms/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ detailed }),
  });
}

export async function startPhotos(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/photos/download`, { method: "POST" });
}

export async function pauseTask(jobId: string, task: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/${task}/pause`, { method: "POST" });
}

export async function resumeTask(jobId: string, task: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/${task}/resume`, { method: "POST" });
}

export async function reuploadData(jobId: string, file: File, isAllocated = false): Promise<Job> {
  const form = new FormData();
  form.append("candidate_file", file);
  form.append("is_allocated", String(isAllocated));
  const res = await fetch(`${API_BASE}/jobs/${jobId}/data`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Re-upload failed");
  }
  return res.json();
}

export function getPdfDownloadUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/pdfs/download`;
}

export function getReportUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/report`;
}

export interface LogMeta {
  key: string;
  label: string;
  filename: string;
  size: number;
}

export interface LogData {
  key: string;
  label: string;
  headers: string[];
  rows: Record<string, string>[];
  offset: number;
  limit: number;
}

export async function getJobLogs(jobId: string): Promise<LogMeta[]> {
  return fetchJSON(`/jobs/${jobId}/logs`);
}

export async function getJobLog(
  jobId: string,
  logKey: string,
  limit = 100,
  offset = 0
): Promise<LogData> {
  return fetchJSON(`/jobs/${jobId}/logs/${logKey}?limit=${limit}&offset=${offset}`);
}
