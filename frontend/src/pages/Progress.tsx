import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getProgress } from "../lib/api";

export default function Progress() {
  const { data, isLoading } = useQuery({ queryKey: ["progress"], queryFn: getProgress });
  if (isLoading || !data) return <Loading />;

  const grammarPct = data.grammar.total_curated
    ? Math.round(100 * data.grammar.mastered / data.grammar.total_curated)
    : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">进度</h1>

      <section className="grid grid-cols-3 gap-4">
        <Stat label="连续打卡">{data.streak} 天</Stat>
        <Stat label="复习中的词汇">{data.vocab.in_srs} / {data.vocab.total}</Stat>
        <Stat label="语法掌握度">
          {data.grammar.mastered} / {data.grammar.total_curated}
          <span className="text-sm text-slate-500 ml-1">（{grammarPct}%）</span>
        </Stat>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">训练历史</h2>
        {data.history.length === 0 ? (
          <div className="text-slate-500">还没有训练记录。</div>
        ) : (
          <table className="w-full text-sm bg-white border rounded">
            <thead className="text-slate-500 text-xs">
              <tr>
                <th className="text-left p-2">日期</th>
                <th className="text-right p-2">复习词汇</th>
                <th className="text-right p-2">复习语法</th>
                <th className="text-right p-2">精读行数</th>
              </tr>
            </thead>
            <tbody>
              {data.history.map((h) => (
                <tr key={h.date} className="border-t">
                  <td className="p-2">{h.date}{h.completed && " ✓"}</td>
                  <td className="p-2 text-right">{h.vocab_reviewed}</td>
                  <td className="p-2 text-right">{h.grammar_reviewed}</td>
                  <td className="p-2 text-right">{h.lines_read}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{children}</div>
    </div>
  );
}
