import { useEffect } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import capsule from "@/assets/capsule.png";
import gear from "@/assets/gear.png";
import { AppHeader } from "@/app/components/app-header";

function HomeIcon() {
  return (
    <svg
      className="h-4 w-4 flex-shrink-0 opacity-75"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 9.75 12 3l9 6.75V21a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V9.75Z"
      />
    </svg>
  );
}

const TOP_NAV = [
  { to: "/", label: "Panel główny", icon: <HomeIcon />, end: true },
  { to: "/cabinet", label: "Apteczka", icon: capsule },
];
const BOTTOM_NAV = [{ to: "/settings", label: "Ustawienia", icon: gear }];

function SidebarLink({
  to,
  label,
  icon,
  end,
  onClick,
}: {
  to: string;
  label: string;
  icon: string | ReactNode;
  end?: boolean;
  onClick?: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        [
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-slate-700 text-white"
            : "text-slate-400 hover:bg-slate-700/60 hover:text-white",
        ].join(" ")
      }
    >
      {typeof icon === "string" ? (
        <img src={icon} alt="" className="h-4 w-4 flex-shrink-0 opacity-75" />
      ) : (
        icon
      )}
      {label}
    </NavLink>
  );
}

interface AppSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

function SidebarContent({
  onClose,
  showHeader,
}: {
  onClose: () => void;
  showHeader?: boolean;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden px-3 py-4">
      {showHeader && (
        <div className="mb-4 border-b border-slate-700 px-1 pb-3">
          <AppHeader />
        </div>
      )}
      <nav className="flex flex-1 flex-col gap-0.5">
        {TOP_NAV.map((item) => (
          <SidebarLink key={item.to} {...item} onClick={onClose} />
        ))}
      </nav>
      <div className="border-t border-slate-700 pt-3">
        <nav className="flex flex-col gap-0.5">
          {BOTTOM_NAV.map((item) => (
            <SidebarLink key={item.to} {...item} onClick={onClose} />
          ))}
        </nav>
      </div>
    </div>
  );
}

export function AppSidebar({ isOpen, onClose }: AppSidebarProps) {
  const location = useLocation();

  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-52 flex-shrink-0 flex-col overflow-hidden border-r border-slate-700 bg-slate-800">
        <SidebarContent onClose={onClose} />
      </aside>

      {/* Mobile drawer overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
            aria-hidden="true"
          />
          <aside className="absolute left-0 top-0 h-full w-52 bg-slate-800 shadow-xl">
            <SidebarContent onClose={onClose} showHeader />
          </aside>
        </div>
      )}
    </>
  );
}
