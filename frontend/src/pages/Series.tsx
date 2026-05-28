import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import EmptyState from "../components/EmptyState";
import { createSeries, generateDemoEpisode, importEpisodeFile, listSeries,
         refreshAnilist, setCurrentSeries } from "../lib/api";
import type { Series } from "../types";

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
      <h1 className="text-2xl font-bold text-ink-900">番剧库</h1>

      <section className="card-padded space-y-3">
        <div className="text-sm text-ink-500">新增番剧</div>
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="番剧名"
            className="input flex-1"
          />
          <button
            onClick={() => title && create.mutate()}
            className="btn-primary"
            disabled={!title || create.isPending}
          >新增</button>
        </div>
      </section>

      <section className="space-y-3">
        {data.length === 0 && (
          <EmptyState icon="📺" title="还没有番剧" hint="先新增一部吧。" />
        )}
        {data.map((s) => (
          <div key={s.id} className="card-padded card-hover">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <SeriesAvatar series={s} />
                <div className="font-semibold text-ink-800 flex items-center gap-2 truncate">
                  {s.title}
                  {s.is_current && <span className="badge-sakura">当前</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {(s.anilist_status === "not_found" || s.anilist_status === "failed") && (
                  <RefreshAnilistButton seriesId={s.id} />
                )}
                {!s.is_current && (
                  <button
                    onClick={() => setCurrent.mutate(s.id)}
                    className="btn-ghost btn-sm"
                  >设为当前</button>
                )}
              </div>
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
      qc.invalidateQueries({ queryKey: ["journey"] });
    },
    onError: (e: Error) => setError(e.message),
  });
  const gen = useMutation({
    mutationFn: () => generateDemoEpisode(seriesId, number),
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["series"] });
      qc.invalidateQueries({ queryKey: ["journey"] });
    },
    onError: (e: Error) => setError(e.message),
  });
  return (
    <div className="mt-4 space-y-3 text-sm">
      <div className="text-ink-500">导入字幕（.srt / .ass）</div>
      <div className="flex items-center gap-2">
        <input
          type="number" min={1} value={number}
          onChange={(e) => setNumber(Number(e.target.value))}
          className="input w-20"
        />
        <input
          type="file" accept=".srt,.ass"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-xs flex-1"
        />
        <button
          onClick={() => file && imp.mutate()}
          className="btn-secondary btn-sm"
          disabled={!file || imp.isPending}
        >{imp.isPending ? "处理中…" : "导入并加工"}</button>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-ink-400 text-xs">或</span>
        <button
          onClick={() => gen.mutate()}
          className="btn-primary btn-sm"
          disabled={gen.isPending}
        >{gen.isPending ? "✨ Claude 生成中…" : "✨ 服务端生成示例剧集（约 20 行）"}</button>
      </div>
      {error && <div className="text-rose-600 text-xs">{error}</div>}
      {imp.isSuccess && <div className="text-emerald-700 text-xs">第 {number} 集已加工完成。</div>}
      {gen.isSuccess && <div className="text-emerald-700 text-xs">第 {number} 集（生成的示例）已加工完成。</div>}
    </div>
  );
}

function SeriesAvatar({ series }: { series: Series }) {
  const [imgFailed, setImgFailed] = useState(false);
  const chars = series.characters ?? [];
  const main = chars.find((c) => c.image_url) ?? chars[0];
  const initial = main?.name_jp?.[0] ?? main?.name_en?.[0] ?? series.title[0] ?? "?";
  if (main?.image_url && !imgFailed) {
    return (
      <img
        src={main.image_url}
        alt={main.name_jp ?? main.name_en ?? series.title}
        className="w-10 h-10 rounded-full object-cover border border-ink-200 shrink-0"
        onError={() => setImgFailed(true)}
      />
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-sakura-100 text-sakura-700 font-bold ja flex items-center justify-center shrink-0">
      {initial}
    </div>
  );
}

function RefreshAnilistButton({ seriesId }: { seriesId: number }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => refreshAnilist(seriesId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["series"] }),
  });
  return (
    <button
      onClick={() => m.mutate()}
      className="btn-ghost btn-sm"
      disabled={m.isPending}
      title="重新尝试 AniList 角色匹配"
    >{m.isPending ? "匹配中…" : "重新匹配"}</button>
  );
}
