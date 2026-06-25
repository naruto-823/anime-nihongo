import { useNavigate } from "react-router-dom";

import type { SceneNode } from "../types";

type Props = {
  episodeId: number;
  scenes: SceneNode[];
};

export default function SceneTimeline({ episodeId, scenes }: Props) {
  const navigate = useNavigate();

  if (scenes.length === 0) {
    return (
      <div className="home-card p-6">
        <div className="skeleton h-5 w-2/3 mb-3" />
        <div className="skeleton h-5 w-1/2 mb-3" />
        <div className="text-sm text-ink-500 mt-3 flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full bg-aidc-ai/70 animate-pulse" />
          正在加工本集，约需 30–60 秒…
        </div>
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {scenes.map((sc) => {
        if (sc.state === "locked") {
          return (
            <li
              key={sc.id}
              className="home-card px-5 py-3.5 text-ink-400 italic select-none cursor-default flex items-center gap-2"
            >
              <span className="inline-block w-2 h-2 rounded-full bg-ink-300" />
              🔒 场景 {sc.idx + 1} · ???
            </li>
          );
        }
        if (sc.state === "done") {
          return (
            <li
              key={sc.id}
              onClick={() => navigate(`/episodes/${episodeId}/reading?scene=${sc.idx}`)}
              className="home-card hover:shadow-aidcL2 px-5 py-3.5 cursor-pointer text-ink-500 flex items-center justify-between"
              title="重读这一场（不会改动进度）"
            >
              <span className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-emerald-600 font-semibold">✓</span>
                场景 {sc.idx + 1} · {sc.title_zh}
              </span>
              <span className="text-xs text-ink-400">{sc.line_count} 行</span>
            </li>
          );
        }
        return (
          <li
            key={sc.id}
            className="home-card p-6 border-aidc-purple/40 ring-2 ring-aidc-purpleLight space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-ink-900 font-semibold flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-aidc-purple" />
                <span className="text-aidc-purple">▶</span>
                场景 {sc.idx + 1} · {sc.title_zh}
              </span>
              <span className="text-xs text-ink-500">{sc.line_count} 行</span>
            </div>
            {sc.preview_lines && sc.preview_lines.length > 0 && (
              <div className="ja text-sm text-ink-700 space-y-1 pl-1 border-l-2 border-aidc-purple/30">
                {sc.preview_lines.map((ln, i) => (
                  <div key={i} className="pl-2">「{ln}」</div>
                ))}
              </div>
            )}
            <button
              onClick={() => navigate(`/episodes/${episodeId}/reading?scene=${sc.idx}`)}
              className="btn-aidc btn-sm"
            >
              继续读这一场 →
            </button>
          </li>
        );
      })}
    </ul>
  );
}
