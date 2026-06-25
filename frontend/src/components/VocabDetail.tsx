import { useQuery } from "@tanstack/react-query";

import { getVocabDetail } from "../lib/api";
import Loading from "./Loading";

export default function VocabDetail({ vocabId, onClose }: {
  vocabId: number | null; onClose: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["vocab-detail", vocabId],
    queryFn: () => getVocabDetail(vocabId as number),
    enabled: vocabId != null,
  });

  if (vocabId == null) return null;

  return (
    <div className="fixed inset-0 z-30 flex justify-end">
      <div className="absolute inset-0 bg-ink-900/30" onClick={onClose} />
      <aside className="relative w-full max-w-md bg-white h-full shadow-xl overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-ink-100 px-5 py-3 flex items-center justify-between">
          <span className="text-sm text-ink-400">词汇详情</span>
          <button onClick={onClose}
                  className="text-ink-400 hover:text-ink-700 text-xl leading-none">×</button>
        </div>

        {isLoading || !data ? (
          <div className="p-6"><Loading /></div>
        ) : (
          <div className="p-5 space-y-5">
            <div>
              <div className="flex items-baseline gap-3">
                <h2 className="text-3xl font-bold text-ink-900 ja">{data.headword}</h2>
                <span className="text-ink-500 ja">{data.reading}</span>
                <span className="text-xs text-brand-700 bg-brand-50 rounded px-1.5 py-0.5">
                  {data.jlpt_level ?? "—"}
                </span>
              </div>
              <p className="text-ink-700 mt-2">{data.meaning_zh}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {data.pos_tags.map((t) => (
                  <span key={t} className="text-xs text-ink-500 bg-ink-100 rounded px-1.5 py-0.5">{t}</span>
                ))}
              </div>
            </div>

            {data.conjugation ? (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-ink-800">
                  活用表 <span className="text-ink-400 font-normal ml-1">{data.conjugation.group}</span>
                </h3>
                <div className="border border-ink-100 rounded-lg overflow-hidden">
                  {data.conjugation.forms.map((f, i) => (
                    <div key={f.key}
                         className={`flex items-center justify-between px-3 py-2 ${
                           i % 2 ? "bg-ink-50/50" : "bg-white"}`}>
                      <span className="text-xs text-ink-500 w-28 shrink-0">{f.label}</span>
                      <span className="ja text-ink-900 font-medium text-right flex-1">{f.surface}</span>
                      {f.kana !== f.surface && (
                        <span className="ja text-ink-400 text-xs ml-2 w-24 text-right shrink-0">{f.kana}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-400">此词不变形(名词/副词等)。</p>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
