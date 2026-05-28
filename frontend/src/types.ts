export type FuriganaSeg = { t: string; r?: string };

export type AnilistStatus = "pending" | "matched" | "not_found" | "failed";

export type Character = {
  name_en: string | null;
  name_jp: string | null;
  image_url: string | null;
  role: "MAIN" | "SUPPORTING" | null;
};

export type Series = {
  id: number; title: string; title_jp: string | null;
  jimaku_entry_id: number | null; is_current: boolean;
  anilist_id: number | null;
  anilist_status: AnilistStatus;
  characters: Character[] | null;
};

export type Episode = {
  id: number; series_id: number; number: number; title: string | null;
  status: "importing" | "processing" | "ready" | "failed";
  total_lines: number; processed_lines: number;
  read_position: number; reading_done: boolean;
};

export type Line = {
  id: number; idx: number; start_ms: number | null; end_ms: number | null;
  speaker: string | null; text_jp: string;
  furigana: FuriganaSeg[] | null; translation_zh: string | null;
  grammar_notes: { point: string; explain: string }[] | null;
  register_tag: string | null;
  grammar_point_keys: string[] | null;
  processed: boolean;
};

export type GrammarPoint = {
  id: number; key: string; name: string; jlpt_level: string;
  explanation: string; status: "locked" | "seen" | "learning";
  in_srs: boolean; mastered: boolean;
};

export type DueItems = {
  vocab: { id: number; headword: string; reading: string;
           meaning_zh: string; pos: string | null; context: string | null }[];
  grammar: { id: number; key: string; name: string; jlpt_level: string;
             explanation: string }[];
};

export type MainCharacter = {
  name_en: string | null;
  name_jp: string | null;
  image_url: string | null;
  fallback_initial: string;
};

export type SeriesWithAniList = Series;

export type SceneState = "done" | "current" | "locked";

export type SceneNode = {
  id: number;
  idx: number;
  state: SceneState;
  title_zh: string | null;
  line_count: number | null;
  start_line_idx: number | null;
  end_line_idx: number | null;
  preview_lines?: string[];
};

export type JourneyResponse = {
  streak: number;
  due_total: number;
  series: {
    id: number;
    title: string;
    anilist_status: AnilistStatus;
    main_character: MainCharacter | null;
  } | null;
  current_episode: {
    id: number;
    number: number;
    title: string | null;
    read_position: number;
    total_lines: number;
    completed_scenes: number;
    total_scenes: number;
    status: "importing" | "processing" | "ready" | "failed";
  } | null;
  scenes: SceneNode[];
};

export type Progress = {
  streak: number;
  vocab: { total: number; in_srs: number };
  grammar: { total_curated: number; encountered: number; mastered: number };
  history: { date: string; completed: boolean;
             vocab_reviewed: number; grammar_reviewed: number;
             lines_read: number }[];
};

export type Grade = "again" | "hard" | "good" | "easy";

export type Critique = {
  ok: boolean;
  corrected: string | null;
  note: string | null;
};

export type ConvTurn = {
  role: "user" | "assistant";
  text: string;
  /** Only present on user turns once the teacher critique has come back. */
  critique?: Critique;
};

export type SpeakerStyle = { id: number; name: string };
export type SpeakerCharacter = {
  name: string;
  speaker_uuid: string;
  styles: SpeakerStyle[];
};
