import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getVocab } from "../lib/api";
import Loading from "./Loading";
import VocabDetail from "./VocabDetail";

const PAGE_SIZE = 50;
const LEVELS = ["N5", "N4", "N3", "N2", "N1"];
const POS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "全部词性" },
  { key: "noun", label: "名词" },
  { key: "verb", label: "动词" },
  { key: "verb_t", label: "他动词" },
  { key: "verb_i", label: "自动词" },
  { key: "i-adj", label: "イ形" },
  { key: "na-adj", label: "ナ形" },
  { key: "adverb", label: "副词" },
  { key: "other", label: "其他" },
];

export default function VocabBrowser() {
  const [level, setLevel] = useState<string>("");
  const [pos, setPos] = useState<string>("");
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // 输入防抖 300ms,回写查询词并回到第一页
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [input]);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["vocab", level, pos, q, page],
    queryFn: () => getVocab({ level: level || undefined, pos: pos || undefined,
      q: q || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const pickLevel = (lv: string) => { setLevel(lv); setPage(0); };
  const pickPos = (p: string) => { setPos(p); setPage(0); };

  return (
    <div className="space-y-4">
      <input
        className="input w-full"
        placeholder="搜索写法 / 读音 / 中文释义…"
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />

      <div className="flex flex-wrap gap-1.5">
        <Chip active={level === ""} onClick={() => pickLevel("")}>
          全部 <span className="opacity-60">{Object.values(data?.counts ?? {}).reduce((a, b) => a + b, 0)}</span>
        </Chip>
        {LEVELS.map((lv) => (
          <Chip key={lv} active={level === lv} onClick={() => pickLevel(lv)}>
            {lv} <span className="opacity-60">{data?.counts?.[lv] ?? 0}</span>
          </Chip>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {POS_FILTERS.map((p) => (
          <Chip key={p.key} active={pos === p.key} onClick={() => pickPos(p.key)} subtle>
            {p.label}
          </Chip>
        ))}
      </div>

      {isLoading ? (
        <Loading />
      ) : total === 0 ? (
        <p className="text-ink-400 text-sm py-8 text-center">没有匹配的词汇</p>
      ) : (
        <div className={`card overflow-hidden ${isFetching ? "opacity-60" : ""} transition-opacity`}>
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-ink-500 text-xs">
              <tr>
                <th className="text-left font-medium px-3 py-2">写法</th>
                <th className="text-left font-medium px-3 py-2">读音</th>
                <th className="text-left font-medium px-3 py-2">中文释义</th>
                <th className="text-left font-medium px-3 py-2">词性</th>
                <th className="text-left font-medium px-3 py-2 w-12">级别</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((v) => (
                <tr key={v.id}
                    onClick={() => setSelectedId(v.id)}
                    className="border-t border-ink-100 hover:bg-brand-50/60 cursor-pointer">
                  <td className="px-3 py-2 ja font-medium text-ink-900">{v.headword}</td>
                  <td className="px-3 py-2 ja text-ink-500">{v.reading}</td>
                  <td className="px-3 py-2 text-ink-700">{v.meaning_zh}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {v.pos_tags.map((t) => (
                        <span key={t} className="text-[10px] text-ink-500 bg-ink-100 rounded px-1 py-0.5">{t}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span className="text-xs text-brand-700 bg-brand-50 rounded px-1.5 py-0.5">
                      {v.jlpt_level ?? "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-ink-500">
        <span>共 {total} 词</span>
        <div className="flex items-center gap-2">
          <button className="btn btn-secondary btn-sm" disabled={page <= 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}>
            上一页
          </button>
          <span>第 {page + 1} / {pageCount} 页</span>
          <button className="btn btn-secondary btn-sm" disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}>
            下一页
          </button>
        </div>
      </div>

      <VocabDetail vocabId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}

function Chip({ active, onClick, children, subtle }: {
  active: boolean; onClick: () => void; children: React.ReactNode; subtle?: boolean;
}) {
  const activeCls = subtle
    ? "bg-ink-700 text-white border-ink-700"
    : "bg-brand-600 text-white border-brand-600";
  return (
    <button
      onClick={onClick}
      className={`text-xs rounded-full px-3 py-1 border transition-colors ${
        active ? activeCls : "bg-white text-ink-500 border-ink-200 hover:border-brand-300"
      }`}
    >
      {children}
    </button>
  );
}
