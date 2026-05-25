import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
  const [focused, setFocused] = useState(0);
  const tts = useVoicevox();
  const listRef = useRef<HTMLUListElement>(null);

  const advance = useMutation({
    mutationFn: (position: number) => setReadingProgress(epId, position),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["episode", epId] }),
  });

  // Keyboard: J/K to move focus, Space to speak, E to toggle translation
  useEffect(() => {
    if (!lines) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault(); setFocused((i) => Math.min(lines.length - 1, i + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault(); setFocused((i) => Math.max(0, i - 1));
      } else if (e.code === "Space") {
        e.preventDefault(); tts.speak(lines[focused].text_jp);
      } else if (e.key === "e" || e.key === "Enter") {
        e.preventDefault();
        const id = lines[focused].id;
        setShowZh((m) => ({ ...m, [id]: !m[id] }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lines, focused, tts]);

  if (!ep || !lines) return <Loading />;

  return (
    <div className="space-y-5">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">精读 · 第 {ep.number} 集</h1>
          <div className="text-xs text-ink-500 mt-1">
            {ep.read_position}/{ep.total_lines} 行 · 快捷键：J/K 翻行 · 空格朗读 · E 译文
          </div>
        </div>
        <label className="text-sm flex items-center gap-2 text-ink-600 cursor-pointer">
          <input type="checkbox" checked={showRuby}
                 onChange={(e) => setShowRuby(e.target.checked)} />
          假名
        </label>
      </header>

      {tts.error && (
        <div className="badge-amber">TTS: {tts.error}</div>
      )}

      <ul ref={listRef} className="space-y-3">
        {lines.map((ln, i) => {
          const isFocused = i === focused;
          const isOpen = !!showZh[ln.id];
          return (
            <li
              key={ln.id}
              onClick={() => setFocused(i)}
              className={`card-padded card-hover group cursor-pointer transition-colors ${
                isFocused ? "ring-2 ring-brand-400 border-brand-200" : ""
              }`}
            >
              {ln.speaker && (
                <div className="text-xs text-sakura-600 font-medium mb-1">{ln.speaker}</div>
              )}
              <div className="ja text-2xl leading-relaxed text-ink-900">
                <Furigana segs={ln.furigana} showRuby={showRuby} />
              </div>

              <div className="flex items-center gap-2 mt-3 text-xs text-ink-500">
                <button
                  className="btn-ghost btn-sm py-1"
                  onClick={(e) => { e.stopPropagation(); tts.speak(ln.text_jp); }}
                  disabled={tts.loading}
                >🔊 朗读</button>
                <button
                  className="btn-ghost btn-sm py-1"
                  onClick={(e) => { e.stopPropagation();
                    setShowZh((m) => ({ ...m, [ln.id]: !m[ln.id] })); }}
                >{isOpen ? "收起译文" : "看译文 / 讲解"}</button>
                {ln.register_tag && <span className="badge-ink">{ln.register_tag}</span>}
                {ln.grammar_point_keys && ln.grammar_point_keys.length > 0 && (
                  <span className="badge-brand">{ln.grammar_point_keys.join(" · ")}</span>
                )}
              </div>

              {isOpen && (
                <div className="mt-3 pt-3 border-t border-ink-100 space-y-2">
                  <div className="text-sm text-ink-700">{ln.translation_zh}</div>
                  {ln.grammar_notes && ln.grammar_notes.length > 0 && (
                    <ul className="text-xs text-ink-600 space-y-1">
                      {ln.grammar_notes.map((g, j) => (
                        <li key={j}><b className="text-brand-700">{g.point}</b>：{g.explain}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="flex gap-2 pt-3">
        <button
          onClick={() => advance.mutate(Math.min(ep.total_lines, ep.read_position + 15))}
          className="btn-primary"
          disabled={advance.isPending || ep.reading_done}
        >推进 15 行</button>
        <button
          onClick={() => advance.mutate(ep.total_lines)}
          className="btn-secondary"
          disabled={advance.isPending || ep.reading_done}
        >标记本集精读完成</button>
      </div>
    </div>
  );
}
