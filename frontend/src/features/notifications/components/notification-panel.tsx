import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  useNotifications,
  useDismissNotification,
  useDismissAllNotifications,
} from "@/features/notifications/api/notifications-queries";
import type { NotificationItem } from "@/features/notifications/api/notifications-api";

interface NotificationPanelProps {
  anchorRef: RefObject<HTMLDivElement | null>;
  onClose: () => void;
}

function dayWord(days: number | null): string {
  return days === 1 ? "dzień" : "dni";
}

// Narrows the cabinet-page navigation beyond a bare name match so entries
// that share a name but didn't trigger this alert (e.g. a second, healthy
// package of the same medication) are excluded from the filtered view.
// Reuses the cabinet page's existing status/below_minimum/sufficiency
// filters — no new query param, no backend change.
function triggerFilterParams(item: NotificationItem): URLSearchParams {
  const params = new URLSearchParams();
  params.set("search", item.medication_name);
  switch (item.trigger_type) {
    case "expiry":
      params.set(
        "status",
        item.days_remaining != null && item.days_remaining < 0
          ? "expired"
          : "expiring",
      );
      break;
    case "below_minimum":
      params.set("below_minimum", "true");
      break;
    case "run_out":
      params.set("sufficiency", "insufficient");
      break;
  }
  return params;
}

function rowLabel(item: NotificationItem): string {
  switch (item.trigger_type) {
    case "expiry":
      if (item.days_remaining != null && item.days_remaining < 0) {
        return "Termin ważności minął";
      }
      return `Termin ważności kończy się za ${item.days_remaining} ${dayWord(item.days_remaining)}`;
    case "below_minimum":
      return "Liczba opakowań poniżej minimalnej wartości";
    case "run_out":
      return `Zabraknie za ${item.days_remaining} ${dayWord(item.days_remaining)}`;
  }
}

export function NotificationPanel({
  anchorRef,
  onClose,
}: NotificationPanelProps) {
  const { data } = useNotifications();
  const dismissMutation = useDismissNotification();
  const dismissAllMutation = useDismissAllNotifications();
  const navigate = useNavigate();
  const [position, setPosition] = useState<{
    top: number;
    right: number;
  } | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const computePosition = () => {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (!rect) return;
      const margin = 16;
      const panelWidth = Math.min(320, window.innerWidth - margin * 2);
      const maxRight = window.innerWidth - panelWidth - margin;
      const desiredRight = window.innerWidth - rect.right;
      setPosition({
        top: rect.bottom + 8,
        right: Math.min(Math.max(desiredRight, margin), maxRight),
      });
    };
    computePosition();
    window.addEventListener("resize", computePosition);
    return () => window.removeEventListener("resize", computePosition);
  }, [anchorRef]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      const insideAnchor = anchorRef.current?.contains(target) ?? false;
      const insidePanel = panelRef.current?.contains(target) ?? false;
      if (!insideAnchor && !insidePanel) {
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onMouseDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onMouseDown);
    };
  }, [onClose, anchorRef]);

  if (!position) return null;

  const items = data?.items ?? [];

  return createPortal(
    <div
      ref={panelRef}
      role="dialog"
      aria-label="Powiadomienia"
      className="fixed z-50 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-600 bg-slate-800 p-3 shadow-xl"
      style={{ top: position.top, right: position.right }}
    >
      {items.length === 0 ? (
        <p className="py-4 text-center text-sm text-slate-400">
          Brak powiadomień
        </p>
      ) : (
        <>
          <div className="mb-2 flex items-center justify-end">
            <button
              type="button"
              onClick={() => dismissAllMutation.mutate(items)}
              disabled={dismissAllMutation.isPending}
              className="text-xs font-medium text-blue-400 hover:text-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Odrzuć wszystkie
            </button>
          </div>
          <ul className="flex max-h-[70vh] flex-col gap-2 overflow-y-auto">
            {items.map((item) => (
              <li
                key={`${item.cabinet_entry_id}-${item.trigger_type}`}
                className="flex items-start justify-between gap-2 rounded border border-slate-700 bg-slate-900 p-2"
              >
                <button
                  type="button"
                  aria-label={`Pokaż w apteczce: ${item.medication_name}`}
                  onClick={() => {
                    navigate(`/cabinet?${triggerFilterParams(item)}`);
                    onClose();
                  }}
                  className="min-w-0 flex-1 cursor-pointer text-left"
                >
                  <p className="truncate text-sm font-medium text-white">
                    {item.medication_name}
                  </p>
                  <p className="text-xs text-slate-400">{rowLabel(item)}</p>
                </button>
                <button
                  type="button"
                  aria-label={`Odrzuć powiadomienie: ${item.medication_name}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    dismissMutation.mutate({
                      cabinet_entry_id: item.cabinet_entry_id,
                      trigger_type: item.trigger_type,
                    });
                  }}
                  className="shrink-0 rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-white"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>,
    document.body,
  );
}
