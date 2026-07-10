import { Link } from "react-router-dom";
import totalIcon from "@/assets/total.png";
import activeIcon from "@/assets/active.png";
import expiringIcon from "@/assets/expiring.png";
import expiredIcon from "@/assets/expired.png";
import outOfStockIcon from "@/assets/out-of-stock.png";
import type { SummaryCardAccent } from "@/features/dashboard/components/summary-cards.config";

const ACCENT_CLASSES: Record<SummaryCardAccent, string> = {
  total: "bg-slate-800/60 border-slate-700 text-white",
  valid: "bg-green-950/40 border-green-900 text-green-400",
  expiring: "bg-orange-950/40 border-orange-900 text-orange-400",
  expired: "bg-red-950/40 border-red-900 text-red-400",
  out_of_stock: "bg-amber-950/40 border-amber-900 text-amber-400",
};

const ACCENT_ICONS: Record<SummaryCardAccent, string> = {
  total: totalIcon,
  valid: activeIcon,
  expiring: expiringIcon,
  expired: expiredIcon,
  out_of_stock: outOfStockIcon,
};

interface SummaryCardProps {
  label: string;
  count: number;
  to: string;
  accent: SummaryCardAccent;
}

export function SummaryCard({ label, count, to, accent }: SummaryCardProps) {
  return (
    <Link
      to={to}
      className={`relative flex min-h-[84px] w-full min-w-[160px] flex-col justify-center gap-1 rounded-lg border p-4 transition-colors hover:brightness-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 md:min-h-[176px] md:justify-start md:p-5 md:pb-20 md:pr-20 ${ACCENT_CLASSES[accent]}`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-3xl font-semibold md:text-4xl">{count}</span>
        <img
          src={ACCENT_ICONS[accent]}
          alt=""
          className="pointer-events-none h-9 w-9 flex-shrink-0 opacity-90 md:hidden"
        />
      </div>
      <span className="max-w-[70%] text-sm text-slate-300 md:max-w-none">
        {label}
      </span>
      <img
        src={ACCENT_ICONS[accent]}
        alt=""
        className="pointer-events-none absolute bottom-2 right-2 hidden h-14 w-14 opacity-90 md:block"
      />
    </Link>
  );
}
