"use client";

import { useState } from "react";
import { Template, updateTemplateVisibility, deleteTemplate } from "@/lib/api";
import PdfPreviewModal from "./PdfPreviewModal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TemplateCardProps {
  template: Template;
  onUpdate?: () => void;
}

export default function TemplateCard({ template, onUpdate }: TemplateCardProps) {
  const [showPreview, setShowPreview] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const isSystem = !template.owner_id;
  const isOwn = template.is_own;

  async function handleToggleVisibility() {
    setToggling(true);
    try {
      const newVis = template.visibility === "public" ? "private" : "public";
      await updateTemplateVisibility(template.id, newVis);
      onUpdate?.();
    } catch {
      // silently fail
    } finally {
      setToggling(false);
      setShowMenu(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this template? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteTemplate(template.id);
      onUpdate?.();
    } catch {
      // silently fail
    } finally {
      setDeleting(false);
      setShowMenu(false);
    }
  }

  return (
    <>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow relative">
        {/* Thumbnail */}
        <div className="h-40 bg-gradient-to-br from-green-50 to-green-100 flex items-center justify-center relative">
          <div className="w-20 h-28 bg-white rounded-lg shadow-md flex flex-col items-center justify-center gap-2 border border-gray-200">
            <div className="w-10 h-1.5 bg-green-700 rounded-full" />
            <div className="w-12 h-1 bg-gray-200 rounded-full" />
            <div className="w-12 h-1 bg-gray-200 rounded-full" />
            <div className="w-8 h-1 bg-gray-200 rounded-full" />
            <div className="w-10 h-3 bg-green-100 rounded mt-1" />
          </div>

          {/* Badges */}
          <div className="absolute top-2 left-2 flex gap-1.5">
            {isSystem && (
              <span className="px-2 py-0.5 bg-green-800 text-white text-[10px] font-bold rounded-full">
                VolleyPacket
              </span>
            )}
            {!isSystem && template.visibility === "public" && (
              <span className="px-2 py-0.5 bg-blue-600 text-white text-[10px] font-bold rounded-full">
                Public
              </span>
            )}
            {!isSystem && template.visibility === "private" && isOwn && (
              <span className="px-2 py-0.5 bg-gray-500 text-white text-[10px] font-bold rounded-full">
                Private
              </span>
            )}
            {template.tier_required !== "free" && (
              <span className="px-2 py-0.5 bg-amber-500 text-white text-[10px] font-bold rounded-full capitalize">
                {template.tier_required}
              </span>
            )}
          </div>

          {/* Menu button (own templates only) */}
          {isOwn && (
            <div className="absolute top-2 right-2">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="w-7 h-7 rounded-full bg-white/80 flex items-center justify-center hover:bg-white transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
                  <circle cx="12" cy="5" r="1" />
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="12" cy="19" r="1" />
                </svg>
              </button>

              {showMenu && (
                <div className="absolute right-0 top-8 bg-white rounded-xl shadow-lg border border-gray-100 py-1 min-w-[160px] z-10">
                  <button
                    onClick={handleToggleVisibility}
                    disabled={toggling}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    {toggling
                      ? "Updating..."
                      : template.visibility === "public"
                      ? "Make Private"
                      : "Publish to Community"}
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete Template"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-4">
          <h3 className="font-semibold text-gray-900 text-sm">{template.name}</h3>
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">{template.description}</p>
          {!isSystem && !isOwn && (
            <p className="text-[10px] text-gray-400 mt-1">by {template.owner_name}</p>
          )}
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={() => setShowPreview(true)}
              className="flex-1 text-center text-xs font-medium py-2 rounded-xl bg-green-50 text-green-800 hover:bg-green-100 transition-colors"
            >
              Preview
            </button>
            <button className="flex-1 text-center text-xs font-medium py-2 rounded-xl bg-green-800 text-white hover:bg-green-900 transition-colors">
              Use Template
            </button>
          </div>
        </div>
      </div>

      {showPreview && (
        <PdfPreviewModal
          url={`${API_BASE}/templates/${template.id}/preview`}
          title={template.name}
          onClose={() => setShowPreview(false)}
        />
      )}
    </>
  );
}
