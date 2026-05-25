import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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
  const [handsFree, setHandsFree] = useState(false);
  // 在异步 onSuccess 里读 handsFree 的最新值，避免闭包陈旧
  const handsFreeRef = useRef(handsFree);
  useEffect(() => { handsFreeRef.current = handsFree; }, [handsFree]);

  const turn = useMutation({
    mutationFn: (text: string) => conversationTurn({
      episode_id: epId, character, history, user_text: text,
    }),
    onSuccess: async (r, sentText) => {
      setHistory((h) => [
        ...h,
        { role: "user", text: sentText, critique: r.critique },
        { role: "assistant", text: r.reply },
      ]);
      setDraft("");
      // 等 AI 念完，再决定要不要重开麦
      await tts.speak(r.reply);
      if (handsFreeRef.current && stt.supported && !stt.listening) {
        stt.start();
      }
    },
  });

  // STT 转写出来后：对讲机模式 → 直接提交；普通模式 → 灌入草稿框
  useEffect(() => {
    if (!stt.transcript) return;
    if (handsFree) {
      if (!turn.isPending) turn.mutate(stt.transcript);
    } else {
      setDraft(stt.transcript);
    }
    // 故意只依赖 transcript，避免 handsFree 切换时误触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stt.transcript]);

  // 切换对讲机：开 → 立刻拉起麦克风；关 → 立刻松手
  const prevHF = useRef(false);
  useEffect(() => {
    const turnedOn = !prevHF.current && handsFree;
    const turnedOff = prevHF.current && !handsFree;
    prevHF.current = handsFree;
    if (turnedOn && stt.supported && !stt.listening && !tts.loading) {
      stt.start();
    } else if (turnedOff && stt.listening) {
      stt.stop();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handsFree]);

  const feedback = useMutation({
    mutationFn: () => conversationFeedback({ episode_id: epId, history }),
  });

  if (!ep) return <Loading />;

  // 角色名首字符作为头像 fallback
  const avatar = (character || "?").slice(0, 1);

  return (
    <div className="space-y-4 max-w-3xl mx-auto">
      <header className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-ink-900">💬 第 {ep.number} 集 · 角色对话</h1>
        <input value={character} onChange={(e) => setCharacter(e.target.value)}
               placeholder="角色名" className="input text-sm w-40" />
      </header>

      {!stt.supported && (
        <div className="card-padded bg-amber-50 border-amber-200 text-amber-800 text-sm py-2">
          当前浏览器不支持语音识别（请用 Chrome / Edge）。可改为打字。
        </div>
      )}

      <div className="card bg-ink-50/60 p-4 space-y-3 max-h-[60vh] overflow-auto">
        {history.length === 0 && (
          <div className="text-ink-400 text-sm text-center py-8">
            用日语和「{character}」聊聊这一集吧。
          </div>
        )}
        {history.map((t, i) => (
          t.role === "user" ? (
            <div key={i} className="space-y-1.5">
              <div className="flex justify-end">
                <div className="ja max-w-[75%] bg-brand-600 text-white px-3.5 py-2 rounded-2xl rounded-br-md">
                  {t.text}
                </div>
              </div>
              {t.critique && !t.critique.ok && (
                <div className="flex justify-end">
                  <div className="max-w-[75%] bg-amber-50 border border-amber-200 text-amber-900 px-3 py-2 rounded-lg text-xs space-y-1">
                    <div className="font-semibold text-amber-700">👩‍🏫 老师建议</div>
                    {t.critique.corrected && (
                      <div className="ja text-amber-900">
                        更自然： <b>{t.critique.corrected}</b>
                      </div>
                    )}
                    {t.critique.note && (
                      <div className="text-amber-800">{t.critique.note}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div key={i} className="flex items-start gap-2">
              <div className="w-8 h-8 rounded-full bg-sakura-500 text-white flex items-center justify-center text-sm font-semibold shrink-0 ja">
                {avatar}
              </div>
              <div>
                <div className="text-xs text-ink-500 mb-1 ja">{character}</div>
                <div className="ja max-w-[75%] bg-white border border-ink-200 px-3.5 py-2 rounded-2xl rounded-bl-md">
                  {t.text}
                </div>
              </div>
            </div>
          )
        ))}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {stt.supported && (
          <>
            <button
              onClick={() => (stt.listening ? stt.stop() : stt.start())}
              className={stt.listening ? "btn-danger" : "btn-secondary"}
              title="麦克风"
              disabled={handsFree && turn.isPending}
            >{stt.listening ? "■ 在听" : "🎙"}</button>
            <label
              className={`btn-sm flex items-center gap-1.5 cursor-pointer rounded-lg border px-2.5 py-1.5 transition ${
                handsFree
                  ? "bg-brand-50 border-brand-300 text-brand-700"
                  : "bg-white border-ink-200 text-ink-600"
              }`}
              title="说完自动发送、AI 念完自动开麦克风，连续对话"
            >
              <input
                type="checkbox"
                className="hidden"
                checked={handsFree}
                onChange={(e) => setHandsFree(e.target.checked)}
              />
              {handsFree ? "🔁 对讲机模式 · 开" : "对讲机模式"}
            </label>
          </>
        )}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={handsFree
            ? "对讲机模式开启：说完自动发送，无需手动提交"
            : "说点什么…（Enter 发送，输入法选词时不会误触）"}
          className="input flex-1 min-w-[180px]"
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            if (e.nativeEvent.isComposing || e.keyCode === 229) return;
            if (draft && !turn.isPending) {
              e.preventDefault();
              turn.mutate(draft);
            }
          }}
        />
        <button
          onClick={() => turn.mutate(draft)}
          disabled={!draft || turn.isPending}
          className="btn-primary"
        >发送</button>
      </div>
      {handsFree && (
        <div className="text-xs text-brand-700 -mt-2">
          {tts.loading ? "🔊 角色说话中…" :
            stt.listening ? "🎙 在听你说…" :
            turn.isPending ? "✨ 思考中…" : "准备就绪"}
        </div>
      )}

      {tts.error && <div className="text-xs text-amber-700">TTS: {tts.error}</div>}

      {history.length > 0 && (
        <div>
          <button
            onClick={() => feedback.mutate()}
            className="btn-secondary"
            disabled={feedback.isPending}
          >{feedback.isPending ? "AI 复盘中…" : "结束对话 · 让 AI 复盘"}</button>
        </div>
      )}

      {feedback.data && (
        <section className="card-padded space-y-3">
          <h3 className="font-semibold text-ink-900">复盘</h3>
          {feedback.data.corrections.length > 0 && (
            <ul className="text-sm space-y-2">
              {feedback.data.corrections.map((c, i) => (
                <li key={i} className="ja">
                  <span className="line-through text-ink-400">{c.original}</span>
                  {" → "}
                  <span className="text-brand-700 font-medium">{c.fixed}</span>
                  <span className="text-ink-500 ml-2 not-italic" style={{ fontFamily: "inherit" }}>{c.explain}</span>
                </li>
              ))}
            </ul>
          )}
          {feedback.data.suggestions.length > 0 && (
            <div className="text-sm text-ink-700">💡 {feedback.data.suggestions.join("；")}</div>
          )}
          {feedback.data.new_vocab.length > 0 && (
            <div className="text-xs text-ink-500 ja">
              新词已加入复习：{feedback.data.new_vocab.map((v) => v.headword).join("、")}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
