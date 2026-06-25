import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import Loading from "../components/Loading";
import { getTowerQuiz, submitQuiz } from "../lib/api";
import type { QuizQuestion, SubmitResult } from "../types";

export default function Quiz() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const level = sp.get("level") ?? "N5";
  const zone = Number(sp.get("zone") ?? 0);
  const stage = Number(sp.get("stage") ?? 0);
  const boss = sp.get("boss") === "1";

  const { data, isLoading } = useQuery({
    queryKey: ["tower-quiz", level, zone, stage, boss],
    queryFn: () => getTowerQuiz({ level, zone, stage, boss }),
    refetchOnWindowFocus: false,
  });

  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [results, setResults] = useState<{ item: QuizQuestion["item"]; correct: boolean }[]>([]);
  const [result, setResult] = useState<SubmitResult | null>(null);

  const questions = useMemo(() => data?.questions ?? [], [data]);
  const q = questions[idx];

  function retry() {
    setIdx(0);
    setPicked(null);
    setResults([]);
    setResult(null);
  }

  async function choose(opt: string) {
    if (picked || !q) return;
    setPicked(opt);
    const correct = opt === q.answer;
    const next = [...results, { item: q.item, correct }];
    setResults(next);
    setTimeout(async () => {
      setPicked(null);
      if (idx + 1 < questions.length) {
        setIdx(idx + 1);
      } else {
        setResult(await submitQuiz({ level, zone, stage, boss, results: next }));
      }
    }, 600);
  }

  if (isLoading || !data) return <Loading />;
  if (result) {
    return (
      <div className="max-w-md mx-auto text-center space-y-4 py-10">
        <h1 className="text-2xl font-bold text-ink-900">本关结算</h1>
        <div className="text-4xl">{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</div>
        <p className="text-ink-600">正确率 {Math.round(result.accuracy * 100)}%</p>
        <p className="text-brand-700 font-semibold">+{result.xp_gained} XP</p>
        <p className={result.passed ? "text-emerald-600" : "text-amber-600"}>
          {result.passed ? "通关!" : "未达标,再来一次"}
        </p>
        <div className="flex gap-3 justify-center pt-4">
          <button onClick={() => nav("/tower")} className="btn btn-primary">返回修炼塔</button>
          <button onClick={retry} className="btn btn-secondary">再来一次</button>
        </div>
      </div>
    );
  }
  if (!q) return <p className="text-ink-400">本关暂无题目</p>;

  return (
    <div className="max-w-md mx-auto space-y-6 py-6">
      <div className="flex items-center justify-between text-xs text-ink-400">
        <button onClick={() => nav("/tower")} className="hover:text-brand-600">← 退出</button>
        <span>第 {idx + 1} / {questions.length} 题</span>
      </div>
      <div className="text-center">
        <div className="text-3xl font-bold text-ink-900 ja">{q.prompt}</div>
        {q.hint && <div className="text-sm text-ink-500 mt-2">{q.hint}</div>}
      </div>
      <div className="grid gap-3">
        {q.options.map((opt) => {
          const state = !picked ? "" : opt === q.answer ? "correct"
            : opt === picked ? "wrong" : "";
          const cls = state === "correct" ? "border-emerald-400 bg-emerald-50"
            : state === "wrong" ? "border-rose-400 bg-rose-50" : "border-ink-200 hover:border-brand-400";
          return (
            <button key={opt} onClick={() => choose(opt)} disabled={!!picked}
                    className={`ja border rounded-xl px-4 py-3 text-lg text-left transition-colors ${cls}`}>
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}
