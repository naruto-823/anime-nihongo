import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import { createSeries, generateDemoEpisode, importEpisodeFile, listSeries, setCurrentSeries } from "../lib/api";

export default function Series() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["series"], queryFn: listSeries });
  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () => createSeries(title),
    onSuccess: () => { setTitle(""); qc.invalidateQueries({ queryKey: ["series"] }); },
  });
  const setCurrent = useMutation({
    mutationFn: (id: number) => setCurrentSeries(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["series"] }),
  });

  if (isLoading || !data) return <Loading />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">番剧库</h1>

      <section className="bg-white rounded border p-4 space-y-2">
        <div className="text-sm text-slate-500">新增番剧</div>
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="番剧名"
            className="border rounded px-3 py-1 flex-1"
          />
          <button
            onClick={() => title && create.mutate()}
            className="px-3 py-1 bg-indigo-600 text-white rounded disabled:opacity-50"
            disabled={!title || create.isPending}
          >新增</button>
        </div>
      </section>

      <section className="space-y-3">
        {data.length === 0 && <div className="text-slate-500">还没有番剧。先新增一部吧。</div>}
        {data.map((s) => (
          <div key={s.id} className="bg-white rounded border p-4">
            <div className="flex items-center justify-between">
              <div className="font-medium">
                {s.title}
                {s.is_current && <span className="ml-2 text-xs text-indigo-600">当前</span>}
              </div>
              {!s.is_current && (
                <button
                  onClick={() => setCurrent.mutate(s.id)}
                  className="text-xs text-indigo-600 hover:underline"
                >设为当前</button>
              )}
            </div>
            <ImportEpisode seriesId={s.id} />
          </div>
        ))}
      </section>
    </div>
  );
}

function ImportEpisode({ seriesId }: { seriesId: number }) {
  const qc = useQueryClient();
  const [number, setNumber] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const imp = useMutation({
    mutationFn: () => importEpisodeFile(seriesId, number, file!),
    onSuccess: () => {
      setFile(null); setError(null);
      qc.invalidateQueries({ queryKey: ["today"] });
    },
    onError: (e: Error) => setError(e.message),
  });
  const gen = useMutation({
    mutationFn: () => generateDemoEpisode(seriesId, number),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["series"] });
      qc.invalidateQueries({ queryKey: ["today"] });
    },
    onError: (e: Error) => setError(e.message),
  });
  return (
    <div className="mt-3 text-sm space-y-1">
      <div className="text-slate-500">导入字幕（.srt / .ass）</div>
      <div className="flex items-center gap-2">
        <input
          type="number" min={1} value={number}
          onChange={(e) => setNumber(Number(e.target.value))}
          className="border rounded px-2 py-1 w-20"
        />
        <input
          type="file" accept=".srt,.ass"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-xs"
        />
        <button
          onClick={() => file && imp.mutate()}
          className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
          disabled={!file || imp.isPending}
        >{imp.isPending ? "处理中…" : "导入并加工"}</button>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-slate-400">或</span>
        <button
          onClick={() => gen.mutate()}
          className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded disabled:opacity-50"
          disabled={gen.isPending}
        >{gen.isPending ? "生成中…" : "服务端生成示例剧集（约 20 行）"}</button>
      </div>
      {error && <div className="text-red-600">{error}</div>}
      {imp.isSuccess && (
        <div className="text-green-700">第 {number} 集已加工完成。</div>
      )}
      {gen.isSuccess && (
        <div className="text-green-700">第 {number} 集（生成的示例）已加工完成。</div>
      )}
    </div>
  );
}
