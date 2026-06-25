import type {
  ConvTurn, Critique, DueItems, Episode, Grade, GrammarPoint,
  JourneyResponse, Line, Progress, QuizQuestion, SceneNode, Series, SeriesWithAniList,
  SpeakerCharacter, SubmitResult, TowerMap, VocabDetail, VocabListResponse,
} from "../types";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!resp.ok) throw new Error(`${resp.status} ${path}: ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

// Series
export const listSeries = () => http<Series[]>("/api/series");
export const createSeries = (title: string, title_jp?: string) =>
  http<Series>("/api/series", { method: "POST", body: JSON.stringify({ title, title_jp }) });
export const setCurrentSeries = (id: number) =>
  http<Series>(`/api/series/${id}/set-current`, { method: "POST" });

// Episodes
export const importEpisodeFile = async (seriesId: number, number: number, file: File) => {
  const form = new FormData();
  form.append("series_id", String(seriesId));
  form.append("number", String(number));
  form.append("file", file);
  const resp = await fetch("/api/episodes/import-file", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json() as Promise<Episode>;
};
export const getEpisode = (id: number) => http<Episode>(`/api/episodes/${id}`);
export const getLines = (id: number) => http<Line[]>(`/api/episodes/${id}/lines`);
export const generateDemoEpisode = (seriesId: number, number: number, lines_count = 20) =>
  http<Episode>("/api/episodes/generate-demo", {
    method: "POST",
    body: JSON.stringify({ series_id: seriesId, number, lines_count }),
  });

// Journey / Today
export const getJourney = () => http<JourneyResponse>("/api/today/journey");

export const getSeries = (id: number) =>
  http<SeriesWithAniList>(`/api/series/${id}`);

export const refreshAnilist = (id: number) =>
  http<SeriesWithAniList>(`/api/series/${id}/refresh-anilist`, { method: "POST" });

export const getScenes = (episodeId: number) =>
  http<SceneNode[]>(`/api/episodes/${episodeId}/scenes`);

// Study
export const addVocabToSrs = (id: number) =>
  http<{ id: number; in_srs: true }>(`/api/study/vocab/${id}/add-srs`, { method: "POST" });
export const addGrammarToSrs = (id: number) =>
  http<{ id: number; in_srs: true; status: string }>(
    `/api/study/grammar/${id}/add-srs`, { method: "POST" });
export const setReadingProgress = (episodeId: number, position: number) =>
  http<Episode>(`/api/study/episodes/${episodeId}/reading-progress`,
    { method: "POST", body: JSON.stringify({ position }) });
export const completeToday = (body: {
  episode_id?: number | null; vocab_reviewed?: number; grammar_reviewed?: number;
  lines_read?: number; conversation_turns?: number; summary?: Record<string, unknown>;
}) => http<{ streak: number }>("/api/study/complete-today",
  { method: "POST", body: JSON.stringify(body) });

// SRS
export const getDue = () => http<DueItems>("/api/srs/due");
export const submitReview = (item_type: "vocab" | "grammar", item_id: number, grade: Grade) =>
  http<{ id: number; interval_days: number; reps: number; due_date: string }>(
    "/api/srs/review",
    { method: "POST", body: JSON.stringify({ item_type, item_id, grade }) });

// Grammar
export const getChecklist = () => http<Record<string, GrammarPoint[]>>("/api/grammar/checklist");
export const getQuiz = (grammarId: number) =>
  http<{ question: string; options: string[]; answer: string; explain: string }>(
    `/api/grammar/${grammarId}/quiz`);

// Vocab
export const getVocab = (params: {
  level?: string; q?: string; pos?: string; limit?: number; offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params.level) sp.set("level", params.level);
  if (params.q) sp.set("q", params.q);
  if (params.pos) sp.set("pos", params.pos);
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));
  const qs = sp.toString();
  return http<VocabListResponse>(`/api/vocab${qs ? `?${qs}` : ""}`);
};

export const getVocabDetail = (id: number) =>
  http<VocabDetail>(`/api/vocab/${id}`);

// Conversation
export const conversationTurn = (body: {
  episode_id: number; character?: string; history: ConvTurn[]; user_text: string;
}) => http<{ reply: string; critique: Critique }>("/api/conversation/turn",
  { method: "POST", body: JSON.stringify(body) });
export const conversationFeedback = (body: { episode_id: number; history: ConvTurn[] }) =>
  http<{
    corrections: { original: string; fixed: string; explain: string }[];
    suggestions: string[];
    new_vocab: { headword: string; reading: string; meaning_zh: string }[];
    weak_grammar_keys: string[];
  }>("/api/conversation/feedback",
    { method: "POST", body: JSON.stringify(body) });

// Progress
export const getProgress = () => http<Progress>("/api/progress");

// TTS (VOICEVOX)
export const getSpeakers = () =>
  http<SpeakerCharacter[]>("/api/tts/speakers");

// Tower
export const getTower = () => http<TowerMap>("/api/tower");
export const getTowerQuiz = (p: { level: string; zone: number; stage: number; boss?: boolean }) =>
  http<{ questions: QuizQuestion[] }>(
    `/api/tower/quiz?level=${p.level}&zone=${p.zone}&stage=${p.stage}&boss=${p.boss ? 1 : 0}`);
export const submitQuiz = (body: {
  level: string; zone: number; stage: number; boss: boolean;
  results: { item: { kind: string; id: number }; correct: boolean }[];
}) => http<SubmitResult>("/api/tower/submit",
  { method: "POST", body: JSON.stringify(body) });
export const getPlayer = () => http<{ total_xp: number; player_level: number }>("/api/player");
