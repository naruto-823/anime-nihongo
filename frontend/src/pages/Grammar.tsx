import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getChecklist } from "../lib/api";

const STATUS_COLOR: Record<string, string> = {
  locked: "bg-slate-100 text-slate-500",
  seen: "bg-amber-100 text-amber-700",
  learning: "bg-indigo-100 text-indigo-700",
};

export default function Grammar() {
  const { data, isLoading } = useQuery({
    queryKey: ["grammar-checklist"], queryFn: getChecklist,
  });
  if (isLoading || !data) return <Loading />;

  const levels = Object.keys(data).sort();
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">语法清单</h1>
      {levels.map((lv) => {
        const pts = data[lv];
        const mastered = pts.filter((p) => p.mastered).length;
        return (
          <section key={lv} className="space-y-2">
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-medium">{lv}</h2>
              <div className="text-sm text-slate-500">
                掌握 {mastered} / {pts.length}
              </div>
            </div>
            <ul className="grid grid-cols-2 gap-2">
              {pts.map((p) => (
                <li key={p.id}
                    className={`p-2 rounded text-sm flex items-center justify-between
                                ${p.mastered ? "bg-emerald-100 text-emerald-800"
                                              : STATUS_COLOR[p.status] ?? ""}`}>
                  <span>{p.name}</span>
                  <span className="text-xs">
                    {p.mastered ? "已掌握" : p.status === "learning" ? "学习中"
                      : p.status === "seen" ? "已遇到" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
