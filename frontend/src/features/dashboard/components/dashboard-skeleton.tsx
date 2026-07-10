export function DashboardSkeleton() {
  return (
    <div
      className="mx-auto grid w-full max-w-6xl grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4"
      role="status"
      aria-label="Ładowanie panelu głównego"
    >
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="flex min-h-[84px] w-full animate-pulse flex-col justify-end gap-2 rounded-lg border border-slate-700 bg-slate-800/60 p-4 md:min-h-[176px] md:p-5"
        >
          <div className="h-7 w-12 rounded bg-slate-700" />
          <div className="h-4 w-20 rounded bg-slate-700" />
        </div>
      ))}
    </div>
  );
}
