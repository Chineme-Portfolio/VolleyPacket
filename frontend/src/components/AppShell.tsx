"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";

const PUBLIC_PAGES = ["/login", "/signup", "/"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Auth pages — no sidebar/topbar
  if (PUBLIC_PAGES.includes(pathname)) {
    return <>{children}</>;
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-100">
        <div className="w-10 h-10 border-4 border-green-700 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Authenticated layout
  return (
    <div className="flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col ml-0 lg:ml-60 min-w-0 overflow-hidden">
        <Topbar onMenuToggle={() => setSidebarOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto min-w-0">{children}</main>
      </div>
    </div>
  );
}
