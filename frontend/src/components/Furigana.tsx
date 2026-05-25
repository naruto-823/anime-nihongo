import type { FuriganaSeg } from "../types";

export default function Furigana({ segs, showRuby = true }:
  { segs: FuriganaSeg[] | null; showRuby?: boolean }) {
  if (!segs) return null;
  return (
    <span className="ja">
      {segs.map((s, i) =>
        s.r && showRuby ? (
          <ruby key={i}>{s.t}<rt>{s.r}</rt></ruby>
        ) : (
          <span key={i}>{s.t}</span>
        ),
      )}
    </span>
  );
}
