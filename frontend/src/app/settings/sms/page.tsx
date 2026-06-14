"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchJSON } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

interface SmsProviderOption {
  value: string;
  label: string;
  region: string;
  fields: { key: string; label: string; type: string; placeholder: string }[];
  senderPlaceholder: string;
  howTo: string;
}

const PROVIDERS: SmsProviderOption[] = [
  {
    value: "bulksms",
    label: "BulkSMS Nigeria",
    region: "Nigeria",
    fields: [{ key: "api_token", label: "API Token", type: "password", placeholder: "Your BulkSMS API token" }],
    senderPlaceholder: "Osalasi",
    howTo:
      "Sign in at bulksmsnigeria.com → Developer/API and copy your API token. Your Sender ID must be registered/approved in your BulkSMS account.",
  },
  {
    value: "twilio",
    label: "Twilio",
    region: "Global",
    fields: [
      { key: "account_sid", label: "Account SID", type: "text", placeholder: "ACxxxxxxxxxxxx" },
      { key: "auth_token", label: "Auth Token", type: "password", placeholder: "your auth token" },
    ],
    senderPlaceholder: "+15551234567 (your Twilio number)",
    howTo:
      "In the Twilio Console (console.twilio.com) copy your Account SID and Auth Token, then buy/verify a phone number. Use that number in E.164 form (e.g. +1...) — or a Messaging Service SID — as the Sender ID.",
  },
  {
    value: "vonage",
    label: "Vonage (Nexmo)",
    region: "Global",
    fields: [
      { key: "api_key", label: "API Key", type: "text", placeholder: "abcd1234" },
      { key: "api_secret", label: "API Secret", type: "password", placeholder: "your api secret" },
    ],
    senderPlaceholder: "Your brand name or Vonage number",
    howTo:
      "From the Vonage dashboard (dashboard.nexmo.com) copy your API key and secret. Sender ID can be an approved alphanumeric (where allowed) or a Vonage number.",
  },
  {
    value: "termii",
    label: "Termii",
    region: "Africa",
    fields: [{ key: "api_key", label: "API Key", type: "password", placeholder: "Your Termii API key" }],
    senderPlaceholder: "Your approved Sender ID",
    howTo:
      "Sign in at accounts.termii.com → Settings → API key. Register and get a Sender ID approved before sending.",
  },
  {
    value: "africastalking",
    label: "Africa's Talking",
    region: "Africa",
    fields: [
      { key: "username", label: "Username", type: "text", placeholder: "your AT username" },
      { key: "api_key", label: "API Key", type: "password", placeholder: "your API key" },
    ],
    senderPlaceholder: "Short code / Sender ID (optional)",
    howTo:
      "From account.africastalking.com copy your username and API key. A Sender ID/short code is optional — the sandbox uses a default.",
  },
];

const COUNTRIES = [
  { code: "NG", name: "Nigeria" },
  { code: "GH", name: "Ghana" },
  { code: "KE", name: "Kenya" },
  { code: "ZA", name: "South Africa" },
  { code: "CM", name: "Cameroon" },
  { code: "EG", name: "Egypt" },
  { code: "US", name: "United States" },
  { code: "CA", name: "Canada" },
  { code: "GB", name: "United Kingdom" },
  { code: "FR", name: "France" },
  { code: "DE", name: "Germany" },
  { code: "IN", name: "India" },
];

interface SmsConfig {
  provider_name: string;
  sender_id: string;
  default_region: string;
  is_configured: boolean;
}

export default function SmsSettingsPage() {
  const { toast } = useToast();
  const [selectedProvider, setSelectedProvider] = useState("");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [senderId, setSenderId] = useState("");
  const [defaultRegion, setDefaultRegion] = useState("NG");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testPhone, setTestPhone] = useState("");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [currentConfig, setCurrentConfig] = useState<SmsConfig | null>(null);

  useEffect(() => {
    fetchJSON<SmsConfig>("/sms-settings")
      .then((data) => {
        if (data) {
          setCurrentConfig(data);
          if (data.is_configured) {
            setSelectedProvider(data.provider_name);
            setSenderId(data.sender_id);
            setDefaultRegion(data.default_region || "NG");
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
      await fetchJSON("/sms-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_name: selectedProvider,
          credentials,
          sender_id: senderId,
          default_region: defaultRegion,
        }),
      });
      setMessage({ type: "success", text: "SMS settings saved successfully." });
      setCurrentConfig({
        provider_name: selectedProvider,
        sender_id: senderId,
        default_region: defaultRegion,
        is_configured: true,
      });
    } catch (err: unknown) {
      setMessage({ type: "error", text: friendlyError(err) });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!testPhone.trim()) {
      setMessage({ type: "error", text: "Enter a phone number to send the test to." });
      return;
    }
    setTesting(true);
    setMessage(null);
    try {
      const result = await fetchJSON<{ message: string }>("/sms-settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: testPhone }),
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
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">SMS Settings</h1>
          <p className="text-gray-500 mt-1 text-sm">Connect an SMS provider to start sending text messages.</p>
        </div>
        <Link
          href="/guides"
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-green-700 bg-green-50 rounded-xl hover:bg-green-100 transition-colors self-start"
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
              Sending as &ldquo;{currentConfig.sender_id}&rdquo; · default country {currentConfig.default_region}
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
        <h2 className="text-lg font-semibold text-gray-900 mb-1">SMS Provider</h2>
        <p className="text-sm text-gray-500 mb-5">Choose how you want to send text messages.</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {PROVIDERS.map((p) => (
            <button
              key={p.value}
              onClick={() => {
                setSelectedProvider(p.value);
                setCredentials({});
              }}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                selectedProvider === p.value ? "border-green-700 bg-green-50" : "border-gray-100 hover:border-gray-200"
              }`}
            >
              <p className="text-sm font-semibold text-gray-900">{p.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{p.region}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Credentials form */}
      {provider && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">{provider.label} Credentials</h2>
          <p className="text-sm text-gray-500 mb-5">Your credentials are encrypted before being stored.</p>

          {/* How To */}
          <div className="flex items-start gap-3 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 mb-5">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#b45309" strokeWidth="2" className="flex-shrink-0 mt-0.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            <p className="text-xs text-amber-800 leading-relaxed">
              <span className="font-semibold">How to set up {provider.label}:</span> {provider.howTo}
            </p>
          </div>

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
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Sender ID</label>
                <input
                  type="text"
                  value={senderId}
                  onChange={(e) => setSenderId(e.target.value)}
                  placeholder={provider.senderPlaceholder}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                />
                <p className="text-xs text-gray-400 mt-1">The &quot;From&quot; shown to recipients (alphanumeric or a number, per provider).</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Default country</label>
                <select
                  value={defaultRegion}
                  onChange={(e) => setDefaultRegion(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                >
                  {COUNTRIES.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">Used for numbers without a +country-code. Numbers with one are detected automatically.</p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-3 mt-6">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50 self-start"
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
            {currentConfig?.is_configured && (
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-3 border-t border-gray-100">
                <input
                  type="tel"
                  value={testPhone}
                  onChange={(e) => setTestPhone(e.target.value)}
                  placeholder="Test number (e.g. +234… or local)"
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
                />
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="px-6 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {testing ? "Sending..." : "Send Test SMS"}
                </button>
              </div>
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
            All API keys and tokens are encrypted with AES-128 before being stored. They are only decrypted at send time.
          </p>
        </div>
      </div>
    </div>
  );
}
