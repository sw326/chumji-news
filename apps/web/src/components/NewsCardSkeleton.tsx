export default function NewsCardSkeleton() {
  return (
    <div className="rounded-xl border border-card-border bg-card px-5 py-4 animate-pulse">
      <div className="flex items-center gap-2 mb-2.5">
        <div className="h-5 w-16 rounded-md bg-card-border" />
        <div className="h-4 w-10 rounded bg-card-border" />
      </div>
      <div className="h-4 w-3/4 rounded bg-card-border mb-1.5" />
      <div className="h-3 w-full rounded bg-card-border mb-1" />
      <div className="h-3 w-5/6 rounded bg-card-border" />
    </div>
  );
}
