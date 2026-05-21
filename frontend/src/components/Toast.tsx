"use client";

import { useEffect, useState, createContext, useContext, useCallback, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";

/* ─── Types ─── */
type ToastType = "error" | "success" | "info" | "warning";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void;
}

/* ─── Context ─── */
const ToastContext = createContext<ToastContextType | null>(null);

let _nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: ToastType = "error") => {
    const id = _nextId++;
    setToasts((prev) => [...prev, { id, type, message }]);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}

      {/* Toast container — fixed bottom-right */}
      <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => (
            <ToastCard key={t.id} item={t} onDismiss={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextType {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

/* ─── Individual toast card ─── */
const ICONS: Record<ToastType, { color: string; bg: string; icon: string }> = {
  error: {
    color: "text-red-600",
    bg: "bg-red-50 border-red-200",
    icon: "M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  success: {
    color: "text-green-600",
    bg: "bg-green-50 border-green-200",
    icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  warning: {
    color: "text-amber-600",
    bg: "bg-amber-50 border-amber-200",
    icon: "M12 9v2m0 4h.01M12 3l9.66 16.5H2.34L12 3z",
  },
  info: {
    color: "text-blue-600",
    bg: "bg-blue-50 border-blue-200",
    icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
};

const AUTO_DISMISS_MS = 6000;

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const style = ICONS[item.type];

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(item.id), AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [item.id, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3.5 rounded-xl border shadow-lg ${style.bg}`}
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={`flex-shrink-0 mt-0.5 ${style.color}`}
      >
        <path d={style.icon} />
      </svg>
      <p className="text-sm text-gray-800 flex-1 leading-snug">{item.message}</p>
      <button
        onClick={() => onDismiss(item.id)}
        className="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </motion.div>
  );
}
