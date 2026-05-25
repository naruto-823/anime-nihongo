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
      {/* Hero: streak focal */}
      <div className="card-padded bg-gradient-to-br from-brand-600 to-sakura-500 text-white">
        <div className="text-sm opacity-90">连续打卡</div>
        <div className="flex items-baseline gap-2 mt-1">
          <div className="text-5xl font-bold leading-none">{data.streak}</div>
          <div className="text-xl opacity-90">天 🔥</div>
        </div>
        <div className="text-sm opacity-85 mt-3">
          今天还有 <b>{data.due.vocab}</b> 个词、<b>{data.due.grammar}</b> 个语法到期。
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 复习卡 */}
        <div className="card-padded card-hover space-y-3">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-ink-800">SRS 复习</div>
            <span className="badge-brand">{data.due.vocab + data.due.grammar} 项到期</span>
          </div>
          <div className="text-sm text-ink-600">
            词汇 <b className="text-ink-800">{data.due.vocab}</b>
            <span className="mx-2 text-ink-300">/</span>
            语法 <b className="text-ink-800">{data.due.grammar}</b>
          </div>
          <Link to="/review" className="btn-primary btn-sm inline-flex">去复习 →</Link>
        </div>

        {/* 当前剧集卡 */}
        <div className="card-padded card-hover space-y-3">
          <div className="font-semibold text-ink-800">当前剧集</div>
          {ep ? (
            <>
              <div className="text-sm text-ink-600">
                第 {ep.number} 集 · <b className="text-ink-800">{ep.read_position}/{ep.total_lines}</b> 行
                {ep.reading_done && <span className="badge-emerald ml-2">精读完成</span>}
              </div>
              <div className="flex gap-2">
                <Link to={`/episodes/${ep.id}/reading`} className="btn-primary btn-sm">📖 精读</Link>
                <Link to={`/episodes/${ep.id}/conversation`} className="btn-secondary btn-sm">💬 角色对话</Link>
              </div>
            </>
          ) : (
            <div className="text-sm text-ink-600">
              还没有当前番。<Link to="/series" className="text-brand-600 hover:underline">先去导入一集 →</Link>
            </div>
          )}
        </div>
      </div>

      <button
        onClick={() => complete.mutate()}
        className="btn-primary"
        disabled={complete.isPending}
      >
        {complete.isPending ? "保存中…" : "✓ 完成今日训练（打卡）"}
      </button>
    </div>
  );
}
