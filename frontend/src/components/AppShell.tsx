"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";

const AUTH_PAGES = ["/login", "/signup"];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useAuth();

  // Auth pages — no sidebar/topbar
  if (AUTH_PAGES.includes(pathname)) {
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
      <Sidebar />
      <div className="flex-1 flex flex-col ml-60 min-w-0 overflow-hidden">
        <Topbar />
        <main className="flex-1 p-8 overflow-auto min-w-0">{children}</main>
      </div>
    </div>
  );
}
