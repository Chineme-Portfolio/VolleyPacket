"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  getTiers,
  getSubscription,
  getUserRegion,
  resetUserRegion,
  createCheckout,
  createPortalSession,
  cancelSubscription,
  resumeSubscription,
  TierInfo,
  Subscription,
} from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { useToast } from "@/components/Toast";

const TIER_ORDER = ["free", "classic", "pro"];

const TIER_COLORS: Record<string, { bg: string; border: string; badge: string; button: string; buttonHover: string }> = {
  free: {
    bg: "bg-white",
    border: "border-gray-200",
    badge: "bg-gray-100 text-gray-600",
    button: "bg-gray-800 text-white",
    buttonHover: "hover:bg-gray-900",
  },
  classic: {
    bg: "bg-white",
    border: "border-green-200",
    badge: "bg-green-100 text-green-700",
    button: "bg-green-800 text-white",
    buttonHover: "hover:bg-green-900",
  },
  pro: {
    bg: "bg-gradient-to-br from-green-50 to-emerald-50",
    border: "border-green-300",
    badge: "bg-emerald-100 text-emerald-700",
    button: "bg-emerald-700 text-white",
    buttonHover: "hover:bg-emerald-800",
  },
};

export default function BillingPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const [tiers, setTiers] = useState<Record<string, TierInfo> | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [region, setRegion] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [resettingRegion, setResettingRegion] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);

  const success = searchParams.get("success");
  const cancelled = searchParams.get("cancelled");

  useEffect(() => {
    if (success === "true") {
      setMessage({ type: "success", text: "Subscription activated! Your account has been upgraded." });
    } else if (cancelled === "true") {
      setMessage({ type: "error", text: "Checkout was cancelled. No changes were made." });
    }
  }, [success, cancelled]);

  useEffect(() => {
    // Region is auto-detected and locked on first call
    Promise.all([getUserRegion(), getSubscription()])
      .then(([regionData, sub]) => {
        const userRegion = regionData.region || "US";
        setRegion(userRegion);
        setSubscription(sub);
        return getTiers(userRegion);
      })
      .then((t) => setTiers(t))
      .catch((err: unknown) => toast(friendlyError(err)))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpgrade(tier: string) {
    setCheckoutLoading(tier);
    setMessage(null);
    try {
      const { checkout_url } = await createCheckout(tier);
      window.location.href = checkout_url;
    } catch (err) {
      setMessage({ type: "error", text: friendlyError(err) });
      setCheckoutLoading(null);
    }
  }

  async function handleManageBilling() {
    setPortalLoading(true);
    setMessage(null);
    try {
      const { portal_url } = await createPortalSession();
      window.location.href = portal_url;
    } catch (err) {
      setMessage({ type: "error", text: friendlyError(err) });
      setPortalLoading(false);
    }
  }

  async function handleCancelSubscription() {
    setCancelLoading(true);
    setMessage(null);
    try {
      const result = await cancelSubscription();
      setMessage({ type: "success", text: result.message });
      setSubscription(await getSubscription());
      setShowCancelConfirm(false);
    } catch (err) {
      setMessage({ type: "error", text: friendlyError(err) });
    } finally {
      setCancelLoading(false);
    }
  }

  async function handleResumeSubscription() {
    setCancelLoading(true);
    setMessage(null);
    try {
      const result = await resumeSubscription();
      setMessage({ type: "success", text: result.message });
      setSubscription(await getSubscription());
    } catch (err) {
      setMessage({ type: "error", text: friendlyError(err) });
    } finally {
      setCancelLoading(false);
    }
  }

  const currentTier = subscription?.tier || user?.tier || "free";
  const isNigeria = region === "NG";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-green-700 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Billing & Subscription</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Choose the plan that fits your workflow.
            {region && (
              <span className="ml-2 text-xs text-gray-400">
                Prices shown in {isNigeria ? "NGN" : "USD"} &middot;{" "}
                <button
                  type="button"
                  disabled={resettingRegion}
                  onClick={async () => {
                    setResettingRegion(true);
                    try {
                      const result = await resetUserRegion();
                      const newRegion = result.region || "US";
                      setRegion(newRegion);
                      const t = await getTiers(newRegion);
                      setTiers(t);
                      toast(newRegion === "NG" ? "Region updated to Nigeria (NGN)" : `Region updated to ${newRegion} (USD)`, "success");
                    } catch (err) {
                      toast(friendlyError(err));
                    } finally {
                      setResettingRegion(false);
                    }
                  }}
                  className="text-green-700 hover:text-green-800 underline underline-offset-2"
                >
                  {resettingRegion ? "Detecting..." : "Wrong region?"}
                </button>
              </span>
            )}
          </p>
        </div>
        <Link
          href="/settings"
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors self-start flex-shrink-0"
        >
          Back to Settings
        </Link>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mb-6 p-4 rounded-xl text-sm font-medium ${
            message.type === "success"
              ? "bg-green-50 border border-green-100 text-green-700"
              : "bg-red-50 border border-red-100 text-red-700"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Current plan banner */}
      <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-center gap-3 bg-green-50 border border-green-100 rounded-2xl px-4 sm:px-5 py-4">
        <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
        <div className="flex-1">
          <p className="text-sm font-medium text-green-900">
            Current plan: <span className="font-bold capitalize">{currentTier}</span>
            {subscription?.payment_provider && currentTier !== "free" && (
              <span className="ml-2 text-xs text-green-600">
                via {subscription.payment_provider === "paystack" ? "Paystack" : "Stripe"}
              </span>
            )}
          </p>
          {subscription?.cancel_at_period_end && subscription.current_period_end && (
            <p className="text-xs text-green-700">
              Cancels at end of period: {new Date(subscription.current_period_end).toLocaleDateString()}
            </p>
          )}
          {subscription?.status === "past_due" && (
            <p className="text-xs text-red-600 font-medium">Payment past due — please update your payment method.</p>
          )}
        </div>
        {currentTier !== "free" && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleManageBilling}
              disabled={portalLoading}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              {portalLoading ? "Opening..." : "Manage Billing"}
            </button>
            {subscription?.cancel_at_period_end ? (
              <button
                onClick={handleResumeSubscription}
                disabled={cancelLoading}
                className="px-4 py-2 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-xl hover:bg-green-100 transition-colors disabled:opacity-50"
              >
                {cancelLoading ? "Resuming..." : "Resume Subscription"}
              </button>
            ) : (
              <button
                onClick={() => setShowCancelConfirm(true)}
                disabled={cancelLoading}
                className="px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-200 rounded-xl hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                Cancel Subscription
              </button>
            )}
          </div>
        )}
      </div>

      {/* Cancel confirmation modal */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Cancel your subscription?</h3>
            <p className="text-sm text-gray-600 mb-1">
              You&apos;ll keep <span className="font-semibold capitalize">{currentTier}</span> access until the end of
              your current billing period{subscription?.current_period_end && (
                <> ({new Date(subscription.current_period_end).toLocaleDateString()})</>
              )}, then your account moves to the Free plan.
            </p>
            <p className="text-sm text-gray-600 mb-5">
              Your jobs and templates are kept. You can resume anytime before the period ends.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowCancelConfirm(false)}
                disabled={cancelLoading}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Keep Subscription
              </button>
              <button
                onClick={handleCancelSubscription}
                disabled={cancelLoading}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-xl hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {cancelLoading ? "Cancelling..." : "Yes, Cancel"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pricing cards */}
      {tiers && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {TIER_ORDER.map((tierKey) => {
            const tier = tiers[tierKey];
            if (!tier) return null;
            const colors = TIER_COLORS[tierKey];
            const isCurrent = currentTier === tierKey;
            const isUpgrade = TIER_ORDER.indexOf(tierKey) > TIER_ORDER.indexOf(currentTier);
            const isDowngrade = TIER_ORDER.indexOf(tierKey) < TIER_ORDER.indexOf(currentTier);

            return (
              <div
                key={tierKey}
                className={`relative rounded-2xl border-2 p-6 flex flex-col ${colors.bg} ${
                  isCurrent ? "border-green-700 shadow-md" : colors.border
                }`}
              >
                {/* Current badge */}
                {isCurrent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-green-800 text-white text-xs font-bold rounded-full">
                    Current Plan
                  </div>
                )}

                {/* Pro popular badge */}
                {tierKey === "pro" && !isCurrent && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-emerald-600 text-white text-xs font-bold rounded-full">
                    Most Popular
                  </div>
                )}

                <div className="mb-4">
                  <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${colors.badge}`}>
                    {tier.name}
                  </span>
                </div>

                <div className="mb-6">
                  <span className="text-4xl font-bold text-gray-900">
                    {tier.currency_symbol}{tier.price_monthly.toLocaleString()}
                  </span>
                  <span className="text-gray-500 text-sm">/month</span>
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8 flex-1">
                  {tier.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-gray-700">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#047857"
                        strokeWidth="2.5"
                        className="flex-shrink-0 mt-0.5"
                      >
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                      {feature}
                    </li>
                  ))}
                </ul>

                {/* Action button */}
                {isCurrent ? (
                  <div className="text-center py-2.5 text-sm font-medium text-gray-500 bg-gray-100 rounded-xl">
                    Your current plan
                  </div>
                ) : isUpgrade ? (
                  <button
                    onClick={() => handleUpgrade(tierKey)}
                    disabled={checkoutLoading === tierKey}
                    className={`w-full py-2.5 text-sm font-medium rounded-xl transition-colors disabled:opacity-50 ${colors.button} ${colors.buttonHover}`}
                  >
                    {checkoutLoading === tierKey ? "Redirecting..." : `Upgrade to ${tier.name}`}
                  </button>
                ) : isDowngrade ? (
                  <button
                    onClick={handleManageBilling}
                    disabled={portalLoading}
                    className="w-full py-2.5 text-sm font-medium text-gray-600 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    Downgrade
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      {/* FAQ / Info */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Frequently Asked Questions</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Can I change plans anytime?</h3>
            <p className="text-sm text-gray-500 mt-1">
              Yes! Upgrade instantly or downgrade at the end of your billing cycle. No long-term contracts.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">What happens to my jobs if I downgrade?</h3>
            <p className="text-sm text-gray-500 mt-1">
              Existing jobs are preserved. On the Free plan you can have up to 3 active jobs — delete completed ones to make room.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">How is my currency determined?</h3>
            <p className="text-sm text-gray-500 mt-1">
              Your currency is automatically set based on your location when you first visit the billing page.
              Nigerian users pay in Naira via Paystack, and international users pay in USD via Stripe.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">How do published templates work?</h3>
            <p className="text-sm text-gray-500 mt-1">
              Classic and Pro users can share their templates publicly. Published templates appear in the community library for all users.
              Your name is shown as the author.
            </p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Is my payment secure?</h3>
            <p className="text-sm text-gray-500 mt-1">
              All payments are processed securely through {isNigeria ? "Paystack" : "Stripe"}. We never store your card details.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
