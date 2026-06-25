import { useState, type ReactNode } from "react";

import type { MainCharacter } from "../types";

type Props = {
  seriesTitle: string;
  character: MainCharacter | null;
  episodeLabel?: string;
  rightSlot?: ReactNode;
};

export default function CharacterHeader({
  seriesTitle, character, episodeLabel, rightSlot,
}: Props) {
  const [imgFailed, setImgFailed] = useState(false);
  const initial = character?.fallback_initial ?? seriesTitle.slice(0, 1) ?? "?";
  const displayName = character?.name_jp ?? character?.name_en;
  const showImage = !!character?.image_url && !imgFailed;

  return (
    <div className="home-card overflow-hidden">
      {/* AIDC AI 渐变顶条：标识「AI 陪练」区域 */}
      <div className="h-[3px] bg-aiGradientBar" />
      <div className="flex items-center gap-4 p-6">
        {showImage ? (
          <img
            src={character!.image_url!}
            alt={displayName ?? "character"}
            className="w-16 h-16 rounded-full object-cover border border-ink-200 shrink-0"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-sakura-100 text-sakura-700 font-bold text-2xl ja flex items-center justify-center shrink-0">
            {initial}
          </div>
        )}
        <div className="flex-1 min-w-0">
          {character && displayName && (
            <div className="text-xs text-ink-500 flex items-center gap-1.5 flex-wrap">
              <span className="inline-flex items-center gap-1 rounded-md bg-aidc-purpleLight px-1.5 py-0.5 text-[11px] font-medium text-aidc-purple">
                ✨ AI 陪练
              </span>
              今天和你一起练 ·{" "}
              <span className="ja text-ink-700 font-medium">{displayName}</span>
            </div>
          )}
          <div className="text-lg font-semibold text-ink-900 truncate mt-0.5">
            {seriesTitle}
          </div>
          {episodeLabel && (
            <div className="text-sm text-ink-600 mt-0.5">{episodeLabel}</div>
          )}
        </div>
        {rightSlot}
      </div>
    </div>
  );
}
