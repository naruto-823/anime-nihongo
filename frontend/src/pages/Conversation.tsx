import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import Loading from "../components/Loading";
import { conversationFeedback, conversationTurn, getEpisode } from "../lib/api";
import { useSTT } from "../lib/speech";
import { useVoicevox } from "../lib/voicevox";
import type { ConvTurn } from "../types";

export default function Conversation() {
  const { id } = useParams();
  const epId = Number(id);
  const { data: ep } = useQuery({ queryKey: ["episode", epId], queryFn: () => getEpisode(epId) });
  const stt = useSTT();
  const tts = useVoicevox();
  const [history, setHistory] = useState<ConvTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [character, setCharacter] = useState("登場人物");

  useEffect(() => {
    if (stt.transcript) setDraft(stt.transcript);
  }, [stt.transcript]);

  const turn = useMutation({
    mutationFn: () => conversationTurn({
      episode_id: epId, character, history, user_text: draft,
    }),
    onSuccess: (r) => {
      const next: ConvTurn[] = [
        ...history,
        { role: "user", text: draft },
        { role: "assistant", text: r.reply },
      ];
      setHistory(next);
      setDraft("");
      tts.speak(r.reply);
    },
  });

  const feedback = useMutation({
    mutationFn: () => conversationFeedback({ episode_id: epId, history }),
  });

  if (!ep) return <Loading />;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">角色对话 · 第 {ep.number} 集</h1>
        <input value={character} onChange={(e) => setCharacter(e.target.value)}
               placeholder="角色名" className="border rounded px-2 py-1 text-sm w-40" />
      </header>

      {!stt.supported && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm p-2 rounded">
          当前浏览器不支持语音识别（请用 Chrome / Edge）。可改为打字。
        </div>
      )}

      <div className="space-y-2 bg-white border rounded p-3 max-h-96 overflow-auto">
        {history.length === 0 && (
          <div className="text-slate-500 text-sm">用日语和角色聊聊这一集吧。</div>
        )}
        {history.map((t, i) => (
          <div key={i} className={t.role === "user" ? "text-right" : ""}>
            <span className={`inline-block px-3 py-2 rounded ${
              t.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-100"
            }`}>{t.text}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        {stt.supported && (
          <button
            onClick={() => (stt.listening ? stt.stop() : stt.start())}
            className={`px-3 py-2 rounded text-sm ${
              stt.listening ? "bg-red-600 text-white" : "bg-slate-200"
            }`}
          >{stt.listening ? "■ 停止" : "🎙 说话"}</button>
        )}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="说点什么…（按 Enter 提交）"
          className="border rounded px-3 py-2 flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft && !turn.isPending) turn.mutate();
          }}
        />
        <button
          onClick={() => turn.mutate()}
          disabled={!draft || turn.isPending}
          className="px-3 py-2 bg-indigo-600 text-white rounded disabled:opacity-50"
        >发送</button>
      </div>

      {tts.error && (
        <div className="text-xs text-amber-700">TTS: {tts.error}</div>
      )}

      {history.length > 0 && (
        <div className="pt-2">
          <button
            onClick={() => feedback.mutate()}
            className="px-3 py-2 bg-slate-800 text-white rounded text-sm"
            disabled={feedback.isPending}
          >{feedback.isPending ? "AI 复盘中…" : "结束对话 · 让 AI 复盘"}</button>
        </div>
      )}

      {feedback.data && (
        <section className="space-y-2 bg-white border rounded p-4">
          <h3 className="font-medium">复盘</h3>
          {feedback.data.corrections.length > 0 && (
            <ul className="text-sm space-y-1">
              {feedback.data.corrections.map((c, i) => (
                <li key={i}>
                  <span className="line-through text-slate-400">{c.original}</span>
                  {" → "}<span className="text-indigo-700 font-medium">{c.fixed}</span>
                  <span className="text-slate-500 ml-2">{c.explain}</span>
                </li>
              ))}
            </ul>
          )}
          {feedback.data.suggestions.length > 0 && (
            <div className="text-sm text-slate-700">
              💡 {feedback.data.suggestions.join("；")}
            </div>
          )}
          {feedback.data.new_vocab.length > 0 && (
            <div className="text-xs text-slate-500">
              新词已加入复习：{feedback.data.new_vocab.map((v) => v.headword).join("、")}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
