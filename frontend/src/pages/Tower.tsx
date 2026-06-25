import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Loading from "../components/Loading";
import { getPlayer, getTower } from "../lib/api";
import type { TowerStage } from "../types";

export default function Tower() {
  const nav = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["tower"], queryFn: getTower });
  const { data: player } = useQuery({ queryKey: ["player"], queryFn: getPlayer });
  const [active, setActive] = useState(0);

  if (isLoading || !data) return <Loading />;
  const level = data.levels[active];

  function open(stage: TowerStage, zoneIdx: number) {
    if (!stage.unlocked) return;
    const boss = stage.is_boss ? "&boss=1" : "";
    nav(`/quiz?level=${level.level}&zone=${zoneIdx}&stage=${stage.stage_idx}${boss}`);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink-900">修炼塔</h1>
        {player && <span className="text-sm text-brand-700">Lv.{player.player_level} · {player.total_xp} XP</span>}
      </div>

      <div className="flex gap-2">
        {data.levels.map((lv, i) => (
          <button key={lv.level} onClick={() => lv.unlocked && setActive(i)}
                  disabled={!lv.unlocked}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                    i === active ? "bg-brand-600 text-white"
                    : lv.unlocked ? "bg-ink-100 text-ink-700" : "bg-ink-50 text-ink-300"}`}>
            {lv.unlocked ? lv.level : `🔒${lv.level}`}
          </button>
        ))}
      </div>

      <div className="space-y-6">
        {level.zones.map((zone) => (
          <section key={zone.zone_idx} className="space-y-2">
            <h2 className="text-sm font-semibold text-ink-500">第 {zone.zone_idx + 1} 区</h2>
            <div className="flex flex-wrap gap-3">
              {zone.stages.map((st) => (
                <button key={`${st.stage_idx}-${st.is_boss}`} onClick={() => open(st, zone.zone_idx)}
                        disabled={!st.unlocked}
                        className={`w-20 h-20 rounded-xl flex flex-col items-center justify-center text-sm border-2 ${
                          !st.unlocked ? "border-ink-100 bg-ink-50 text-ink-300"
                          : st.is_boss ? "border-rose-300 bg-rose-50 text-rose-700"
                          : st.cleared ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                          : "border-brand-300 bg-white text-brand-700"}`}>
                  <span>{st.is_boss ? "👹 Boss" : `第 ${st.stage_idx + 1} 关`}</span>
                  <span className="text-xs">
                    {st.unlocked ? "★".repeat(st.stars) + "☆".repeat((st.is_boss ? 3 : 3) - st.stars) : "🔒"}
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
