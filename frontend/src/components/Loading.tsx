import { Skeleton, SkeletonCard } from "./Skeleton";

export default function Loading({ kind = "card" }: { kind?: "card" | "inline" }) {
  if (kind === "inline") {
    return <div className="text-ink-500 py-8 text-center">加载中…</div>;
  }
  return (
    <div className="space-y-4">
      <Skeleton className="skeleton h-8 w-40" />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  );
}
