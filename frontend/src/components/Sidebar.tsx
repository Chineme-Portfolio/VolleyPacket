"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoCompact } from "@/components/Logo";

const menuItems = [
  { name: "Dashboard", href: "/dashboard", icon: DashboardIcon },
  { name: "Jobs", href: "/jobs", icon: JobsIcon },
  { name: "Templates", href: "/templates", icon: TemplatesIcon },
];

const generalItems = [
  { name: "Settings", href: "/settings", icon: SettingsIcon },
  { name: "Billing", href: "/settings/billing", icon: BillingIcon },
  { name: "Setup Guides", href: "/guides", icon: GuidesIcon },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-white border-r border-gray-200 flex flex-col z-10">
      {/* Logo */}
      <div className="px-5 py-5">
        <Link href="/dashboard">
          <LogoCompact />
        </Link>
      </div>

      {/* Menu */}
      <nav className="flex-1 px-4 mt-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 mb-3">Menu</p>
        <ul className="space-y-1">
          {menuItems.map((item) => {
            const isActive = pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-green-800 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  <item.icon active={isActive} />
                  {item.name}
                </Link>
              </li>
            );
          })}
        </ul>

        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 mb-3 mt-8">General</p>
        <ul className="space-y-1">
          {generalItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-green-800 text-white"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  <item.icon active={isActive} />
                  {item.name}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

function DashboardIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function JobsIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
      <path d="M9 14l2 2 4-4" />
    </svg>
  );
}

function TemplatesIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
      <path d="M10 9H8" />
    </svg>
  );
}

function SettingsIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function BillingIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  );
}

function GuidesIcon({ active }: { active: boolean }) {
  const color = active ? "white" : "#6b7280";
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  );
}
