import type { ReactNode } from "react";

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
  const initial = character?.fallback_initial ?? seriesTitle.slice(0, 1) ?? "?";
  const displayName = character?.name_jp ?? character?.name_en;

  return (
    <div className="card-padded flex items-center gap-4">
      {character?.image_url ? (
        <img
          src={character.image_url}
          alt={displayName ?? "character"}
          className="w-16 h-16 rounded-full object-cover border border-ink-200"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
      ) : (
        <div className="w-16 h-16 rounded-full bg-sakura-100 text-sakura-700 font-bold text-2xl ja flex items-center justify-center shrink-0">
          {initial}
        </div>
      )}
      <div className="flex-1 min-w-0">
        {character && displayName && (
          <div className="text-xs text-ink-500">
            今天和你一起练的是 ·{" "}
            <span className="ja text-ink-700 font-medium">{displayName}</span>
          </div>
        )}
        <div className="text-lg font-semibold text-ink-900 truncate">
          {seriesTitle}
        </div>
        {episodeLabel && (
          <div className="text-sm text-ink-600 mt-0.5">{episodeLabel}</div>
        )}
      </div>
      {rightSlot}
    </div>
  );
}
