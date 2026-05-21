"use client";

import { useRef, useEffect, useState } from "react";
import Link from "next/link";
import { motion, useScroll, useTransform, useInView, useSpring } from "framer-motion";
import { LogoIcon, LogoFull } from "@/components/Logo";

/* ───────────── Volleyball 3D Component ───────────── */
function Volleyball3D({ className = "" }: { className?: string }) {
  return (
    <div className={`volleyball-scene ${className}`}>
      <div className="volleyball-ball">
        {/* Seam lines rendered as pseudo-elements via CSS */}
        <div className="vb-seam vb-seam-h1" />
        <div className="vb-seam vb-seam-h2" />
        <div className="vb-seam vb-seam-v1" />
        {/* Paper airplane overlay */}
        <div className="vb-airplane">
          <svg viewBox="0 0 40 30" width="40" height="30">
            <polygon points="0,15 36,0 12,12" fill="white" opacity="0.9" />
            <polygon points="12,12 36,0 16,26" fill="white" opacity="0.7" />
          </svg>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Animated counter ───────────── */
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const duration = 1500;
    const step = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      setVal(Math.floor(progress * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [isInView, target]);

  return (
    <span ref={ref}>
      {val.toLocaleString()}
      {suffix}
    </span>
  );
}

/* ───────────── Feature card with 3D tilt ───────────── */
function TiltCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState({ rotateX: 0, rotateY: 0 });

  function handleMove(e: React.MouseEvent) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setStyle({ rotateX: -y * 12, rotateY: x * 12 });
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={() => setStyle({ rotateX: 0, rotateY: 0 })}
      animate={style}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      style={{ perspective: 800, transformStyle: "preserve-3d" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ───────────── Section reveal wrapper ───────────── */
function Reveal({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.7, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

/* ───────────── HOW IT WORKS step data ───────────── */
const steps = [
  {
    num: "01",
    title: "Upload your list",
    desc: "Drop a CSV or Excel file with your recipients. We parse names, emails, and custom fields automatically.",
    icon: (
      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    ),
  },
  {
    num: "02",
    title: "Design your template",
    desc: "Use our AI-powered editor or upload a DOCX/PDF. Insert merge fields like {{name}} and {{date}}.",
    icon: (
      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
    ),
  },
  {
    num: "03",
    title: "Hit send",
    desc: "Generate personalized PDFs and emails in one click. Track delivery, opens, and errors in real-time.",
    icon: (
      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="22" y1="2" x2="11" y2="13" />
        <polygon points="22 2 15 22 11 13 2 9 22 2" />
      </svg>
    ),
  },
];

/* ───────────── FEATURES data ───────────── */
const features = [
  {
    title: "AI Email Composer",
    desc: "Describe what you want, and our AI writes professional emails with perfect merge fields.",
    icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  },
  {
    title: "Batch PDF Generation",
    desc: "Turn a single template into hundreds of personalized documents — exam slips, invoices, certificates.",
    icon: "M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z",
  },
  {
    title: "Real-time Tracking",
    desc: "Monitor delivery status, bounce rates, and open tracking from a live dashboard.",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  },
  {
    title: "Bring Your Own SMTP",
    desc: "Connect Resend, SendGrid, Mailgun, or any SMTP provider. Your domain, your reputation.",
    icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  },
  {
    title: "Excel & CSV Parsing",
    desc: "Upload recipient lists in any format. We auto-detect columns and validate email addresses.",
    icon: "M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z",
  },
  {
    title: "Secure & Private",
    desc: "Encrypted credentials, JWT auth, and no third-party data sharing. Your data stays yours.",
    icon: "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z",
  },
];

/* ───────────── PRICING data ───────────── */
const tiers = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    desc: "For individuals getting started",
    features: ["50 emails / month", "5 templates", "CSV upload", "Email tracking"],
    cta: "Get Started",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$19",
    period: "/mo",
    desc: "For teams and growing businesses",
    features: ["5,000 emails / month", "Unlimited templates", "AI composer", "PDF generation", "Priority support"],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    desc: "For large-scale operations",
    features: ["Unlimited emails", "Dedicated SMTP", "Custom integrations", "SLA guarantee", "Dedicated support"],
    cta: "Contact Us",
    highlighted: false,
  },
];

/* ═══════════════════════════════════════════════════════
   LANDING PAGE
   ═══════════════════════════════════════════════════════ */
export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: containerRef });
  const heroY = useTransform(scrollYProgress, [0, 0.25], [0, -120]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.18], [1, 0]);
  const smoothProgress = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });

  return (
    <div ref={containerRef} className="bg-white overflow-hidden">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md bg-white/80 border-b border-gray-100">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 h-16">
          <Link href="/" className="flex items-center gap-2.5">
            <LogoIcon size={32} />
            <div className="flex items-baseline">
              <span className="text-lg font-extrabold text-gray-900">Volley</span>
              <span className="text-lg font-extrabold text-green-800">Packet</span>
            </div>
          </Link>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How It Works</a>
            <a href="#pricing" className="hover:text-gray-900 transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="px-5 py-2 bg-green-800 text-white text-sm font-semibold rounded-full hover:bg-green-900 transition-colors shadow-sm"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <motion.section
        style={{ y: heroY, opacity: heroOpacity }}
        className="relative min-h-screen flex items-center justify-center pt-16 overflow-hidden"
      >
        {/* Background gradient blobs */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-green-200 rounded-full blur-3xl opacity-30 animate-pulse" />
          <div className="absolute bottom-32 right-1/4 w-80 h-80 bg-emerald-100 rounded-full blur-3xl opacity-40" />
        </div>

        <div className="max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          {/* Left — copy */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-green-50 border border-green-200 rounded-full text-sm font-medium text-green-800 mb-6">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              Now in v2.0
            </div>
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold text-gray-900 leading-[1.08] tracking-tight mb-6">
              Batch emails,
              <br />
              <span className="text-green-700">made simple.</span>
            </h1>
            <p className="text-lg md:text-xl text-gray-500 max-w-lg mb-8 leading-relaxed">
              Upload your recipients, design personalized emails and PDFs with AI, and send thousands in one click.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href="/signup"
                className="px-8 py-3.5 bg-green-800 text-white font-semibold rounded-full hover:bg-green-900 transition-all shadow-lg shadow-green-800/20 hover:shadow-xl hover:shadow-green-800/30 hover:-translate-y-0.5"
              >
                Start for Free
              </Link>
              <a
                href="#how-it-works"
                className="px-8 py-3.5 bg-white text-gray-700 font-semibold rounded-full border border-gray-200 hover:bg-gray-50 transition-all hover:-translate-y-0.5"
              >
                See How It Works
              </a>
            </div>
          </motion.div>

          {/* Right — 3D volleyball */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
            className="flex items-center justify-center"
          >
            <div className="relative">
              <Volleyball3D className="w-72 h-72 md:w-96 md:h-96" />
              {/* Floating badges */}
              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                className="absolute -top-4 -right-4 bg-white rounded-2xl shadow-xl px-4 py-3 border border-gray-100"
              >
                <p className="text-xs text-gray-400 font-medium">Emails sent</p>
                <p className="text-xl font-bold text-gray-900">12,847</p>
              </motion.div>
              <motion.div
                animate={{ y: [0, 8, 0] }}
                transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
                className="absolute -bottom-4 -left-4 bg-white rounded-2xl shadow-xl px-4 py-3 border border-gray-100"
              >
                <p className="text-xs text-gray-400 font-medium">Delivery rate</p>
                <p className="text-xl font-bold text-green-700">99.2%</p>
              </motion.div>
            </div>
          </motion.div>
        </div>

        {/* Scroll indicator */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2">
            <path d="M12 5v14M5 12l7 7 7-7" />
          </svg>
        </motion.div>
      </motion.section>

      {/* ── Social proof bar ── */}
      <Reveal>
        <section className="py-16 bg-gray-50 border-y border-gray-100">
          <div className="max-w-5xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <p className="text-3xl md:text-4xl font-extrabold text-gray-900">
                <Counter target={50000} suffix="+" />
              </p>
              <p className="text-sm text-gray-500 mt-1">Emails sent</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-extrabold text-gray-900">
                <Counter target={99} suffix="%" />
              </p>
              <p className="text-sm text-gray-500 mt-1">Delivery rate</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-extrabold text-gray-900">
                <Counter target={500} suffix="+" />
              </p>
              <p className="text-sm text-gray-500 mt-1">Active users</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-extrabold text-gray-900">
                <Counter target={10} suffix="K+" />
              </p>
              <p className="text-sm text-gray-500 mt-1">PDFs generated</p>
            </div>
          </div>
        </section>
      </Reveal>

      {/* ── Features ── */}
      <section id="features" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <Reveal>
            <div className="text-center mb-16">
              <span className="text-sm font-semibold text-green-700 uppercase tracking-wider">Features</span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mt-3">
                Everything you need to send at scale
              </h2>
              <p className="text-gray-500 mt-4 max-w-2xl mx-auto text-lg">
                From AI-powered composition to real-time delivery tracking — one platform for all your batch communication needs.
              </p>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <Reveal key={f.title} delay={i * 0.08}>
                <TiltCard className="h-full">
                  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-7 h-full hover:shadow-md transition-shadow">
                    <div className="w-12 h-12 rounded-xl bg-green-50 flex items-center justify-center text-green-700 mb-5">
                      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d={f.icon} />
                      </svg>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">{f.title}</h3>
                    <p className="text-gray-500 text-sm leading-relaxed">{f.desc}</p>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works (3D volleyball animation section) ── */}
      <section id="how-it-works" className="py-24 bg-gradient-to-b from-gray-50 to-white overflow-hidden">
        <div className="max-w-7xl mx-auto px-6">
          <Reveal>
            <div className="text-center mb-20">
              <span className="text-sm font-semibold text-green-700 uppercase tracking-wider">How It Works</span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mt-3">
                Three steps. That&apos;s it.
              </h2>
            </div>
          </Reveal>

          <div className="grid lg:grid-cols-2 gap-16 items-center">
            {/* Left — animated volleyball */}
            <Reveal>
              <div className="flex justify-center">
                <div className="relative">
                  <Volleyball3D className="w-64 h-64 md:w-80 md:h-80 volleyball-how-it-works" />

                  {/* Orbiting elements */}
                  <div className="absolute inset-0 animate-orbit">
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-white rounded-xl shadow-lg px-3 py-2 border border-gray-100">
                      <span className="text-xs font-semibold text-green-700">CSV</span>
                    </div>
                  </div>
                  <div className="absolute inset-0 animate-orbit-delayed">
                    <div className="absolute top-1/2 -right-8 -translate-y-1/2 bg-white rounded-xl shadow-lg px-3 py-2 border border-gray-100">
                      <span className="text-xs font-semibold text-green-700">PDF</span>
                    </div>
                  </div>
                  <div className="absolute inset-0 animate-orbit-delayed-2">
                    <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-white rounded-xl shadow-lg px-3 py-2 border border-gray-100">
                      <span className="text-xs font-semibold text-green-700">SMTP</span>
                    </div>
                  </div>
                </div>
              </div>
            </Reveal>

            {/* Right — steps */}
            <div className="space-y-10">
              {steps.map((step, i) => (
                <Reveal key={step.num} delay={i * 0.15}>
                  <div className="flex gap-5">
                    <div className="flex-shrink-0 w-14 h-14 rounded-2xl bg-green-800 flex items-center justify-center text-white shadow-lg shadow-green-800/20">
                      {step.icon}
                    </div>
                    <div>
                      <span className="text-xs font-bold text-green-600 uppercase tracking-wider">Step {step.num}</span>
                      <h3 className="text-xl font-bold text-gray-900 mt-1 mb-2">{step.title}</h3>
                      <p className="text-gray-500 leading-relaxed">{step.desc}</p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Pricing ── */}
      <section id="pricing" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <Reveal>
            <div className="text-center mb-16">
              <span className="text-sm font-semibold text-green-700 uppercase tracking-wider">Pricing</span>
              <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mt-3">
                Simple, transparent pricing
              </h2>
              <p className="text-gray-500 mt-4 max-w-xl mx-auto text-lg">
                Start free. Upgrade when you&apos;re ready. No hidden fees.
              </p>
            </div>
          </Reveal>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {tiers.map((tier, i) => (
              <Reveal key={tier.name} delay={i * 0.1}>
                <TiltCard className="h-full">
                  <div
                    className={`relative rounded-2xl border p-8 h-full flex flex-col ${
                      tier.highlighted
                        ? "border-green-600 bg-green-800 text-white shadow-2xl shadow-green-800/20 scale-[1.02]"
                        : "border-gray-200 bg-white shadow-sm"
                    }`}
                  >
                    {tier.highlighted && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-green-500 text-white text-xs font-bold px-4 py-1 rounded-full shadow-md">
                        Most Popular
                      </div>
                    )}
                    <h3 className={`text-lg font-bold ${tier.highlighted ? "text-green-100" : "text-gray-900"}`}>
                      {tier.name}
                    </h3>
                    <p className={`text-sm mt-1 ${tier.highlighted ? "text-green-200" : "text-gray-500"}`}>
                      {tier.desc}
                    </p>
                    <div className="mt-6 mb-8">
                      <span className={`text-4xl font-extrabold ${tier.highlighted ? "text-white" : "text-gray-900"}`}>
                        {tier.price}
                      </span>
                      {tier.period && (
                        <span className={`text-sm ${tier.highlighted ? "text-green-200" : "text-gray-500"}`}>
                          {tier.period}
                        </span>
                      )}
                    </div>
                    <ul className="space-y-3 flex-1">
                      {tier.features.map((feat) => (
                        <li key={feat} className="flex items-start gap-2.5 text-sm">
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            className={`flex-shrink-0 mt-0.5 ${tier.highlighted ? "stroke-green-300" : "stroke-green-600"}`}
                            strokeWidth="2.5"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          <span className={tier.highlighted ? "text-green-100" : "text-gray-600"}>{feat}</span>
                        </li>
                      ))}
                    </ul>
                    <Link
                      href="/signup"
                      className={`mt-8 block text-center py-3 rounded-full font-semibold text-sm transition-all hover:-translate-y-0.5 ${
                        tier.highlighted
                          ? "bg-white text-green-800 hover:bg-green-50 shadow-lg"
                          : "bg-green-800 text-white hover:bg-green-900 shadow-sm"
                      }`}
                    >
                      {tier.cta}
                    </Link>
                  </div>
                </TiltCard>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA banner ── */}
      <Reveal>
        <section className="py-24 bg-gradient-to-br from-green-800 to-green-950 text-white overflow-hidden relative">
          <div className="absolute inset-0 -z-0 opacity-10">
            <div className="absolute top-10 left-10 w-72 h-72 border border-white/20 rounded-full" />
            <div className="absolute bottom-10 right-10 w-96 h-96 border border-white/20 rounded-full" />
          </div>
          <div className="max-w-3xl mx-auto px-6 text-center relative z-10">
            <h2 className="text-3xl md:text-5xl font-extrabold mb-6">
              Ready to send smarter?
            </h2>
            <p className="text-green-100 text-lg mb-10 max-w-xl mx-auto">
              Join hundreds of businesses using VolleyPacket to send batch emails, generate PDFs, and manage communications — effortlessly.
            </p>
            <Link
              href="/signup"
              className="inline-flex px-10 py-4 bg-white text-green-800 font-bold rounded-full hover:bg-green-50 transition-all shadow-xl hover:shadow-2xl hover:-translate-y-1 text-lg"
            >
              Get Started for Free
            </Link>
          </div>
        </section>
      </Reveal>

      {/* ── Footer ── */}
      <footer className="bg-gray-900 text-gray-400 py-16">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-10">
            {/* Brand */}
            <div className="md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <LogoIcon size={28} />
                <div className="flex items-baseline">
                  <span className="text-base font-extrabold text-white">Volley</span>
                  <span className="text-base font-extrabold text-green-400">Packet</span>
                </div>
              </div>
              <p className="text-sm leading-relaxed">
                The modern batch email and document generation platform.
              </p>
            </div>

            {/* Links */}
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Documentation</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API Reference</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Setup Guides</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold text-sm mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
              </ul>
            </div>
          </div>

          <div className="border-t border-gray-800 mt-12 pt-8 text-sm text-center">
            &copy; {new Date().getFullYear()} VolleyPacket. All rights reserved.
          </div>
        </div>
      </footer>

      {/* ── Scroll progress bar ── */}
      <motion.div
        style={{ scaleX: smoothProgress }}
        className="fixed top-0 left-0 right-0 h-1 bg-green-600 origin-left z-[60]"
      />
    </div>
  );
}
