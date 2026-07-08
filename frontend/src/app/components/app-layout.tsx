import { useState, useCallback } from "react";
import type { ReactNode } from "react";
import { AppSidebar } from "@/app/components/app-sidebar";
import { AppHeader } from "@/app/components/app-header";
import { AppFooter } from "@/app/components/app-footer";
import { LogoutButton } from "@/features/auth/components/logout-button";
import { NotificationBell } from "@/features/notifications/components/notification-bell";

interface AppLayoutProps {
  children: ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <div className="flex h-dvh flex-col bg-slate-900">
      {/* Top header — full width */}
      <header className="flex flex-shrink-0 items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded p-1.5 text-slate-400 hover:bg-slate-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 md:hidden"
            aria-label="Otwórz menu"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <AppHeader />
        </div>
        <div className="flex items-center gap-2">
          <NotificationBell />
          <LogoutButton />
        </div>
      </header>

      {/* Body: sidebar + content */}
      <div className="flex flex-1 overflow-hidden">
        <AppSidebar isOpen={sidebarOpen} onClose={closeSidebar} />

        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 flex-col min-h-0 px-6 py-8">
            {children}
          </div>
          <AppFooter />
        </main>
      </div>
    </div>
  );
}
