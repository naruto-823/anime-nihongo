from pathlib import Path

from app.services.subtitles import parse_subtitle

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_srt():
    lines = parse_subtitle((FIXTURES / "sample.srt").read_text(encoding="utf-8"), "srt")
    assert len(lines) == 2
    assert lines[0].idx == 0
    assert lines[0].start_ms == 1000
    assert lines[0].end_ms == 4000
    assert lines[0].text == "おはよう、元気？"
    # 多行文本合并为一行
    assert "今日はいい天気だね" in lines[1].text


def test_parse_ass_strips_tags_and_reads_speaker():
    lines = parse_subtitle((FIXTURES / "sample.ass").read_text(encoding="utf-8"), "ass")
    assert len(lines) == 2
    assert lines[0].text == "おはよう、元気？"  # {\i1} 等标签被剥离
    assert lines[0].speaker == "アキラ"
    assert lines[0].start_ms == 1000
    assert lines[1].text == "うん、まあまあ。"  # \N 换行转空白后规整
    assert lines[1].speaker is None


def test_parse_detects_format_from_filename():
    lines = parse_subtitle((FIXTURES / "sample.srt").read_text(encoding="utf-8"), "SRT")
    assert len(lines) == 2


def test_parse_unsupported_format_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_subtitle("whatever", "vtt")
