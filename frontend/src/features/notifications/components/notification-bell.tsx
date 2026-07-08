import { useState, useRef } from "react";
import { useNotifications } from "@/features/notifications/api/notifications-queries";
import { NotificationPanel } from "@/features/notifications/components/notification-panel";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data } = useNotifications();
  const count = data?.items.length ?? 0;
  const anchorRef = useRef<HTMLDivElement>(null);

  return (
    <div className="relative" ref={anchorRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="relative rounded p-1.5 text-slate-400 hover:bg-slate-700 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Powiadomienia"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {count > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-xs font-medium text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>
      {open && (
        <NotificationPanel
          anchorRef={anchorRef}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  );
}
