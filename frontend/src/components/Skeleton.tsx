export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SkeletonCard() {
  return (
    <div className="card-padded space-y-3">
      <Skeleton className="skeleton h-4 w-24" />
      <Skeleton className="skeleton h-6 w-3/4" />
      <Skeleton className="skeleton h-4 w-1/2" />
    </div>
  );
}
