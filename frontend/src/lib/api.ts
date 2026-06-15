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
  owner_avatar: string | null;
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
  status_manual?: string | null; // non-null = user-set override (vs auto-derived)
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

/** Manually set a job's status, or pass null to revert to automatic (derived from tasks). */
export async function setJobStatus(jobId: string, status: string | null): Promise<{ status: string | null }> {
  return fetchJSON(`/jobs/${jobId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
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

/** Refine a draft template via AI (edit, don't regenerate) — for the new-template builder. */
export async function aiEditTemplate(
  htmlContent: string,
  messages: { role: "user" | "assistant"; content: string }[],
  columns?: string[],
): Promise<{ html_content: string; summary: string }> {
  return fetchJSON("/generate-template/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ html_content: htmlContent, messages, columns }),
  });
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

export async function cancelTask(jobId: string, task: string): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/${task}/cancel`, { method: "POST" });
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

export function getPhotosDownloadUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/photos/zip`;
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

export async function downloadJobLog(jobId: string, logKey: string): Promise<void> {
  return downloadFile(
    `${API_BASE}/jobs/${jobId}/logs/${logKey}/download`,
    `${logKey}_log_${jobId}.csv`
  );
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

export function downloadTemplatePdf(templateId: string) {
  const token = typeof window !== "undefined" ? localStorage.getItem("vp_token") : null;
  const url = `${API_BASE}/templates/${templateId}/download`;
  // Use a hidden link with auth header via fetch + blob
  return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then((res) => {
      if (!res.ok) throw new Error("Download failed");
      return res.blob();
    })
    .then((blob) => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      const disposition = "template_preview.pdf";
      a.download = disposition;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    });
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

export async function cancelSubscription(): Promise<{ message: string; cancel_at_period_end: boolean }> {
  return fetchJSON("/billing/cancel", { method: "POST" });
}

export async function resumeSubscription(): Promise<{ message: string; cancel_at_period_end: boolean }> {
  return fetchJSON("/billing/resume", { method: "POST" });
}

export async function deleteAccount(): Promise<{ message: string }> {
  return fetchJSON("/auth/me", { method: "DELETE" });
}


// ── Profile ──────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  auth_provider: string;
  tier: string;
  username: string;
  avatar: string | null;
}

/** Update display name and/or avatar. Send only the field(s) you're changing. */
export async function updateProfile(fields: { username?: string; avatar?: string }): Promise<UserProfile> {
  return fetchJSON("/auth/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
}

/** Upload a custom avatar image (PNG/JPEG/WEBP); the server normalizes it to a square PNG. */
export async function uploadAvatar(file: File): Promise<UserProfile> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetchAPI("/auth/me/avatar", { method: "POST", body: form });
  return res.json();
}

/** Public URL for a user's uploaded avatar (only valid when their avatar is an upload). */
export function avatarUrl(userId: string, version?: string): string {
  return `${API_BASE}/auth/avatar/${userId}${version ? `?v=${encodeURIComponent(version)}` : ""}`;
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



// ── Column Mapping ──────────────────────────────────────────────────

export interface ColumnMapping {
  placeholders: string[];
  columns: string[];
  auto_matched: Record<string, string>;
  unmatched: string[];
  confirmed: boolean;
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


// ── In-Job Template Editing ─────────────────────────────────────────

export interface JobTemplate {
  id: string;
  name: string;
  description: string;
  html_content: string;
  placeholders: string[];
}

export interface JobTemplateChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** The job-local template fork (editable copy; never the shared library template). */
export async function getJobTemplate(jobId: string): Promise<JobTemplate> {
  return fetchJSON(`/jobs/${jobId}/template`);
}

/** Save edited HTML to the job-local template (HTML + rich-text tabs). */
export async function saveJobTemplate(jobId: string, htmlContent: string): Promise<JobTemplate> {
  return fetchJSON(`/jobs/${jobId}/template`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ html_content: htmlContent }),
  });
}

/** Edit the job-local template via AI. Pass the full client-held chat transcript. */
export async function aiEditJobTemplate(
  jobId: string,
  messages: JobTemplateChatMessage[],
): Promise<{ template: JobTemplate; summary: string }> {
  return fetchJSON(`/jobs/${jobId}/template/ai-edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
}

/** Discard in-job edits, re-forking from the original library template. */
export async function resetJobTemplate(jobId: string): Promise<JobTemplate> {
  return fetchJSON(`/jobs/${jobId}/template/reset`, { method: "POST" });
}

/**
 * Fetch the job template rendered with the first real data row, as an object URL
 * for an iframe `src`. Uses a Blob (not a data: URL) because templates can embed
 * megabytes of base64 images. Caller must URL.revokeObjectURL() the returned URL.
 */
export async function getJobTemplatePreviewUrl(jobId: string): Promise<string> {
  const res = await fetchAPI(`/jobs/${jobId}/template/preview`);
  const html = await res.text();
  const blob = new Blob([html], { type: "text/html" });
  return URL.createObjectURL(blob);
}


// ── Ask Volley — AI chats (server-persisted per job) ─────────────────

export interface AiChats {
  template: JobTemplateChatMessage[];
  email: JobTemplateChatMessage[];
  sms: JobTemplateChatMessage[];
}

/** Load all per-channel Ask Volley transcripts for a job (fast — light load). */
export async function getJobAiChats(jobId: string): Promise<AiChats> {
  return fetchJSON(`/jobs/${jobId}/ai-chats`);
}

/** First data row as a dict — for live previews (e.g. filling SMS placeholders). */
export async function getJobSampleRow(jobId: string): Promise<Record<string, string>> {
  return fetchJSON(`/jobs/${jobId}/sample-row`);
}

/** Replace one channel's transcript (used for "Clear"). */
export async function setJobAiChat(
  jobId: string,
  channel: "template" | "email" | "sms",
  messages: JobTemplateChatMessage[],
): Promise<{ message: string }> {
  return fetchJSON(`/jobs/${jobId}/ai-chats/${channel}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
}

/** Ask Volley: draft/refine the job's email. Applies to the job + persists the transcript. */
export async function aiDraftEmail(
  jobId: string,
  messages: JobTemplateChatMessage[],
): Promise<{ subject: string; body: string; summary: string }> {
  return fetchJSON(`/jobs/${jobId}/email/ai-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
}

/** Ask Volley: draft/refine the job's SMS. Applies to the job + persists the transcript. */
export async function aiDraftSms(
  jobId: string,
  messages: JobTemplateChatMessage[],
): Promise<{ body: string; summary: string }> {
  return fetchJSON(`/jobs/${jobId}/sms/ai-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
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

export interface SmsProviderStatus {
  provider_name: string;
  sender_id: string;
  default_region: string;
  is_configured: boolean;
}

export async function getSmsProviderStatus(): Promise<SmsProviderStatus> {
  return fetchJSON("/sms-settings");
}
