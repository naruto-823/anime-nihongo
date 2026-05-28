import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import CharacterHeader from "../components/CharacterHeader";
import EmptyState from "../components/EmptyState";
import Loading from "../components/Loading";
import SceneTimeline from "../components/SceneTimeline";
import { getJourney } from "../lib/api";

export default function Today() {
  const { data, isLoading } = useQuery({
    queryKey: ["journey"],
    queryFn: getJourney,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      const ep = d.current_episode;
      if (ep && (ep.status === "processing" || ep.status === "importing")) {
        return 5000;
      }
      // AniList: poll only while genuinely pending, cap ~10 attempts (≈30s)
      if (d.series?.anilist_status === "pending" && q.state.dataUpdateCount < 11) {
        return 3000;
      }
      return false;
    },
  });

  if (isLoading || !data) return <Loading />;

  if (!data.series) {
    return (
      <EmptyState
        icon="📺"
        title="还没有番剧"
        hint={<>去 <Link to="/series" className="text-brand-600 hover:underline">导入你在追的第一部番 →</Link></>}
      />
    );
  }

  const ep = data.current_episode;
  const seriesTitle = data.series.title;

  const rightChip = (
    <div className="flex flex-col items-end gap-1 text-xs shrink-0">
      <span className="badge-amber">🔥 {data.streak} 天</span>
      {data.due_total > 0 ? (
        <Link to="/review" className="badge-brand hover:bg-brand-200">
          🧠 {data.due_total} 到期 →
        </Link>
      ) : (
        <span className="text-ink-400">无到期复习</span>
      )}
    </div>
  );

  const episodeLabel = ep
    ? `第 ${ep.number} 集 · ${ep.completed_scenes}/${ep.total_scenes} 通关 · ${ep.read_position}/${ep.total_lines} 行`
    : undefined;

  return (
    <div className="space-y-6">
      <CharacterHeader
        seriesTitle={seriesTitle}
        character={data.series.main_character}
        episodeLabel={episodeLabel}
        rightSlot={rightChip}
      />

      {!ep ? (
        <EmptyState
          icon="📚"
          title={`《${seriesTitle}》还没有任何一集`}
          hint={<>去 <Link to="/series" className="text-brand-600 hover:underline">导入第一集 →</Link></>}
        />
      ) : ep.status === "failed" ? (
        <div className="card-padded border-rose-200 bg-rose-50 text-rose-800 text-sm">
          本集加工失败。请到番剧库重新触发导入。
        </div>
      ) : ep.read_position >= ep.total_lines ? (
        <div className="card-padded border-emerald-200 bg-emerald-50 text-emerald-800 text-sm">
          本集已读完 · <Link to="/series" className="underline">开始下一集 →</Link>
        </div>
      ) : (
        <SceneTimeline episodeId={ep.id} scenes={data.scenes} />
      )}
    </div>
  );
}
