"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { LogoIcon, LogoFull } from "@/components/Logo";
import { friendlyError } from "@/lib/errors";
import GoogleSignIn from "@/components/GoogleSignIn";

export default function SignupPage() {
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      await signup(email, password);
    } catch (err: unknown) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left — branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-green-800 text-white flex-col justify-center px-16">
        <div className="flex items-center gap-3 mb-8">
          <LogoFull height={40} className="brightness-0 invert" />
        </div>
        <h2 className="text-4xl font-bold leading-tight mb-4">
          Get started<br />in seconds.
        </h2>
        <p className="text-green-100 text-lg max-w-md">
          Create your account, connect your email service, and start sending batch emails right away.
        </p>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <LogoFull height={32} />
          </div>

          <h1 className="text-2xl font-bold text-gray-900 mb-1">Create your account</h1>
          <p className="text-gray-500 mb-8">Start sending batch emails in minutes.</p>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-100 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm password</label>
              <input
                type="password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm text-gray-800 placeholder-gray-400 outline-none focus:ring-2 focus:ring-green-700/20 focus:border-green-300"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-green-800 text-white text-sm font-semibold rounded-xl hover:bg-green-900 transition-colors disabled:opacity-50"
            >
              {loading ? "Creating account..." : "Create account"}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400 uppercase">or</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          {/* Google */}
          <GoogleSignIn onError={(msg) => setError(msg)} label="Sign up with Google" />

          <p className="text-center text-sm text-gray-500 mt-8">
            Already have an account?{" "}
            <Link href="/login" className="text-green-700 font-medium hover:text-green-800">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
