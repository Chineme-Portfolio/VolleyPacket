"use client";

import { useState } from "react";
import Link from "next/link";

interface Guide {
  id: string;
  name: string;
  channel: "email" | "sms";
  type: "api" | "smtp";
  difficulty: "Easy" | "Medium";
  meta: string;
  steps: { title: string; content: string }[];
}

const guides: Guide[] = [
  // ── Email providers ──────────────────────────────────────────────
  {
    id: "resend",
    name: "Resend",
    channel: "email",
    type: "api",
    difficulty: "Easy",
    meta: "3,000 emails/month free",
    steps: [
      {
        title: "Create a Resend account",
        content: "Go to resend.com and sign up for a free account. No credit card required.",
      },
      {
        title: "Get your API key",
        content:
          "After signing in, go to API Keys in the left sidebar. Click \"Create API Key\", give it a name (e.g. \"VolleyPacket\"), and select \"Sending access\" permission. Copy the key — it starts with re_.",
      },
      {
        title: "Verify your domain (optional)",
        content:
          "By default you can send from onboarding@resend.dev. To send from your own domain, go to Domains > Add Domain and add the DNS records Resend gives you. This takes a few minutes to verify.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > Email Provider, select Resend, paste your API key, set your sender name and email, then click Save. Hit \"Send Test Email\" to verify it works.",
      },
    ],
  },
  {
    id: "sendgrid",
    name: "SendGrid",
    channel: "email",
    type: "api",
    difficulty: "Easy",
    meta: "100 emails/day free",
    steps: [
      {
        title: "Create a SendGrid account",
        content:
          "Go to sendgrid.com and sign up. You will need to verify your email and may need to complete account verification (takes up to 24 hours for new accounts).",
      },
      {
        title: "Create a Sender Identity",
        content:
          "Go to Settings > Sender Authentication. You can either verify a single sender email or authenticate your whole domain via DNS records. Single sender is faster to start.",
      },
      {
        title: "Generate an API key",
        content:
          "Go to Settings > API Keys > Create API Key. Choose \"Restricted Access\" and enable only \"Mail Send\". Copy the key — it starts with SG.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > Email Provider, select SendGrid, paste your API key, set your sender name and verified email, then click Save.",
      },
    ],
  },
  {
    id: "gmail",
    name: "Gmail SMTP",
    channel: "email",
    type: "smtp",
    difficulty: "Medium",
    meta: "~500 emails/day",
    steps: [
      {
        title: "Enable 2-Step Verification",
        content:
          "Go to myaccount.google.com > Security > 2-Step Verification and turn it on. This is required to create an App Password.",
      },
      {
        title: "Create an App Password",
        content:
          "Go to myaccount.google.com > Security > App Passwords (or search \"App Passwords\" in your Google account settings). Select \"Mail\" as the app, give it a name like \"VolleyPacket\", and click Generate. Copy the 16-character password shown.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > Email Provider, select Gmail SMTP. Enter your full Gmail address as the username and the App Password you just generated (not your regular Gmail password). Set sender email to your Gmail address.",
      },
    ],
  },
  {
    id: "zoho",
    name: "Zoho SMTP",
    channel: "email",
    type: "smtp",
    difficulty: "Medium",
    meta: "Included with Zoho Mail",
    steps: [
      {
        title: "Get a Zoho Mail account",
        content:
          "If you don't have one, sign up at zoho.com/mail. The free plan includes SMTP access. You will need to verify your domain.",
      },
      {
        title: "Enable SMTP access",
        content:
          "In Zoho Mail, go to Settings > Mail Accounts > your account > SMTP. Make sure SMTP access is enabled. If you have 2FA enabled, you will need to generate an App-Specific Password under Security > App Passwords.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > Email Provider, select Zoho SMTP. Enter your Zoho email as the username and your password (or App Password if 2FA is on). Set sender email to your Zoho address.",
      },
    ],
  },
  {
    id: "custom",
    name: "Custom SMTP",
    channel: "email",
    type: "smtp",
    difficulty: "Medium",
    meta: "Depends on provider",
    steps: [
      {
        title: "Get your SMTP credentials",
        content:
          "From your email provider, find the SMTP settings. You will need: SMTP host (e.g. smtp.example.com), port (usually 587 for TLS), username, and password.",
      },
      {
        title: "Common SMTP hosts",
        content:
          "Yahoo: smtp.mail.yahoo.com (port 587) | Outlook/Hotmail: smtp-mail.outlook.com (port 587) | Office 365: smtp.office365.com (port 587) | Amazon SES: email-smtp.us-east-1.amazonaws.com (port 587)",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > Email Provider, select Custom SMTP. Fill in the host, port, username, and password. Set your sender name and email, then Save and test.",
      },
    ],
  },

  // ── SMS providers ────────────────────────────────────────────────
  {
    id: "bulksms",
    name: "BulkSMS Nigeria",
    channel: "sms",
    type: "api",
    difficulty: "Easy",
    meta: "Nigeria · pay-as-you-go",
    steps: [
      {
        title: "Create a BulkSMS account",
        content: "Sign up at bulksmsnigeria.com and fund your wallet (SMS is pay-as-you-go).",
      },
      {
        title: "Get your API token",
        content:
          "In the dashboard, open Developers / API and copy your API token. Keep it secret — it's your sending credential.",
      },
      {
        title: "Register a Sender ID",
        content:
          "Under Sender IDs, register the name recipients will see (e.g. your business name) and wait for approval. Unapproved sender IDs are rejected.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > SMS Provider, select BulkSMS Nigeria, paste your API token, set your approved Sender ID, choose your default country, Save, then Send Test SMS.",
      },
    ],
  },
  {
    id: "twilio",
    name: "Twilio",
    channel: "sms",
    type: "api",
    difficulty: "Medium",
    meta: "Global · free trial credit",
    steps: [
      {
        title: "Create a Twilio account",
        content:
          "Sign up at twilio.com — new accounts get trial credit. Note: trial accounts can only text numbers you've verified until you upgrade.",
      },
      {
        title: "Get a phone number",
        content:
          "In Console > Phone Numbers > Buy a number, get an SMS-capable number. It will be in E.164 form (e.g. +1...). This is your Sender ID.",
      },
      {
        title: "Copy your Account SID and Auth Token",
        content:
          "On the Twilio Console dashboard (console.twilio.com) copy your Account SID and Auth Token (the Auth Token is your secret).",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > SMS Provider, select Twilio, paste the Account SID and Auth Token, set the Sender ID to your Twilio number, Save, then Send Test SMS.",
      },
    ],
  },
  {
    id: "vonage",
    name: "Vonage (Nexmo)",
    channel: "sms",
    type: "api",
    difficulty: "Medium",
    meta: "Global · free trial credit",
    steps: [
      {
        title: "Create a Vonage account",
        content: "Sign up at vonage.com (Communications APIs). New accounts include trial credit.",
      },
      {
        title: "Copy your API key and secret",
        content: "From the dashboard home (dashboard.nexmo.com), copy your API key and API secret.",
      },
      {
        title: "Choose a Sender ID",
        content:
          "Use an approved alphanumeric sender ID (where the destination country allows it) or buy a Vonage number to send from.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > SMS Provider, select Vonage, paste your API key and secret, set your Sender ID, Save, then Send Test SMS.",
      },
    ],
  },
  {
    id: "termii",
    name: "Termii",
    channel: "sms",
    type: "api",
    difficulty: "Medium",
    meta: "Africa · pay-as-you-go",
    steps: [
      {
        title: "Create a Termii account",
        content: "Sign up at termii.com and fund your wallet.",
      },
      {
        title: "Get your API key",
        content: "In accounts.termii.com > Settings > API, copy your API key.",
      },
      {
        title: "Register a Sender ID",
        content:
          "Request a Sender ID and wait for approval — it's required before you can send live messages.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > SMS Provider, select Termii, paste your API key, set your approved Sender ID, Save, then Send Test SMS.",
      },
    ],
  },
  {
    id: "africastalking",
    name: "Africa's Talking",
    channel: "sms",
    type: "api",
    difficulty: "Medium",
    meta: "Africa · sandbox + live",
    steps: [
      {
        title: "Create an account",
        content: "Sign up at africastalking.com and create an app from the dashboard.",
      },
      {
        title: "Get your username and API key",
        content:
          "Copy your app's username (use \"sandbox\" for testing) and generate an API key under Settings > API Key.",
      },
      {
        title: "Sender ID / short code (optional)",
        content:
          "For production, request an alphanumeric Sender ID or short code. The sandbox uses a default sender, so you can skip this while testing.",
      },
      {
        title: "Add to VolleyPacket",
        content:
          "Go to Settings > SMS Provider, select Africa's Talking, enter your username and API key, optionally a Sender ID, Save, then Send Test SMS.",
      },
    ],
  },
];

