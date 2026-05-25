import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getProgress } from "../lib/api";

export default function Progress() {
  const { data, isLoading } = useQuery({ queryKey: ["progress"], queryFn: getProgress });
  if (isLoading || !data) return <Loading />;

  const grammarPct = data.grammar.total_curated
    ? Math.round(100 * data.grammar.mastered / data.grammar.total_curated)
    : 0;

  // Build a 30-day heatmap from history
  const today = new Date();
  const completedDates = new Set(
    data.history.filter((h) => h.completed).map((h) => h.date),
  );
  const cells: { date: string; done: boolean }[] = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today); d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    cells.push({ date: iso, done: completedDates.has(iso) });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-ink-900">进度</h1>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="连续打卡" value={`${data.streak} 天`} accent="from-brand-500 to-sakura-500" />
        <Stat label="复习中的词汇" value={`${data.vocab.in_srs} / ${data.vocab.total}`} />
        <Stat label="语法掌握度" value={`${data.grammar.mastered} / ${data.grammar.total_curated}`} sub={`${grammarPct}%`} />
      </section>

      <section className="card-padded">
        <div className="text-sm font-semibold text-ink-800 mb-3">最近 30 天</div>
        <div className="grid grid-cols-[repeat(30,minmax(0,1fr))] gap-1">
          {cells.map((c) => (
            <div
              key={c.date}
              title={c.date + (c.done ? " ✓" : "")}
              className={`aspect-square rounded ${c.done ? "bg-brand-500" : "bg-ink-100"}`}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-ink-800 mb-2">训练历史</h2>
        {data.history.length === 0 ? (
          <div className="card-padded text-ink-500 text-center">还没有训练记录。</div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-ink-500 text-xs bg-ink-50">
                <tr>
                  <th className="text-left p-3">日期</th>
                  <th className="text-right p-3">复习词汇</th>
                  <th className="text-right p-3">复习语法</th>
                  <th className="text-right p-3">精读行数</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map((h) => (
                  <tr key={h.date} className="border-t border-ink-100">
                    <td className="p-3 ja">{h.date}{h.completed && " ✓"}</td>
                    <td className="p-3 text-right">{h.vocab_reviewed}</td>
                    <td className="p-3 text-right">{h.grammar_reviewed}</td>
                    <td className="p-3 text-right">{h.lines_read}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, sub, accent }:
  { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className={`card-padded ${accent ? `bg-gradient-to-br ${accent} text-white` : ""}`}>
      <div className={`text-sm ${accent ? "opacity-90" : "text-ink-500"}`}>{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && <div className={`text-xs mt-1 ${accent ? "opacity-85" : "text-ink-400"}`}>{sub}</div>}
    </div>
  );
}
