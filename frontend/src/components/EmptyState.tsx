export default function EmptyState({
  icon = "🍡", title, hint,
}: { icon?: string; title: string; hint?: React.ReactNode }) {
  return (
    <div className="card-padded text-center py-10 space-y-2">
      <div className="text-4xl">{icon}</div>
      <div className="text-ink-700 font-medium">{title}</div>
      {hint && <div className="text-sm text-ink-500">{hint}</div>}
    </div>
  );
}
