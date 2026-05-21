"use client";

import { useAuth } from "@/lib/auth";

interface TopbarProps {
  onMenuToggle: () => void;
}

export default function Topbar({ onMenuToggle }: TopbarProps) {
  const { user, logout } = useAuth();

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "VP";

  return (
    <header className="h-14 sm:h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 sm:px-6 lg:px-8">
      {/* Left: hamburger + search */}
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

        {/* Search */}
        <div className="hidden sm:flex items-center gap-2 bg-gray-100 rounded-xl px-4 py-2 w-full max-w-xs lg:max-w-sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search..."
            className="bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none flex-1 min-w-0"
          />
        </div>
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

        {/* User */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-green-700 flex items-center justify-center text-white text-sm font-semibold">
            {initials}
          </div>
          <div className="hidden lg:block">
            <p className="text-sm font-semibold text-gray-900 max-w-[160px] truncate">
              {user?.email || "VolleyPacket"}
            </p>
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
