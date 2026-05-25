import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import { getDue, submitReview } from "../lib/api";
import type { Grade } from "../types";

const GRADE_LABELS: { grade: Grade; label: string; cls: string }[] = [
  { grade: "again", label: "又错了", cls: "bg-red-600" },
  { grade: "hard",  label: "有点难", cls: "bg-amber-500" },
  { grade: "good",  label: "会了",   cls: "bg-emerald-600" },
  { grade: "easy",  label: "很简单", cls: "bg-indigo-600" },
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
    return <div className="text-slate-600">今天没有到期复习。继续推进当前集吧。</div>;
  }

  const remaining = data.vocab.length + data.grammar.length;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">复习 · 还有 {remaining} 项</h1>
      <div className="bg-white border rounded p-6">
        {current.kind === "vocab" ? (
          <VocabCard item={current.item} show={show} />
        ) : (
          <GrammarCard item={current.item} show={show} />
        )}
      </div>
      {!show ? (
        <button onClick={() => setShow(true)}
                className="px-4 py-2 bg-slate-800 text-white rounded">
          显示答案
        </button>
      ) : (
        <div className="flex flex-wrap gap-2">
          {GRADE_LABELS.map(({ grade, label, cls }) => (
            <button
              key={grade}
              onClick={() => submit.mutate({ kind: current.kind, id: current.item.id, grade })}
              className={`${cls} text-white px-3 py-2 rounded text-sm disabled:opacity-50`}
              disabled={submit.isPending}
            >{label}</button>
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
    <div className="space-y-2">
      <div className="text-3xl">{item.headword}</div>
      {show && (
        <>
          <div className="text-lg">{item.reading}</div>
          <div className="text-slate-700">
            {item.pos && <span className="text-xs mr-2 px-1.5 py-0.5 bg-slate-100 rounded">{item.pos}</span>}
            {item.meaning_zh}
          </div>
          {item.context && <div className="text-slate-500 text-sm">语境：{item.context}</div>}
        </>
      )}
    </div>
  );
}

function GrammarCard({ item, show }:
  { item: { name: string; jlpt_level: string; explanation: string }; show: boolean }) {
  return (
    <div className="space-y-2">
      <div className="text-2xl">{item.name}</div>
      <div className="text-xs text-slate-500">{item.jlpt_level}</div>
      {show && <div className="text-slate-700">{item.explanation}</div>}
    </div>
  );
}
