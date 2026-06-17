interface StatusBadgeProps {
  status: { label: string; pillClassName: string };
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.pillClassName}`}
    >
      {status.label}
    </span>
  );
}
