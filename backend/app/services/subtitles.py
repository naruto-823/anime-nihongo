import re
from dataclasses import dataclass

_TAG_RE = re.compile(r"\{[^}]*\}")        # ASS 覆盖标签 {\...}
_WS_RE = re.compile(r"\s+")


@dataclass
class ParsedLine:
    idx: int
    start_ms: int | None
    end_ms: int | None
    speaker: str | None
    text: str


def _clean(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = text.replace("\\N", "").replace("\\n", "").replace("\n", " ")  # \N/\n 软换行直接去掉（日文无需词间空格）
    return _WS_RE.sub(" ", text).strip()


def _srt_time_to_ms(t: str) -> int:
    # 00:00:01,000
    hh, mm, rest = t.strip().split(":")
    ss, ms = rest.replace(".", ",").split(",")
    return ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(ms)


def _ass_time_to_ms(t: str) -> int:
    # 0:00:01.00（百分之一秒）
    hh, mm, rest = t.strip().split(":")
    ss, cs = rest.split(".")
    return ((int(hh) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(cs) * 10


def _parse_srt(content: str) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        rows = [r for r in block.splitlines() if r.strip()]
        if len(rows) < 2 or "-->" not in rows[1]:
            continue
        parts = rows[1].split("-->", 1)
        if len(parts) != 2:
            continue
        start, end = parts
        try:
            start_ms = _srt_time_to_ms(start)
            end_ms = _srt_time_to_ms(end)
        except ValueError:
            continue
        text = _clean(" ".join(rows[2:]))
        if not text:
            continue
        out.append(ParsedLine(len(out), start_ms, end_ms, None, text))
    return out


def _parse_ass(content: str) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    fmt: list[str] = []
    in_events = False
    for raw in content.splitlines():
        line = raw.strip()
        if line == "[Events]":
            in_events = True
        elif line.startswith("[") and line.endswith("]"):
            in_events = False
        elif in_events and line.lower().startswith("format:"):
            fmt = [c.strip().lower() for c in line.split(":", 1)[1].split(",")]
        elif line.startswith("Dialogue:") and fmt:
            parts = line.split(":", 1)[1].split(",", len(fmt) - 1)
            row = dict(zip(fmt, parts))
            text = _clean(row.get("text", ""))
            if not text:
                continue
            speaker = (row.get("name") or "").strip() or None
            try:
                start_ms = _ass_time_to_ms(row.get("start", "0:0:0.0"))
                end_ms = _ass_time_to_ms(row.get("end", "0:0:0.0"))
            except ValueError:
                continue
            out.append(ParsedLine(len(out), start_ms, end_ms, speaker, text))
    return out


def parse_subtitle(content: str, fmt: str) -> list[ParsedLine]:
    """fmt: 'srt' 或 'ass'（大小写不敏感）。返回按时间排序的 ParsedLine 列表。"""
    fmt = fmt.lower().lstrip(".")
    if fmt == "srt":
        lines = _parse_srt(content)
    elif fmt == "ass":
        lines = _parse_ass(content)
    else:
        raise ValueError(f"不支持的字幕格式: {fmt}")
    lines.sort(key=lambda x: (x.start_ms or 0))
    for i, ln in enumerate(lines):
        ln.idx = i
    return lines
