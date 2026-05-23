import { parseApiError, parseFetchError } from "@/lib/errors";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("vp_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchAPI(path: string, options?: RequestInit) {
  const authHeaders = getAuthHeaders();

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...authHeaders,
        ...options?.headers,
      },
    });
  } catch (networkErr) {
    // Network failure, DNS error, CORS block, offline, etc.
    throw new Error(parseFetchError(networkErr));
  }

  if (!res.ok) {
    // Auto-logout on 401 (expired/invalid token)
    if (res.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("vp_token");
      localStorage.removeItem("vp_template_chat");
      Object.keys(localStorage).forEach((key) => {
        if (key.startsWith("vp_email_chat_")) localStorage.removeItem(key);
      });
      window.location.href = "/login";
      throw new Error("Your session has expired. Please sign in again.");
    }
    // Parse the backend error into a user-friendly message
    const message = await parseApiError(res);
    throw new Error(message);
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
  owner_id: string | null;
  owner_name: string;
  visibility: string;
  tier_required: string;
  is_own: boolean;
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
  job_mode: string;
  email_subject: string;
  email_body: string;
  sms_body: string;
  tasks: Record<string, TaskStatus>;
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
  const res = await fetchAPI("/upload", { method: "POST", body: form });
  return res.json();
}

export async function generateTemplate(
  parsedContents: Record<string, unknown>[],
  instructions?: string,
  columns?: string[],
): Promise<Record<string, unknown>> {
  return fetchJSON("/generate-template", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parsed_contents: parsedContents, instructions, columns }),
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
  // Backend returns HTML now (not PDF), so create a data URL for iframe
  const html = await res.text();
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  raw_text: string;
  detected_fields: Record<string, unknown>;
}

export async function createJob(file: File): Promise<Job> {
  const form = new FormData();
  form.append("candidate_file", file);
  const res = await fetchAPI("/jobs", { method: "POST", body: form });
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

export async function deleteJob(jobId: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}`, { method: "DELETE" });
}

export async function startPdfs(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/pdfs/generate`, { method: "POST" });
}

export async function startEmails(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/emails/send`, { method: "POST" });
}

export async function startSms(jobId: string): Promise<{ message: string; total: number }> {
  return fetchJSON(`/jobs/${jobId}/sms/send`, { method: "POST" });
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

export async function reuploadData(jobId: string, file: File): Promise<Job> {
  const form = new FormData();
  form.append("candidate_file", file);
  const res = await fetchAPI(`/jobs/${jobId}/data`, { method: "POST", body: form });
  return res.json();
}

export function getPdfDownloadUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/pdfs/download`;
}

export function getReportUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/report`;
}

/** Download a file from an authenticated endpoint and trigger browser download. */
export async function downloadFile(url: string, fallbackFilename: string): Promise<void> {
  const res = await fetch(url, { headers: getAuthHeaders() });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Download failed" }));
    throw new Error(err.detail || "Download failed");
  }
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  // Try to get filename from Content-Disposition header
  const disposition = res.headers.get("content-disposition");
  if (disposition) {
    const match = disposition.match(/filename="?([^";\n]+)"?/);
    if (match) a.download = match[1];
    else a.download = fallbackFilename;
  } else {
    a.download = fallbackFilename;
  }
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(blobUrl);
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


// ── Templates (with ownership) ───────────────────────────────────────

export async function getTemplates(filter: string = "all"): Promise<Template[]> {
  return fetchJSON(`/templates?filter=${filter}`);
}

export async function getTemplate(templateId: string): Promise<Record<string, unknown>> {
  return fetchJSON(`/templates/${templateId}`);
}

export async function deleteTemplate(templateId: string): Promise<{ message: string }> {
  return fetchJSON(`/templates/${templateId}`, { method: "DELETE" });
}

export async function updateTemplateVisibility(
  templateId: string,
  visibility: string,
): Promise<{ message: string; visibility: string }> {
  return fetchJSON(`/templates/${templateId}/visibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visibility }),
  });
}


// ── Billing ──────────────────────────────────────────────────────────

export interface TierInfo {
  name: string;
  price_monthly: number;
  currency: string;
  currency_symbol: string;
  features: string[];
  max_active_jobs: number | null;
  ai_chat_messages: number | null;
  can_publish_templates: boolean;
}

export interface Subscription {
  tier: string;
  status: string;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
  payment_provider: string;
  stripe_customer_id: string | null;
}

export async function getTiers(region?: string): Promise<Record<string, TierInfo>> {
  const params = region ? `?region=${region}` : "";
  return fetchJSON(`/billing/tiers${params}`);
}

export async function getSubscription(): Promise<Subscription> {
  return fetchJSON("/billing/subscription");
}

export async function getUserRegion(): Promise<{ region: string | null; locked: boolean }> {
  return fetchJSON("/billing/region");
}

export async function resetUserRegion(): Promise<{ region: string | null; locked: boolean }> {
  return fetchJSON("/billing/region/reset", { method: "POST" });
}

export async function createCheckout(tier: string): Promise<{ checkout_url: string }> {
  return fetchJSON("/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tier }),
  });
}

export async function createPortalSession(): Promise<{ portal_url: string }> {
  return fetchJSON("/billing/portal", { method: "POST" });
}


// ── Job Mode & Email Content ─────────────────────────────────────────

export async function setJobMode(
  jobId: string,
  mode: string,
  staticAttachment?: File,
): Promise<{ message: string; job_mode: string }> {
  const form = new FormData();
  form.append("mode", mode);
  if (staticAttachment) {
    form.append("static_attachment", staticAttachment);
  }
  const res = await fetchAPI(`/jobs/${jobId}/mode`, { method: "POST", body: form });
  return res.json();
}

export async function setEmailContent(
  jobId: string,
  subject: string,
  body: string,
): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/email-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, body }),
  });
}

export async function generateEmailAI(
  prompt: string,
  columns: string[],
  context?: string,
): Promise<{ subject: string; body: string }> {
  return fetchJSON("/ai-email/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, columns, context: context || "" }),
  });
}


// ── Column Mapping ──────────────────────────────────────────────────

export interface ColumnMapping {
  placeholders: string[];
  columns: string[];
  auto_matched: Record<string, string>;
  unmatched: string[];
}

export async function getColumnMapping(jobId: string): Promise<ColumnMapping> {
  return fetchJSON(`/jobs/${jobId}/column-mapping`);
}

export async function applyColumnMapping(
  jobId: string,
  mapping: Record<string, string>,
): Promise<{ message: string; columns: string[] }> {
  return fetchJSON(`/jobs/${jobId}/column-mapping`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping }),
  });
}


// ── SMS Content ─────────────────────────────────────────────────────

export async function setSmsContent(
  jobId: string,
  body: string,
): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/sms-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
}


// ── Email Provider Status ───────────────────────────────────────────

export interface EmailProviderStatus {
  provider_name: string;
  from_name: string;
  from_email: string;
  is_configured: boolean;
}

export async function getEmailProviderStatus(): Promise<EmailProviderStatus> {
  return fetchJSON("/email-settings");
}
