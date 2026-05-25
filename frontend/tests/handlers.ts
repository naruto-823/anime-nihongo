import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/series", () => HttpResponse.json([
    { id: 1, title: "测试番", title_jp: null, jimaku_entry_id: null, is_current: true },
  ])),
  http.get("/api/study/today", () => HttpResponse.json({
    due: { vocab: 3, grammar: 1 },
    current_episode: { id: 10, number: 1, title: null,
                       read_position: 0, total_lines: 2, reading_done: false },
    streak: 5,
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
  http.get("/api/episodes/10/lines", () => HttpResponse.json([
    { id: 100, idx: 0, start_ms: 1000, end_ms: 4000, speaker: null,
      text_jp: "おはよう、元気？",
      furigana: [{ t: "おはよう、" }, { t: "元気", r: "げんき" }, { t: "？" }],
      translation_zh: "早上好，精神吗？",
      grammar_notes: [], register_tag: "casual", grammar_point_keys: [], processed: true },
  ])),
];
