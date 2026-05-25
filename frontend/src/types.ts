export type FuriganaSeg = { t: string; r?: string };

export type Series = {
  id: number; title: string; title_jp: string | null;
  jimaku_entry_id: number | null; is_current: boolean;
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

export type Today = {
  due: { vocab: number; grammar: number };
  current_episode: { id: number; number: number; title: string | null;
                     read_position: number; total_lines: number;
                     reading_done: boolean } | null;
  streak: number;
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

export type ConvTurn = { role: "user" | "assistant"; text: string };
