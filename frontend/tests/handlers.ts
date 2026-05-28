import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/series", () => HttpResponse.json([
    { id: 1, title: "测试番", title_jp: null, jimaku_entry_id: null,
      is_current: true, anilist_id: null, anilist_status: "matched",
      characters: null },
  ])),
  http.get("/api/today/journey", () => HttpResponse.json({
    streak: 5,
    due_total: 4,
    series: {
      id: 1, title: "测试番", anilist_status: "matched",
      main_character: { name_en: null, name_jp: "波奇", image_url: null,
                        fallback_initial: "波" },
    },
    current_episode: {
      id: 10, number: 1, title: null, read_position: 0, total_lines: 2,
      completed_scenes: 0, total_scenes: 2, status: "ready",
    },
    scenes: [
      { id: 1, idx: 0, state: "current", title_zh: "开场", line_count: 1,
        start_line_idx: 0, end_line_idx: 0, preview_lines: ["おはよう、元気？"] },
      { id: 2, idx: 1, state: "locked", title_zh: null, line_count: null,
        start_line_idx: null, end_line_idx: null },
    ],
  })),
  http.get("/api/srs/due", () => HttpResponse.json({
    vocab: [{ id: 1, headword: "猫", reading: "ねこ", meaning_zh: "猫",
              pos: "名詞", context: "猫が走る" }],
    grammar: [],
  })),
  http.get("/api/grammar/checklist", () => HttpResponse.json({
    N2: [{ id: 1, key: "ni-atatte", name: "〜にあたって", jlpt_level: "N2",
           explanation: "在…之际", status: "locked", in_srs: false, mastered: false }],
  })),
  http.get("/api/progress", () => HttpResponse.json({
    streak: 5,
    vocab: { total: 10, in_srs: 7 },
    grammar: { total_curated: 264, encountered: 12, mastered: 2 },
    history: [],
  })),
  http.get("/api/episodes/10", () => HttpResponse.json({
    id: 10, series_id: 1, number: 1, title: null, status: "ready",
    total_lines: 2, processed_lines: 2, read_position: 0, reading_done: false,
  })),
  http.get("/api/episodes/10/scenes", () => HttpResponse.json([
    { id: 1, idx: 0, state: "current", title_zh: "开场", line_count: 1,
      start_line_idx: 0, end_line_idx: 0, preview_lines: ["おはよう、元気？"] },
  ])),
  http.post("/api/study/complete-today", () => HttpResponse.json({ streak: 6 })),
  http.get("/api/episodes/10/lines", () => HttpResponse.json([
    { id: 100, idx: 0, start_ms: 1000, end_ms: 4000, speaker: null,
      text_jp: "おはよう、元気？",
      furigana: [{ t: "おはよう、" }, { t: "元気", r: "げんき" }, { t: "？" }],
      translation_zh: "早上好，精神吗？",
      grammar_notes: [], register_tag: "casual", grammar_point_keys: [], processed: true },
  ])),
  http.get("/api/tts/speakers", () => HttpResponse.json([
    {
      name: "ずんだもん",
      speaker_uuid: "uuid-1",
      styles: [{ id: 3, name: "ノーマル" }],
    },
    {
      name: "四国めたん",
      speaker_uuid: "uuid-2",
      styles: [{ id: 2, name: "ノーマル" }],
    },
  ])),
];
