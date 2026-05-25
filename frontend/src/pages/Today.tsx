import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Loading from "../components/Loading";
import { completeToday, getToday } from "../lib/api";

export default function Today() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["today"], queryFn: getToday });
  const complete = useMutation({
    mutationFn: () => completeToday({ episode_id: data?.current_episode?.id ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["today"] }),
  });

  if (isLoading || !data) return <Loading />;
  const ep = data.current_episode;

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">今日训练</h1>
        <div className="text-sm text-slate-600">
          连续打卡 <span className="font-semibold text-indigo-600">{data.streak}</span> 天
        </div>
      </header>

      <section className="grid grid-cols-2 gap-4">
        <Card title="到期复习">
          <div>词汇 <b>{data.due.vocab}</b></div>
          <div>语法 <b>{data.due.grammar}</b></div>
          <Link to="/review" className="text-indigo-600 text-sm">去复习 →</Link>
        </Card>
        <Card title="当前剧集">
          {ep ? (
            <>
              <div>第 {ep.number} 集 · {ep.read_position}/{ep.total_lines} 行
                {ep.reading_done && " · 精读已完成"}</div>
              <div className="flex gap-3 mt-2">
                <Link to={`/episodes/${ep.id}/reading`}
                      className="text-indigo-600 text-sm">精读 →</Link>
                <Link to={`/episodes/${ep.id}/conversation`}
                      className="text-indigo-600 text-sm">角色对话 →</Link>
              </div>
            </>
          ) : (
            <div>
              还没有当前番。<Link to="/series" className="text-indigo-600">先去导入一集 →</Link>
            </div>
          )}
        </Card>
      </section>

      <button
        onClick={() => complete.mutate()}
        className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
        disabled={complete.isPending}
      >
        {complete.isPending ? "保存中…" : "完成今日训练（打卡）"}
      </button>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded border p-4 space-y-1">
      <div className="text-sm text-slate-500">{title}</div>
      {children}
    </div>
  );
}
