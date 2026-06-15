"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import Avatar from "@/components/Avatar";

interface TopbarProps {
  onMenuToggle: () => void;
}

export default function Topbar({ onMenuToggle }: TopbarProps) {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 sm:h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Left: hamburger */}
      <div className="flex items-center gap-3 flex-1 min-w-0">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 -ml-1 rounded-xl hover:bg-gray-100 transition-colors flex-shrink-0"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2" strokeLinecap="round">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 sm:gap-5 flex-shrink-0">
        {/* Notification bell */}
        <button className="relative p-2 rounded-xl hover:bg-gray-100 transition-colors">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>

        {/* User → profile */}
        <div className="flex items-center gap-3">
          <Link href="/profile" title="Your profile" className="flex-shrink-0">
            <Avatar avatar={user?.avatar} name={user?.username || user?.email} userId={user?.id} size={36} />
          </Link>
          <div className="hidden lg:block leading-tight">
            <Link href="/profile">
              <p className="text-sm font-semibold text-gray-900 max-w-[160px] truncate hover:text-green-800 transition-colors">
                {user?.username || user?.email || "VolleyPacket"}
              </p>
            </Link>
            <button
              onClick={logout}
              className="text-xs text-gray-500 hover:text-red-600 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
