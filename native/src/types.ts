export type User = { id: number; username: string };
export type Player = { total_xp: number; player_level: number };
export type Stage = {
  stage_idx: number;
  is_boss: boolean;
  unlocked: boolean;
  cleared: boolean;
  stars: number;
};
export type Zone = { zone_idx: number; stages: Stage[] };
export type Level = { level: string; unlocked: boolean; zones: Zone[] };
export type TowerMap = { levels: Level[] };
export type Question = {
  id: string;
  prompt: string;
  hint: string | null;
  options: string[];
  answer: string;
  item: { kind: string; id: number; dimension: string };
};
export type VocabItem = {
  id: number;
  headword: string;
  reading: string;
  meaning_zh: string;
  jlpt_level: string | null;
};
export type DueItem = {
  id: number;
  headword?: string;
  reading?: string;
  meaning_zh?: string;
  name?: string;
  explanation?: string;
};
export type DueData = { vocab: DueItem[]; grammar: DueItem[] };
export type Coverage = {
  syllabus_complete: boolean;
  levels: Array<{
    level: string;
    vocab: { total: number; mapped: number };
    grammar: { total: number; mapped: number };
    mastery_percent: number;
  }>;
  totals: { content_items: number; mastery_percent: number };
};
