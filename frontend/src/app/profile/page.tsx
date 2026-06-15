"use client";

import { useState, useEffect, ChangeEvent } from "react";
import { useAuth } from "@/lib/auth";
import { updateProfile, uploadAvatar, deleteAccount } from "@/lib/api";
import { PRESET_AVATARS, PRESET_GROUPS } from "@/lib/avatars";
import Avatar from "@/components/Avatar";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

export default function ProfilePage() {
  const { user, refreshUser, logout } = useAuth();
  const { toast } = useToast();

  const [username, setUsername] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [pickingPreset, setPickingPreset] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (user?.username) setUsername(user.username);
  }, [user?.username]);

  async function handleSaveName() {
    const name = username.trim();
    if (!name) {
      toast("Please enter a display name.", "error");
      return;
    }
    setSavingName(true);
    try {
      await updateProfile({ username: name });
      await refreshUser();
      toast("Display name saved.", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setSavingName(false);
    }
  }

  async function handlePickPreset(id: string) {
    setPickingPreset(true);
    try {
      await updateProfile({ avatar: `preset:${id}` });
      await refreshUser();
      toast("Avatar updated.", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setPickingPreset(false);
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    setUploadingAvatar(true);
    try {
      await uploadAvatar(file);
      await refreshUser();
      toast("Avatar uploaded.", "success");
    } catch (err) {
      toast(friendlyError(err));
    } finally {
      setUploadingAvatar(false);
    }
  }

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

  const busy = uploadingAvatar || pickingPreset;

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Profile</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Customize how you appear on your dashboard and on templates you make public.
        </p>
      </div>

      {/* Identity + display name */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
        <div className="flex items-center gap-4">
          <Avatar avatar={user?.avatar} name={user?.username || user?.email} userId={user?.id} size={72} />
          <div className="min-w-0">
            <p className="text-lg font-semibold text-gray-900 truncate">{user?.username || "—"}</p>
            <p className="text-sm text-gray-500 truncate">{user?.email}</p>
          </div>
        </div>

        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Display name</label>
          <p className="text-xs text-gray-500 mb-2">
            Shown on your dashboard and as the author on your public templates.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              maxLength={50}
              placeholder="e.g. Osalasi Company"
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
            />
            <button
              onClick={handleSaveName}
              disabled={savingName || username.trim() === (user?.username || "")}
              className="px-6 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
            >
              {savingName ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>

      {/* Avatar */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-900">Avatar</h2>
          <label
            className={`px-4 py-2 text-sm font-medium rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
              uploadingAvatar ? "opacity-50 pointer-events-none" : ""
            }`}
          >
            {uploadingAvatar ? "Uploading..." : "Upload image"}
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={handleUpload} className="hidden" />
          </label>
        </div>
        <p className="text-sm text-gray-500 mb-5">Upload your own (PNG/JPG/WEBP) or pick a preset below.</p>

        {PRESET_GROUPS.map((group) => (
          <div key={group} className="mb-5 last:mb-0">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">{group}</p>
            <div className="grid grid-cols-5 sm:grid-cols-7 gap-3">
              {PRESET_AVATARS.filter((p) => p.group === group).map((p) => {
                const selected = user?.avatar === `preset:${p.id}`;
                return (
                  <button
                    key={p.id}
                    onClick={() => handlePickPreset(p.id)}
                    disabled={busy}
                    title={p.label}
                    aria-label={p.label}
                    className={`rounded-full transition-all disabled:opacity-60 ${
                      selected
                        ? "ring-2 ring-green-700 ring-offset-2"
                        : "hover:ring-2 hover:ring-gray-200 hover:ring-offset-2"
                    }`}
                  >
                    <Avatar avatar={`preset:${p.id}`} size={48} />
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        <p className="text-[11px] text-gray-400 mt-4">Animal &amp; alien avatars by Twemoji (CC-BY 4.0).</p>
      </div>

      {/* Danger zone (moved here from Settings) */}
      <div className="bg-white rounded-2xl border border-red-100 shadow-sm p-6">
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
            onClick={() => {
              setConfirmText("");
              setShowDeleteModal(true);
            }}
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
