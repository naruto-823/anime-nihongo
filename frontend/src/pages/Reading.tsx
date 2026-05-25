import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import Furigana from "../components/Furigana";
import Loading from "../components/Loading";
import { getEpisode, getLines, setReadingProgress } from "../lib/api";
import { useVoicevox } from "../lib/voicevox";

export default function Reading() {
  const { id } = useParams();
  const epId = Number(id);
  const qc = useQueryClient();
  const { data: ep } = useQuery({ queryKey: ["episode", epId], queryFn: () => getEpisode(epId) });
  const { data: lines } = useQuery({ queryKey: ["lines", epId], queryFn: () => getLines(epId) });
  const [showRuby, setShowRuby] = useState(true);
  const [showZh, setShowZh] = useState<Record<number, boolean>>({});
  const tts = useVoicevox();

  const advance = useMutation({
    mutationFn: (position: number) => setReadingProgress(epId, position),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["episode", epId] }),
  });

  if (!ep || !lines) return <Loading />;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          精读 · 第 {ep.number} 集（{ep.read_position}/{ep.total_lines}）
        </h1>
        <label className="text-sm flex items-center gap-2">
          <input type="checkbox" checked={showRuby}
                 onChange={(e) => setShowRuby(e.target.checked)} />
          显示假名注音
        </label>
      </header>

      <ul className="space-y-2">
        {lines.map((ln) => (
          <li key={ln.id} className="bg-white border rounded p-3">
            <div className="text-lg leading-relaxed">
              {ln.speaker && (
                <span className="text-slate-500 text-sm mr-2">{ln.speaker}：</span>
              )}
              <Furigana segs={ln.furigana} showRuby={showRuby} />
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
              <button
                className="hover:text-indigo-600"
                onClick={() => tts.speak(ln.text_jp)}
                disabled={tts.loading}
              >🔊 朗读</button>
              <button
                className="hover:text-indigo-600"
                onClick={() => setShowZh((m) => ({ ...m, [ln.id]: !m[ln.id] }))}
              >{showZh[ln.id] ? "收起译文" : "看译文"}</button>
              {ln.register_tag && (
                <span className="px-2 py-0.5 bg-slate-100 rounded">{ln.register_tag}</span>
              )}
              {ln.grammar_point_keys && ln.grammar_point_keys.length > 0 && (
                <span>语法: {ln.grammar_point_keys.join(", ")}</span>
              )}
            </div>
            {showZh[ln.id] && (
              <div className="mt-2 text-sm text-slate-700">{ln.translation_zh}</div>
            )}
            {showZh[ln.id] && ln.grammar_notes && ln.grammar_notes.length > 0 && (
              <ul className="mt-1 text-xs text-slate-600 list-disc list-inside">
                {ln.grammar_notes.map((g, i) => (
                  <li key={i}><b>{g.point}</b>：{g.explain}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      {tts.error && (
        <div className="text-xs text-amber-700">TTS: {tts.error}</div>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => advance.mutate(Math.min(ep.total_lines, ep.read_position + 15))}
          className="px-3 py-2 bg-indigo-600 text-white rounded disabled:opacity-50"
          disabled={advance.isPending || ep.reading_done}
        >推进 15 行</button>
        <button
          onClick={() => advance.mutate(ep.total_lines)}
          className="px-3 py-2 bg-slate-200 rounded disabled:opacity-50"
          disabled={advance.isPending || ep.reading_done}
        >标记本集精读完成</button>
      </div>
    </div>
  );
}
