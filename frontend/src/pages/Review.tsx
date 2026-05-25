import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import EmptyState from "../components/EmptyState";
import { getDue, submitReview } from "../lib/api";
import type { Grade } from "../types";

const GRADES: { grade: Grade; label: string; hint: string; cls: string }[] = [
  { grade: "again", label: "又错了", hint: "< 1 day",  cls: "bg-rose-500 hover:bg-rose-600" },
  { grade: "hard",  label: "有点难", hint: "短间隔",   cls: "bg-amber-500 hover:bg-amber-600" },
  { grade: "good",  label: "会了",   hint: "正常",     cls: "bg-emerald-600 hover:bg-emerald-700" },
  { grade: "easy",  label: "很简单", hint: "更长间隔", cls: "bg-brand-600 hover:bg-brand-700" },
];

export default function Review() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["due"], queryFn: getDue });
  const [show, setShow] = useState(false);

  const submit = useMutation({
    mutationFn: ({ kind, id, grade }: { kind: "vocab" | "grammar"; id: number; grade: Grade }) =>
      submitReview(kind, id, grade),
    onSuccess: () => {
      setShow(false);
      qc.invalidateQueries({ queryKey: ["due"] });
      qc.invalidateQueries({ queryKey: ["today"] });
    },
  });

  if (isLoading || !data) return <Loading />;

  const current =
    data.vocab[0]
      ? { kind: "vocab" as const, item: data.vocab[0] }
      : data.grammar[0]
        ? { kind: "grammar" as const, item: data.grammar[0] }
        : null;

  if (!current) {
    return <EmptyState icon="🎉" title="今天没有到期复习了"
                       hint={<>去 <a href="/" className="text-brand-600 hover:underline">今日训练</a> 推进当前集吧。</>} />;
  }

  const remaining = data.vocab.length + data.grammar.length;

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-ink-900">复习</h1>
        <span className="badge-brand">还有 {remaining} 项</span>
      </div>

      <div className="card-padded py-12 text-center">
        {current.kind === "vocab" ? (
          <VocabCard item={current.item} show={show} />
        ) : (
          <GrammarCard item={current.item} show={show} />
        )}
      </div>

      {!show ? (
        <button onClick={() => setShow(true)}
                className="btn-secondary w-full py-3 text-base">
          显示答案 <span className="text-xs text-ink-400 ml-2">（空格）</span>
        </button>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {GRADES.map(({ grade, label, hint, cls }) => (
            <button
              key={grade}
              onClick={() => submit.mutate({ kind: current.kind, id: current.item.id, grade })}
              className={`${cls} text-white px-3 py-4 rounded-lg transition disabled:opacity-50 text-center`}
              disabled={submit.isPending}
            >
              <div className="font-semibold">{label}</div>
              <div className="text-xs opacity-80 mt-0.5">{hint}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function VocabCard({ item, show }:
  { item: { headword: string; reading: string; meaning_zh: string;
            pos: string | null; context: string | null }; show: boolean }) {
  return (
    <div className="space-y-3">
      <div className="ja text-5xl font-semibold text-ink-900">{item.headword}</div>
      {show && (
        <>
          <div className="ja text-xl text-ink-600">{item.reading}</div>
          <div className="text-ink-700">
            {item.pos && <span className="badge-ink mr-2">{item.pos}</span>}
            {item.meaning_zh}
          </div>
          {item.context && (
            <div className="ja text-sm text-ink-500 italic">「{item.context}」</div>
          )}
        </>
      )}
    </div>
  );
}

function GrammarCard({ item, show }:
  { item: { name: string; jlpt_level: string; explanation: string }; show: boolean }) {
  return (
    <div className="space-y-3">
      <div className="ja text-4xl font-semibold text-ink-900">{item.name}</div>
      <div><span className="badge-sakura">{item.jlpt_level}</span></div>
      {show && <div className="text-ink-700">{item.explanation}</div>}
    </div>
  );
}
