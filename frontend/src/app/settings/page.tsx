"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { deleteAccount } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

const settingSections = [
  {
    title: "Email Provider",
    description: "Connect your email service (Resend, SendGrid, Gmail, Zoho, or custom SMTP).",
    href: "/settings/email",
    icon: EmailIcon,
  },
  {
    title: "SMS Provider",
    description: "Connect an SMS service (BulkSMS, Twilio, Vonage, Termii, or Africa's Talking).",
    href: "/settings/sms",
    icon: SmsIcon,
  },
  {
    title: "Billing & Subscription",
    description: "Manage your plan, view usage, and update payment details.",
    href: "/settings/billing",
    icon: BillingIcon,
  },
];

export default function SettingsPage() {
  const { logout } = useAuth();
  const { toast } = useToast();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function handleDeleteAccount() {
    setDeleting(true);
    try {
      await deleteAccount();
      logout();
      window.location.href = "/";
    } catch (err) {
      toast(friendlyError(err));
      setDeleting(false);
    }
  }

  return (
    <div>
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 mt-1 text-sm">Manage your account and service connections.</p>
      </div>

      <div className="space-y-4">
        {settingSections.map((section) => (
          <Link
            key={section.title}
            href={section.href}
            className="block bg-white rounded-2xl border border-gray-100 shadow-sm p-6 hover:border-green-200 hover:shadow-md transition-all"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center">
                <section.icon />
              </div>
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
                <p className="text-sm text-gray-500 mt-0.5">{section.description}</p>
              </div>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </div>
          </Link>
        ))}
      </div>

      {/* Danger zone */}
      <div className="mt-10 bg-white rounded-2xl border border-red-100 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-red-700">Danger Zone</h2>
        <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-gray-900">Delete account</p>
            <p className="text-sm text-gray-500 mt-0.5">
              Permanently deletes your account, jobs, templates, and data. Any active subscription is cancelled.
              This cannot be undone.
            </p>
          </div>
          <button
            onClick={() => { setConfirmText(""); setShowDeleteModal(true); }}
            className="px-4 py-2.5 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-xl hover:bg-red-50 transition-colors self-start sm:self-auto flex-shrink-0"
          >
            Delete Account
          </button>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Delete your account?</h3>
            <p className="text-sm text-gray-600 mb-4">
              This permanently deletes your account, all jobs, templates, and settings. Any active
              subscription is cancelled immediately. <span className="font-semibold">This cannot be undone.</span>
            </p>
            <label className="block text-sm text-gray-700 mb-2">
              Type <span className="font-mono font-bold">DELETE</span> to confirm:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm mb-5 focus:outline-none focus:ring-2 focus:ring-red-500"
              placeholder="DELETE"
              autoFocus
            />
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={confirmText !== "DELETE" || deleting}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-xl hover:bg-red-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {deleting ? "Deleting..." : "Delete Forever"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function BillingIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  );
}

function EmailIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function SmsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
