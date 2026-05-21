"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useAuth } from "@/lib/auth";
import { friendlyError } from "@/lib/errors";

const GOOGLE_CLIENT_ID =
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
  "903491688476-rhjci8k05pm96v8afa9eruklqi3co8ce.apps.googleusercontent.com";

/**
 * Loads the Google Identity Services script once globally.
 * Returns a promise that resolves when `google.accounts.id` is ready.
 */
let _gsiPromise: Promise<void> | null = null;

function loadGsi(): Promise<void> {
  if (_gsiPromise) return _gsiPromise;
  _gsiPromise = new Promise((resolve, reject) => {
    if (typeof window === "undefined") return reject();
    // Already loaded?
    if (window.google?.accounts?.id) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      _gsiPromise = null;
      reject(new Error("Failed to load Google Sign-In"));
    };
    document.head.appendChild(script);
  });
  return _gsiPromise;
}

// Extend Window for google global
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: Record<string, unknown>) => void;
          prompt: (cb?: (notification: { isNotDisplayed: () => boolean }) => void) => void;
          renderButton: (el: HTMLElement, config: Record<string, unknown>) => void;
          revoke: (email: string, cb: () => void) => void;
        };
      };
    };
  }
}

interface GoogleSignInProps {
  onError?: (msg: string) => void;
  label?: string;
}

export default function GoogleSignIn({ onError, label = "Continue with Google" }: GoogleSignInProps) {
  const { googleLogin } = useAuth();
  const [loading, setLoading] = useState(false);
  const btnRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  const handleCredentialResponse = useCallback(
    async (response: { credential: string }) => {
      setLoading(true);
      try {
        await googleLogin(response.credential);
      } catch (err) {
        onError?.(friendlyError(err));
      } finally {
        setLoading(false);
      }
    },
    [googleLogin, onError],
  );

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    loadGsi()
      .then(() => {
        window.google!.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleCredentialResponse,
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        // Render the styled Google button into our hidden container
        if (btnRef.current) {
          window.google!.accounts.id.renderButton(btnRef.current, {
            type: "standard",
            shape: "rectangular",
            theme: "outline",
            size: "large",
            text: "continue_with",
            width: btnRef.current.offsetWidth,
          });
        }
      })
      .catch(() => {
        // Script failed to load — button stays as our custom fallback
      });
  }, [handleCredentialResponse]);

  return (
    <div className="relative w-full">
      {/* Google's rendered button (positioned on top, transparent so our styled button shows through) */}
      <div
        ref={btnRef}
        className="absolute inset-0 z-10 overflow-hidden rounded-xl opacity-[0.01]"
        style={{ minHeight: 48 }}
      />

      {/* Our custom styled button (visible underneath) */}
      <button
        type="button"
        disabled={loading}
        className="w-full flex items-center justify-center gap-3 py-3 border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 relative"
      >
        {loading ? (
          <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23Z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84Z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53Z"
              fill="#EA4335"
            />
          </svg>
        )}
        {label}
      </button>
    </div>
  );
}
