import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getChecklist } from "../lib/api";

export default function Grammar() {
  const { data, isLoading } = useQuery({
    queryKey: ["grammar-checklist"], queryFn: getChecklist,
  });
  if (isLoading || !data) return <Loading />;

  const levels = Object.keys(data).sort();
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-ink-900">语法清单</h1>
      {levels.map((lv) => {
        const pts = data[lv];
        const mastered = pts.filter((p) => p.mastered).length;
        const learning = pts.filter((p) => p.status === "learning").length;
        const seen = pts.filter((p) => p.status === "seen").length;
        return (
          <section key={lv} className="space-y-3">
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-semibold text-ink-800">
                {lv} <span className="text-ink-400 text-sm ml-1">{pts.length}</span>
              </h2>
              <div className="text-xs text-ink-500 flex gap-2">
                <span>✓ 掌握 {mastered}</span>
                <span>📖 学习 {learning}</span>
                <span>👁 遇到 {seen}</span>
              </div>
            </div>
            <ul className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {pts.map((p) => {
                const cls = p.mastered
                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                  : p.status === "learning"
                    ? "bg-brand-50 text-brand-800 border-brand-200"
                    : p.status === "seen"
                      ? "bg-amber-50 text-amber-800 border-amber-200"
                      : "bg-white text-ink-500 border-ink-200";
                return (
                  <li key={p.id}
                      className={`border rounded-lg px-3 py-2 text-sm flex items-center justify-between ${cls}`}>
                    <span className="ja truncate">{p.name}</span>
                    <span className="text-xs shrink-0 ml-2">
                      {p.mastered ? "✓" : p.status === "learning" ? "学" : p.status === "seen" ? "见" : "·"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
