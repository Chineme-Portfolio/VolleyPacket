import Link from "next/link";

const settingSections = [
  {
    title: "Profile",
    description: "Set your display name and avatar, and manage your account.",
    href: "/profile",
    icon: ProfileIcon,
  },
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
    </div>
  );
}

function ProfileIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#047857" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
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
