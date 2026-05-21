"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchJSON } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

interface ProviderOption {
  value: string;
  label: string;
  type: "api" | "smtp";
  fields: { key: string; label: string; type: string; placeholder: string }[];
}

const PROVIDERS: ProviderOption[] = [
  {
    value: "resend",
    label: "Resend",
    type: "api",
    fields: [{ key: "api_key", label: "API Key", type: "password", placeholder: "re_xxxxxxxxx" }],
  },
  {
    value: "sendgrid",
    label: "SendGrid",
    type: "api",
    fields: [{ key: "api_key", label: "API Key", type: "password", placeholder: "SG.xxxxxxxxx" }],
  },
  {
    value: "gmail",
    label: "Gmail SMTP",
    type: "smtp",
    fields: [
      { key: "username", label: "Gmail Address", type: "email", placeholder: "you@gmail.com" },
      { key: "password", label: "App Password", type: "password", placeholder: "xxxx xxxx xxxx xxxx" },
    ],
  },
  {
    value: "zoho",
    label: "Zoho SMTP",
    type: "smtp",
    fields: [
      { key: "username", label: "Zoho Email", type: "email", placeholder: "you@zoho.com" },
      { key: "password", label: "Password", type: "password", placeholder: "Your Zoho password" },
    ],
  },
  {
    value: "outlook",
    label: "Outlook SMTP",
    type: "smtp",
    fields: [
      { key: "username", label: "Outlook Email", type: "email", placeholder: "you@outlook.com" },
      { key: "password", label: "Password", type: "password", placeholder: "Your Outlook password" },
    ],
  },
  {
    value: "smtp",
    label: "Custom SMTP",
    type: "smtp",
    fields: [
      { key: "host", label: "SMTP Host", type: "text", placeholder: "smtp.example.com" },
      { key: "port", label: "SMTP Port", type: "number", placeholder: "587" },
      { key: "username", label: "Username", type: "text", placeholder: "your-username" },
      { key: "password", label: "Password", type: "password", placeholder: "your-password" },
    ],
  },
];

export default function EmailSettingsPage() {
  const { toast } = useToast();
  const [selectedProvider, setSelectedProvider] = useState("");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [fromName, setFromName] = useState("");
  const [fromEmail, setFromEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [currentConfig, setCurrentConfig] = useState<{
    provider_name: string;
    from_name: string;
    from_email: string;
    is_configured: boolean;
  } | null>(null);

  useEffect(() => {
    fetchJSON<typeof currentConfig>("/email-settings")
      .then((data) => {
        if (data) {
          setCurrentConfig(data);
          if (data.is_configured) {
            setSelectedProvider(data.provider_name);
            setFromName(data.from_name);
            setFromEmail(data.from_email);
          }
        }
      })
      .catch((err: unknown) => toast(friendlyError(err)));
  }, []);

  const provider = PROVIDERS.find((p) => p.value === selectedProvider);

  function handleCredentialChange(key: string, value: string) {
    setCredentials((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!provider) return;
    setSaving(true);
    setMessage(null);
    try {
      await fetchJSON("/email-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_name: selectedProvider,
          credentials,
          from_name: fromName,
          from_email: fromEmail,
        }),
      });
      setMessage({ type: "success", text: "Email settings saved successfully." });
      setCurrentConfig({
        provider_name: selectedProvider,
        from_name: fromName,
        from_email: fromEmail,
        is_configured: true,
      });
    } catch (err: unknown) {
      setMessage({ type: "error", text: friendlyError(err) });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setMessage(null);
    try {
      const result = await fetchJSON<{ message: string }>("/email-settings/test", {
        method: "POST",
      });
      setMessage({ type: "success", text: result.message });
    } catch (err: unknown) {
      setMessage({ type: "error", text: friendlyError(err) });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Email Settings</h1>
          <p className="text-gray-500 mt-1">Connect your email service to start sending.</p>
        </div>
        <Link
          href="/guides"
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-green-700 bg-green-50 rounded-xl hover:bg-green-100 transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
          Setup Guides
        </Link>
      </div>

      {/* Current config status */}
      {currentConfig?.is_configured && (
        <div className="mb-6 flex items-center gap-3 bg-green-50 border border-green-100 rounded-2xl px-5 py-4">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
          <div>
            <p className="text-sm font-medium text-green-900">
              Connected to {PROVIDERS.find((p) => p.value === currentConfig.provider_name)?.label || currentConfig.provider_name}
            </p>
            <p className="text-xs text-green-700">
              Sending as {currentConfig.from_name} &lt;{currentConfig.from_email}&gt;
            </p>
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div
          className={`mb-6 p-3 rounded-xl text-sm ${
            message.type === "success"
              ? "bg-green-50 border border-green-100 text-green-700"
              : "bg-red-50 border border-red-100 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Provider selector */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Email Provider</h2>
        <p className="text-sm text-gray-500 mb-5">Choose how you want to send emails.</p>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {PROVIDERS.map((p) => (
            <button
              key={p.value}
              onClick={() => {
                setSelectedProvider(p.value);
                setCredentials({});
              }}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                selectedProvider === p.value
                  ? "border-green-700 bg-green-50"
                  : "border-gray-100 hover:border-gray-200"
              }`}
            >
              <p className="text-sm font-semibold text-gray-900">{p.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {p.type === "api" ? "API Key" : "SMTP"}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Credentials form */}
      {provider && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">{provider.label} Credentials</h2>
          <p className="text-sm text-gray-500 mb-5">
            Your credentials are encrypted before being stored.
          </p>

          <div className="space-y-4">
            {provider.fields.map((field) => (
              <div key={field.key}>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">{field.label}</label>
                <input
                  type={field.type}
                  value={credentials[field.key] || ""}
                  onChange={(e) => handleCredentialChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                />
              </div>
            ))}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Sender Name</label>
                <input
                  type="text"
                  value={fromName}
                  onChange={(e) => setFromName(e.target.value)}
                  placeholder="Your Company"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Sender Email</label>
                <input
                  type="email"
                  value={fromEmail}
                  onChange={(e) => setFromEmail(e.target.value)}
                  placeholder="noreply@yourdomain.com"
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-6">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
            {currentConfig?.is_configured && (
              <button
                onClick={handleTest}
                disabled={testing}
                className="px-6 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                {testing ? "Sending..." : "Send Test Email"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Security note */}
      <div className="flex items-start gap-3 bg-gray-50 border border-gray-100 rounded-2xl px-5 py-4">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" className="flex-shrink-0 mt-0.5">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
        <div>
          <p className="text-sm font-medium text-gray-700">Your credentials are secure</p>
          <p className="text-xs text-gray-500 mt-0.5">
            All API keys and passwords are encrypted with AES-128 before being stored. They are only decrypted at send time.
          </p>
        </div>
      </div>
    </div>
  );
}