export default function GuidesPage() {
  const [activeGuide, setActiveGuide] = useState<string | null>(null);

  const selected = guides.find((g) => g.id === activeGuide);
  const emailGuides = guides.filter((g) => g.channel === "email");
  const smsGuides = guides.filter((g) => g.channel === "sms");

  const renderCard = (guide: Guide) => (
    <button
      key={guide.id}
      onClick={() => setActiveGuide(activeGuide === guide.id ? null : guide.id)}
      className={`text-left p-5 rounded-2xl border-2 transition-all ${
        activeGuide === guide.id
          ? "border-green-700 bg-green-50 shadow-sm"
          : "border-gray-100 bg-white hover:border-gray-200"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">{guide.name}</h3>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
            guide.type === "api" ? "bg-blue-100 text-blue-700" : "bg-orange-100 text-orange-700"
          }`}
        >
          {guide.type === "api" ? "API" : "SMTP"}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span>Difficulty: {guide.difficulty}</span>
        <span>{guide.meta}</span>
      </div>
    </button>
  );

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Setup Guides</h1>
          <p className="text-gray-500 mt-1 text-sm">Step-by-step instructions for connecting your email and SMS services.</p>
        </div>
        <Link
          href="/settings"
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-xl hover:bg-gray-50 transition-colors self-start"
        >
          Settings
        </Link>
      </div>

      {/* Email providers */}
      <h2 className="text-lg font-semibold text-gray-900 mb-3">Email providers</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {emailGuides.map(renderCard)}
      </div>

      {/* SMS providers */}
      <h2 className="text-lg font-semibold text-gray-900 mb-3">SMS providers</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        {smsGuides.map(renderCard)}
      </div>

      {/* Expanded guide */}
      {selected && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 sm:p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900">{selected.name} Setup</h2>
            <span className="text-sm text-gray-500">{selected.steps.length} steps</span>
          </div>

          <div className="space-y-6">
            {selected.steps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-800 text-white flex items-center justify-center text-sm font-bold">
                  {i + 1}
                </div>
                <div className="flex-1 pt-1">
                  <h3 className="text-base font-semibold text-gray-900 mb-1">{step.title}</h3>
                  <p className="text-sm text-gray-600 leading-relaxed">{step.content}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-gray-100 flex items-center gap-3">
            <Link
              href={selected.channel === "sms" ? "/settings/sms" : "/settings/email"}
              className="px-6 py-2.5 bg-green-800 text-white text-sm font-medium rounded-xl hover:bg-green-900 transition-colors"
            >
              Configure {selected.name}
            </Link>
            <button
              onClick={() => setActiveGuide(null)}
              className="px-6 py-2.5 text-gray-600 text-sm font-medium hover:text-gray-800 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
