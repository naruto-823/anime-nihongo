# 追番日语 Phase 1 · Plan 2：学习引擎与后端 API 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1 的后端引擎之上，实现 SRS 间隔重复、语法小测、角色对话、今日训练编排四个学习引擎模块，以及一套完整的 FastAPI HTTP API，让前端（Plan 3）有接口可接。

**Architecture:** 学习引擎为 `app/services/` 下的纯逻辑/服务模块（SRS 为纯函数，对话/小测经 `llm.call_json`）。HTTP 层为 FastAPI：`app/main.py` 提供 ASGI app、DB 会话依赖、CORS、静态托管；`app/api/` 下按域分路由模块。路由通过 `Depends(get_db)` 拿会话，测试用 `TestClient` + 依赖覆盖 + 内存 SQLite，LLM 在边界处打桩。

**Tech Stack:** 沿用 Plan 1（FastAPI、SQLAlchemy 2.0、SQLite、anthropic SDK、pytest）。新增 `fastapi.testclient`（随 FastAPI 自带，依赖 `httpx`，已装）。

参考规格：`docs/superpowers/specs/2026-05-22-anime-japanese-phase1-design.md`（§5.3–5.7、§6、§7）。
前置：Plan 1 已合并入 master（models、subtitles、jimaku、tokenizer、llm、pipeline、cli 均可用）。

---

## 文件结构

```
backend/app/
  db.py                 # 修改：增加全局 SessionLocal 与 get_db 依赖
  main.py               # 新建：FastAPI app、CORS、静态托管、路由挂载
  services/
    srs.py              # 新建：SM-2 间隔重复算法 + 复习应用 + 到期查询
    grammar_quiz.py     # 新建：语法点小测生成与缓存
    conversation.py     # 新建：角色对话 + 对话反馈
    session.py          # 新建：今日训练编排（当前集、到期数、连续打卡、完成记录）
  api/
    __init__.py         # 新建
    series.py           # 新建：番剧 CRUD + Jimaku 搜索
    episodes.py         # 新建：剧集导入（上传/Jimaku）、详情、台词列表
    study.py            # 新建：今日训练、加入 SRS、精读进度、完成打卡
    srs.py              # 新建：到期复习项、提交评分
    grammar.py          # 新建：语法清单、语法小测
    conversation.py     # 新建：对话轮次、对话反馈
    progress.py         # 新建：进度汇总
backend/tests/
    test_srs.py / test_grammar_quiz.py / test_conversation.py / test_session.py
    test_api_series.py / test_api_episodes.py / test_api_study.py
    test_api_srs.py / test_api_grammar.py / test_api_conversation.py / test_api_progress.py
    conftest.py         # 修改：增加 FastAPI TestClient 夹具
```

每个路由模块单一域；服务模块单一职责。

---

## Task 1: SRS 间隔重复算法 srs.py

实现 SM-2 算法（规格 §7，本计划在其基础上修正"新卡 easy 区间"等边界）。

**Files:**
- Create: `backend/app/services/srs.py`
- Test: `backend/tests/test_srs.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_srs.py`:

```python
from datetime import date

from app.models import Vocab
from app.services.srs import (
    MASTERED_INTERVAL,
    SrsState,
    apply_review,
    is_mastered,
    next_state,
)


def test_new_card_good_then_good():
    s = next_state(SrsState(2.5, 0, 0, 0), "good")
    assert s.interval_days == 1 and s.reps == 1
    s2 = next_state(s, "good")
    assert s2.interval_days == 6 and s2.reps == 2


def test_again_resets_and_drops_ease():
    s = next_state(SrsState(2.5, 30, 5, 0), "again")
    assert s.interval_days == 0 and s.reps == 0 and s.lapses == 1
    assert abs(s.ease - 2.30) < 1e-9


def test_ease_floor():
    s = SrsState(1.3, 10, 3, 0)
    assert next_state(s, "again").ease == 1.3  # 不低于 1.3


def test_good_mature_multiplies_by_ease():
    s = next_state(SrsState(2.5, 10, 4, 0), "good")
    assert s.interval_days == 25  # round(10 * 2.5)


def test_easy_new_card():
    s = next_state(SrsState(2.5, 0, 0, 0), "easy")
    assert s.interval_days == 4 and abs(s.ease - 2.65) < 1e-9


def test_unknown_grade_raises():
    import pytest
    with pytest.raises(ValueError):
        next_state(SrsState(2.5, 0, 0, 0), "perfect")


def test_apply_review_mutates_model(db_session):
    v = Vocab(headword="本", reading="ほん", meaning_zh="书", in_srs=True)
    db_session.add(v)
    db_session.commit()
    apply_review(v, "good", today=date(2026, 5, 22))
    assert v.interval_days == 1
    assert v.due_date == date(2026, 5, 23)
    assert v.last_reviewed is not None


def test_is_mastered():
    assert is_mastered(SrsState(2.5, MASTERED_INTERVAL, 5, 0)) is True
    assert is_mastered(SrsState(2.5, 5, 2, 0)) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_srs.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.srs'`.

- [ ] **Step 3: 写实现** — `backend/app/services/srs.py`:

```python
from dataclasses import dataclass
from datetime import date, datetime, timedelta

GRADES = ("again", "hard", "good", "easy")
_MIN_EASE = 1.3
MASTERED_INTERVAL = 21  # interval_days ≥ 此值视为「已掌握」


@dataclass
class SrsState:
    ease: float
    interval_days: int
    reps: int
    lapses: int


def next_state(state: SrsState, grade: str) -> SrsState:
    """按 SM-2 计算下一个 SRS 状态。grade ∈ GRADES。"""
    if grade not in GRADES:
        raise ValueError(f"未知评分: {grade}")
    ease, interval, reps, lapses = (
        state.ease, state.interval_days, state.reps, state.lapses)
    if grade == "again":
        return SrsState(max(_MIN_EASE, ease - 0.20), 0, 0, lapses + 1)
    if grade == "hard":
        new_interval = 1 if reps == 0 else max(1, round(interval * 1.2))
        return SrsState(max(_MIN_EASE, ease - 0.15), new_interval, reps + 1, lapses)
    if grade == "good":
        if reps == 0:
            new_interval = 1
        elif reps == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval * ease))
        return SrsState(ease, new_interval, reps + 1, lapses)
    # easy
    new_ease = ease + 0.15
    if reps == 0:
        new_interval = 4
    elif reps == 1:
        new_interval = 10
    else:
        new_interval = max(1, round(interval * new_ease * 1.3))
    return SrsState(new_ease, new_interval, reps + 1, lapses)


def is_mastered(state: SrsState) -> bool:
    return state.interval_days >= MASTERED_INTERVAL


def apply_review(item, grade: str, today: date | None = None) -> None:
    """把一次复习评分应用到 Vocab / GrammarPoint 模型对象（鸭子类型）。"""
    today = today or date.today()
    st = next_state(
        SrsState(item.ease, item.interval_days, item.reps, item.lapses), grade)
    item.ease = st.ease
    item.interval_days = st.interval_days
    item.reps = st.reps
    item.lapses = st.lapses
    item.due_date = today + timedelta(days=st.interval_days)
    item.last_reviewed = datetime.now()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_srs.py -v`
Expected: 8 tests PASS.

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/srs.py backend/tests/test_srs.py
git commit -m "feat: SRS 间隔重复算法"
```

---

## Task 2: 语法小测服务 grammar_quiz.py

为语法 SRS 复习生成小测题，缓存在 `GrammarPoint.quiz_cache`。

**Files:**
- Create: `backend/app/services/grammar_quiz.py`
- Test: `backend/tests/test_grammar_quiz.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_grammar_quiz.py`:

```python
from app.models import GrammarPoint
from app.services import grammar_quiz


def _fake_quiz_llm(system, user, model=None, max_tokens=8000):
    return {"quiz": [
        {"question": "下線部に入るのは？　努力___、成功はない。",
         "options": ["なくして", "ながら", "ばかり", "つつ"],
         "answer": "なくして", "explain": "〜なくして（は）表示必要条件"},
        {"question": "「努力なくして成功なし」の意味は？",
         "options": ["不努力就没有成功", "努力很累", "成功很难", "努力之后"],
         "answer": "不努力就没有成功", "explain": "强调必要条件"},
    ]}


def test_get_quiz_generates_and_caches(db_session, monkeypatch):
    monkeypatch.setattr(grammar_quiz.llm, "call_json", _fake_quiz_llm)
    gp = GrammarPoint(key="nakushite", name="〜なくして", jlpt_level="N1",
                      explanation="没有…就（没有）", curated=True)
    db_session.add(gp)
    db_session.commit()

    q1 = grammar_quiz.get_quiz(db_session, gp)
    assert q1["answer"] == "なくして"
    assert gp.quiz_cache is not None and len(gp.quiz_cache) >= 1
    # 第二次从缓存取，不再调用 LLM
    monkeypatch.setattr(grammar_quiz.llm, "call_json",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("不应再调用")))
    q2 = grammar_quiz.get_quiz(db_session, gp)
    assert "question" in q2


def test_get_quiz_regenerates_when_cache_empty(db_session, monkeypatch):
    calls = []

    def counting(system, user, model=None, max_tokens=8000):
        calls.append(1)
        return _fake_quiz_llm(system, user)

    monkeypatch.setattr(grammar_quiz.llm, "call_json", counting)
    gp = GrammarPoint(key="nakushite", name="〜なくして", jlpt_level="N1",
                      explanation="没有…就", curated=True, quiz_cache=[])
    db_session.add(gp)
    db_session.commit()
    grammar_quiz.get_quiz(db_session, gp)
    assert len(calls) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_grammar_quiz.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.grammar_quiz'`.

- [ ] **Step 3: 写实现** — `backend/app/services/grammar_quiz.py`:

```python
import random

from sqlalchemy.orm import Session

from app.models import GrammarPoint
from app.services import llm

_SYSTEM = """你是日语语法出题助手。给定一个语法点，出 4 道面向 N2 学习者的小测题。
只返回 JSON 对象，不要多余文字。结构：
{"quiz": [
  {"question": "题干（可含填空线 ___）",
   "options": ["选项1","选项2","选项3","选项4"],
   "answer": "正确选项的文本（必须与 options 之一完全一致）",
   "explain": "简短中文讲解"}
]}
题目要考查该语法点的用法，options 必须有且仅有 4 个，answer 必须是其中之一。"""


def _generate(point: GrammarPoint) -> list[dict]:
    user = f"语法点：{point.name}\nJLPT：{point.jlpt_level}\n释义：{point.explanation}"
    result = llm.call_json(system=_SYSTEM, user=user)
    quiz = result.get("quiz", [])
    return [q for q in quiz if q.get("question") and q.get("answer")]


def get_quiz(session: Session, point: GrammarPoint) -> dict:
    """取该语法点的一道小测题。缓存空/耗尽时经 LLM 生成并写入 quiz_cache。"""
    cache = point.quiz_cache or []
    if not cache:
        cache = _generate(point)
        if not cache:
            raise RuntimeError(f"语法点 {point.key} 小测生成失败")
        point.quiz_cache = cache
        session.commit()
    return random.choice(cache)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_grammar_quiz.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/grammar_quiz.py backend/tests/test_grammar_quiz.py
git commit -m "feat: 语法小测服务"
```

---

## Task 3: 角色对话服务 conversation.py

Claude 扮演当前番里的角色与用户对话；结束给纠错反馈。

**Files:**
- Create: `backend/app/services/conversation.py`
- Test: `backend/tests/test_conversation.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_conversation.py`:

```python
from app.services import conversation


def _fake_turn_llm(system, user, model=None, max_tokens=8000):
    assert "アキラ" in system  # 角色名进了 system
    return {"reply": "うん、面白かったね。君はどう思った？"}


def _fake_feedback_llm(system, user, model=None, max_tokens=8000):
    return {
        "corrections": [
            {"original": "私は思う面白い", "fixed": "面白いと思う",
             "explain": "「と思う」前面用普通形"}
        ],
        "suggestions": ["可以多用「〜と思う」表达看法"],
        "new_vocab": [{"headword": "感想", "reading": "かんそう", "meaning_zh": "感想"}],
        "weak_grammar_keys": ["to-omou"],
    }


def test_converse_returns_reply(monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", _fake_turn_llm)
    out = conversation.converse(
        series_title="サンプル", episode_number=1, character="アキラ",
        history=[{"role": "user", "text": "今日のエピソードどうだった？"}],
        user_text="面白かったよ")
    assert out["reply"].startswith("うん")


def test_conversation_feedback_structure(monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", _fake_feedback_llm)
    fb = conversation.conversation_feedback(
        series_title="サンプル", episode_number=1,
        history=[{"role": "user", "text": "私は思う面白い"}])
    assert fb["corrections"][0]["fixed"] == "面白いと思う"
    assert fb["weak_grammar_keys"] == ["to-omou"]
    assert fb["new_vocab"][0]["headword"] == "感想"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_conversation.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.conversation'`.

- [ ] **Step 3: 写实现** — `backend/app/services/conversation.py`:

```python
import json

from app.services import llm

_TURN_SYSTEM = """你在用日语和一名中国 N2 学习者做口语对话练习。
你要扮演动漫《{series}》第 {number} 集里的角色「{character}」，用该角色的口吻、
普通体（タメ口）自然对话，话题围绕这一集的剧情。每次只回 1–3 句，口语化，
适当反问以推动对话。只返回 JSON：{{"reply": "你的日语回复"}}。"""

_FEEDBACK_SYSTEM = """你是日语口语老师。下面是一名中国 N2 学习者在围绕动漫
《{series}》第 {number} 集的对话中说过的日语。请复盘他的发言，只返回 JSON 对象：
{{
  "corrections": [{{"original": "原句", "fixed": "更自然的说法", "explain": "中文讲解"}}],
  "suggestions": ["中文改进建议"],
  "new_vocab": [{{"headword": "辞书形", "reading": "假名", "meaning_zh": "中文释义"}}],
  "weak_grammar_keys": ["从对话暴露出的薄弱语法点，用 kebab-case key，可空"]
}}
只针对学习者（role=user）的发言点评。"""


def _history_text(history: list[dict]) -> str:
    role_label = {"user": "学习者", "assistant": "角色"}
    return "\n".join(
        f"{role_label.get(h['role'], h['role'])}: {h['text']}" for h in history)


def converse(series_title: str, episode_number: int, character: str,
             history: list[dict], user_text: str) -> dict:
    """进行一轮角色对话。history 为既往轮次，user_text 为本轮用户发言。返回 {"reply": ...}。"""
    system = _TURN_SYSTEM.format(
        series=series_title, number=episode_number, character=character)
    convo = history + [{"role": "user", "text": user_text}]
    user = json.dumps({"对话历史": _history_text(convo)}, ensure_ascii=False)
    result = llm.call_json(system=system, user=user)
    return {"reply": result.get("reply", "")}


def conversation_feedback(series_title: str, episode_number: int,
                          history: list[dict]) -> dict:
    """对整段对话里学习者的发言做复盘反馈。"""
    system = _FEEDBACK_SYSTEM.format(series=series_title, number=episode_number)
    user = json.dumps({"对话历史": _history_text(history)}, ensure_ascii=False)
    result = llm.call_json(system=system, user=user)
    return {
        "corrections": result.get("corrections", []),
        "suggestions": result.get("suggestions", []),
        "new_vocab": result.get("new_vocab", []),
        "weak_grammar_keys": result.get("weak_grammar_keys", []),
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_conversation.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/conversation.py backend/tests/test_conversation.py
git commit -m "feat: 角色对话服务"
```

---

## Task 4: 今日训练编排 session.py

提供今日训练所需的查询/记录助手：当前集、到期数、连续打卡、完成记录。

**Files:**
- Create: `backend/app/services/session.py`
- Test: `backend/tests/test_session.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_session.py`:

```python
from datetime import date, timedelta

from app.models import DailySession, Episode, GrammarPoint, Series, Vocab
from app.services import session as sess


def test_current_episode_picks_current_series_unfinished(db_session):
    s = Series(title="番A", is_current=True)
    done = Episode(series=s, number=1, source="upload", status="ready",
                   reading_done=True)
    cur = Episode(series=s, number=2, source="upload", status="ready",
                  reading_done=False)
    db_session.add(s)
    db_session.commit()
    ep = sess.current_episode(db_session)
    assert ep is not None and ep.number == 2


def test_due_counts(db_session):
    today = date(2026, 5, 22)
    db_session.add_all([
        Vocab(headword="A", reading="あ", meaning_zh="a", in_srs=True,
              due_date=today),
        Vocab(headword="B", reading="び", meaning_zh="b", in_srs=True,
              due_date=today + timedelta(days=3)),  # 未到期
        GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x",
                     in_srs=True, due_date=today - timedelta(days=1)),
    ])
    db_session.commit()
    counts = sess.due_counts(db_session, today)
    assert counts["vocab"] == 1
    assert counts["grammar"] == 1


def test_compute_streak(db_session):
    today = date(2026, 5, 22)
    for d in (today, today - timedelta(days=1), today - timedelta(days=2)):
        db_session.add(DailySession(date=d, completed=True))
    db_session.add(DailySession(date=today - timedelta(days=4), completed=True))
    db_session.commit()
    assert sess.compute_streak(db_session, today) == 3


def test_record_completion_upserts(db_session):
    today = date(2026, 5, 22)
    sess.record_completion(db_session, today, episode_id=None,
                           stats={"vocab_reviewed": 5})
    row = db_session.query(DailySession).filter_by(date=today).one()
    assert row.completed is True and row.vocab_reviewed == 5
    # 再次调用：更新而非重复插入
    sess.record_completion(db_session, today, episode_id=None,
                           stats={"vocab_reviewed": 9})
    assert db_session.query(DailySession).filter_by(date=today).count() == 1
    assert db_session.query(DailySession).filter_by(date=today).one().vocab_reviewed == 9
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_session.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.session'`.

- [ ] **Step 3: 写实现** — `backend/app/services/session.py`:

```python
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import DailySession, Episode, GrammarPoint, Series, Vocab

_STAT_FIELDS = ("vocab_reviewed", "grammar_reviewed", "lines_read",
                "conversation_turns")


def current_episode(session: Session) -> Episode | None:
    """当前主攻番里、最该推进的一集：优先精读未完成、集数最小者；否则集数最大者。"""
    series = session.query(Series).filter_by(is_current=True).first()
    if series is None:
        return None
    episodes = (
        session.query(Episode)
        .filter_by(series_id=series.id, status="ready")
        .order_by(Episode.number)
        .all()
    )
    if not episodes:
        return None
    unfinished = [e for e in episodes if not e.reading_done]
    return unfinished[0] if unfinished else episodes[-1]


def due_counts(session: Session, today: date) -> dict:
    """到期待复习的词汇 / 语法数量。"""
    vocab = (
        session.query(Vocab)
        .filter(Vocab.in_srs.is_(True), Vocab.due_date <= today)
        .count()
    )
    grammar = (
        session.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True), GrammarPoint.due_date <= today)
        .count()
    )
    return {"vocab": vocab, "grammar": grammar}


def compute_streak(session: Session, today: date) -> int:
    """连续打卡天数：从 today 往回数连续 completed 的 DailySession。"""
    completed = {
        r.date
        for r in session.query(DailySession).filter_by(completed=True).all()
    }
    streak = 0
    cursor = today
    while cursor in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def record_completion(session: Session, today: date, episode_id: int | None,
                       stats: dict) -> DailySession:
    """记录/更新今天的训练完成情况（按日期 upsert）。"""
    row = session.query(DailySession).filter_by(date=today).first()
    if row is None:
        row = DailySession(date=today)
        session.add(row)
    row.completed = True
    row.episode_id = episode_id
    for field in _STAT_FIELDS:
        if field in stats:
            setattr(row, field, stats[field])
    if "summary" in stats:
        row.summary = stats["summary"]
    session.commit()
    return row
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_session.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/session.py backend/tests/test_session.py
git commit -m "feat: 今日训练编排助手"
```

---

## Task 5: FastAPI 应用骨架 main.py

**Files:**
- Modify: `backend/app/db.py`（增加全局 `SessionLocal` 与 `get_db` 依赖）
- Create: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`（增加 `client` 夹具，覆盖 `get_db`）
- Test: `backend/tests/test_api_health.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_health.py`:

```python
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_health.py -v`
Expected: FAIL（`client` 夹具不存在 / `app.main` 不存在）。

- [ ] **Step 3: 改 `db.py`** —— 在 `backend/app/db.py` 末尾追加全局会话工厂与依赖：

```python
from collections.abc import Iterator

from app.config import settings

_engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(_engine)


def init_app_db() -> None:
    """应用启动时建表。"""
    init_db(_engine)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

（`make_engine` / `make_session_factory` / `init_db` / `Session` 已在 `db.py` 内，无需重复导入；只新增 `Iterator` 和 `settings` 的导入。）

- [ ] **Step 4: 写 `main.py`** — `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_app_db
from app.grammar_loader import load_grammar_seed
from app.db import SessionLocal


def create_app() -> FastAPI:
    app = FastAPI(title="追番日语 API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # 前端开发服务器
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_app_db()
        db = SessionLocal()
        try:
            load_grammar_seed(db)
        finally:
            db.close()

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: 改 `conftest.py`** —— 整个替换 `backend/tests/conftest.py` 为下面内容（`db_session` 夹具保持与之前一致，新增 `client` 夹具）：

```python
import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_db, make_engine, make_session_factory
from app.main import app


@pytest.fixture
def db_session():
    engine = make_engine("sqlite://")
    init_db(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient，get_db 依赖覆盖为测试用的内存会话。

    刻意不使用 `with TestClient(...)`：不触发 startup/shutdown 生命周期事件，
    避免 startup 里的 init_app_db / load_grammar_seed 操作真实文件库。
    测试库由 db_session 夹具建表；需要语法种子的测试自行调用 load_grammar_seed。
    """
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

说明：不进入 `TestClient` 的上下文管理器，`startup` 不会触发，所以测试不会去碰真实的 `data/anime-nihongo.db` 文件库；HTTP 请求本身不需要 `with` 也能正常工作。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_health.py -v`
Expected: PASS。再跑全量 `make test` 确认无回归。

- [ ] **Step 7: 提交**

```bash
git add backend/app/db.py backend/app/main.py backend/tests/conftest.py backend/tests/test_api_health.py
git commit -m "feat: FastAPI 应用骨架与测试夹具"
```

---

## Task 6: 番剧与剧集导入路由

**Files:**
- Create: `backend/app/api/__init__.py`（空文件）
- Create: `backend/app/api/series.py`
- Create: `backend/app/api/episodes.py`
- Modify: `backend/app/main.py`（挂载这两个路由）
- Test: `backend/tests/test_api_series.py`、`backend/tests/test_api_episodes.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_series.py`:

```python
from app.models import Series


def test_create_and_list_series(client, db_session):
    resp = client.post("/api/series", json={"title": "鬼灭之刃"})
    assert resp.status_code == 200
    sid = resp.json()["id"]

    listed = client.get("/api/series").json()
    assert any(s["id"] == sid and s["title"] == "鬼灭之刃" for s in listed)


def test_set_current_series(client, db_session):
    a = client.post("/api/series", json={"title": "A"}).json()["id"]
    b = client.post("/api/series", json={"title": "B"}).json()["id"]
    client.post(f"/api/series/{a}/set-current")
    client.post(f"/api/series/{b}/set-current")
    rows = {s.id: s.is_current for s in db_session.query(Series).all()}
    assert rows[a] is False and rows[b] is True  # 全局至多一个 current
```

`backend/tests/test_api_episodes.py`:

```python
from pathlib import Path

from app.services import pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_file_creates_episode(client, db_session, monkeypatch):
    from tests.test_pipeline import _fake_llm
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)

    sid = client.post("/api/series", json={"title": "测试番"}).json()["id"]
    with open(FIXTURES / "sample.srt", "rb") as f:
        resp = client.post(
            "/api/episodes/import-file",
            data={"series_id": str(sid), "number": "1"},
            files={"file": ("sample.srt", f, "text/plain")},
        )
    assert resp.status_code == 200
    ep = resp.json()
    assert ep["total_lines"] == 2

    detail = client.get(f"/api/episodes/{ep['id']}").json()
    assert detail["status"] == "ready"

    lines = client.get(f"/api/episodes/{ep['id']}/lines").json()
    assert len(lines) == 2
    assert lines[0]["text_jp"] == "おはよう、元気？"
    assert lines[0]["processed"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_series.py tests/test_api_episodes.py -v`
Expected: FAIL（路由不存在 → 404）。

- [ ] **Step 3: 写实现**

`backend/app/api/__init__.py`: 空文件。

`backend/app/api/series.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Series
from app.services.jimaku import JimakuClient, JimakuError

router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    title_jp: str | None = None
    jimaku_entry_id: int | None = None


def _series_dict(s: Series) -> dict:
    return {"id": s.id, "title": s.title, "title_jp": s.title_jp,
            "jimaku_entry_id": s.jimaku_entry_id, "is_current": s.is_current}


@router.get("")
def list_series(db: Session = Depends(get_db)) -> list[dict]:
    return [_series_dict(s) for s in db.query(Series).order_by(Series.id).all()]


@router.post("")
def create_series(body: SeriesCreate, db: Session = Depends(get_db)) -> dict:
    s = Series(title=body.title, title_jp=body.title_jp,
               jimaku_entry_id=body.jimaku_entry_id)
    db.add(s)
    db.commit()
    return _series_dict(s)


@router.post("/{series_id}/set-current")
def set_current(series_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
    for other in db.query(Series).filter(Series.is_current.is_(True)).all():
        other.is_current = False
    s.is_current = True
    db.commit()
    return _series_dict(s)


@router.get("/search-jimaku")
def search_jimaku(query: str) -> list[dict]:
    if not settings.jimaku_api_token:
        raise HTTPException(400, "未配置 JIMAKU_API_TOKEN")
    try:
        return JimakuClient(settings.jimaku_api_token).search_entries(query)
    except JimakuError as exc:
        raise HTTPException(502, str(exc)) from exc
```

`backend/app/api/episodes.py`:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Episode, Line, Series
from app.services import pipeline
from app.services.jimaku import JimakuClient, JimakuError
from app.services.subtitles import parse_subtitle

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def _episode_dict(e: Episode) -> dict:
    return {"id": e.id, "series_id": e.series_id, "number": e.number,
            "title": e.title, "status": e.status,
            "total_lines": e.total_lines, "processed_lines": e.processed_lines,
            "read_position": e.read_position, "reading_done": e.reading_done}


def _line_dict(ln: Line) -> dict:
    return {"id": ln.id, "idx": ln.idx, "start_ms": ln.start_ms,
            "end_ms": ln.end_ms, "speaker": ln.speaker, "text_jp": ln.text_jp,
            "furigana": ln.furigana, "translation_zh": ln.translation_zh,
            "grammar_notes": ln.grammar_notes, "register_tag": ln.register_tag,
            "grammar_point_keys": ln.grammar_point_keys,
            "processed": ln.processed}


def _import_lines(db: Session, series_id: int, number: int,
                  source: str, content: str, fmt: str) -> Episode:
    parsed = parse_subtitle(content, fmt)
    if not parsed:
        raise HTTPException(400, "字幕未解析出任何台词")
    if db.get(Series, series_id) is None:
        raise HTTPException(404, "番剧不存在")
    if db.query(Episode).filter_by(series_id=series_id, number=number).first():
        raise HTTPException(409, f"第 {number} 集已存在")
    ep = Episode(series_id=series_id, number=number, source=source,
                 status="processing", total_lines=len(parsed))
    for p in parsed:
        ep.lines.append(Line(idx=p.idx, start_ms=p.start_ms, end_ms=p.end_ms,
                             speaker=p.speaker, text_jp=p.text, processed=False))
    db.add(ep)
    db.commit()
    return ep


@router.post("/import-file")
def import_file(series_id: int = Form(...), number: int = Form(...),
                file: UploadFile = File(...),
                db: Session = Depends(get_db)) -> dict:
    raw = file.file.read().decode("utf-8", errors="ignore")
    fmt = (file.filename or "x.srt").rsplit(".", 1)[-1]
    ep = _import_lines(db, series_id, number, "upload", raw, fmt)
    pipeline.process_episode(db, ep.id)
    db.refresh(ep)
    return _episode_dict(ep)


class JimakuImport(BaseModel):
    series_id: int
    number: int
    file_url: str


@router.post("/import-jimaku")
def import_jimaku(body: JimakuImport, db: Session = Depends(get_db)) -> dict:
    if not settings.jimaku_api_token:
        raise HTTPException(400, "未配置 JIMAKU_API_TOKEN")
    try:
        content = JimakuClient(settings.jimaku_api_token).download_file(body.file_url)
    except JimakuError as exc:
        raise HTTPException(502, str(exc)) from exc
    fmt = body.file_url.rsplit(".", 1)[-1]
    ep = _import_lines(db, body.series_id, body.number, "jimaku", content, fmt)
    pipeline.process_episode(db, ep.id)
    db.refresh(ep)
    return _episode_dict(ep)


@router.get("/{episode_id}")
def get_episode(episode_id: int, db: Session = Depends(get_db)) -> dict:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    return _episode_dict(ep)


@router.get("/{episode_id}/lines")
def get_lines(episode_id: int, db: Session = Depends(get_db)) -> list[dict]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    lines = db.query(Line).filter_by(episode_id=episode_id).order_by(Line.idx).all()
    return [_line_dict(ln) for ln in lines]
```

在 `backend/app/main.py` 的 `create_app()` 内，`return app` 之前挂载路由：

```python
    from app.api import series, episodes
    app.include_router(series.router)
    app.include_router(episodes.router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_series.py tests/test_api_episodes.py -v`
Expected: 全部 PASS。`pipeline.process_episode` 同步执行（Phase 1 简化：导入即同步加工，测试里 LLM 已打桩）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_series.py backend/tests/test_api_episodes.py
git commit -m "feat: 番剧与剧集导入路由"
```

---

## Task 7: 今日训练与学习动作路由 study.py

**Files:**
- Create: `backend/app/api/study.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_api_study.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_study.py`:

```python
from datetime import date

from app.models import Episode, GrammarPoint, Line, Series, Vocab


def _ready_episode(db_session):
    s = Series(title="番", is_current=True)
    ep = Episode(series=s, number=1, source="upload", status="ready",
                 total_lines=1, reading_done=False)
    ln = Line(episode=ep, idx=0, text_jp="猫が好き", processed=True,
              grammar_point_keys=["mai"])
    db_session.add(s)
    db_session.commit()
    return ep, ln


def test_today_returns_plan(client, db_session):
    _ready_episode(db_session)
    resp = client.get("/api/study/today")
    assert resp.status_code == 200
    body = resp.json()
    assert "due" in body and "current_episode" in body and "streak" in body
    assert body["current_episode"]["number"] == 1


def test_add_vocab_to_srs(client, db_session):
    ep, ln = _ready_episode(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", source_line_id=ln.id)
    db_session.add(v)
    db_session.commit()
    resp = client.post(f"/api/study/vocab/{v.id}/add-srs")
    assert resp.status_code == 200
    db_session.refresh(v)
    assert v.in_srs is True and v.due_date is not None


def test_add_grammar_to_srs(client, db_session):
    gp = GrammarPoint(key="mai", name="〜まい", jlpt_level="N2",
                      explanation="x", status="seen")
    db_session.add(gp)
    db_session.commit()
    resp = client.post(f"/api/study/grammar/{gp.id}/add-srs")
    assert resp.status_code == 200
    db_session.refresh(gp)
    assert gp.in_srs is True and gp.status == "learning"


def test_reading_progress_and_complete(client, db_session):
    ep, _ = _ready_episode(db_session)
    client.post(f"/api/study/episodes/{ep.id}/reading-progress",
                json={"position": 1})
    db_session.refresh(ep)
    assert ep.read_position == 1

    resp = client.post("/api/study/complete-today",
                       json={"episode_id": ep.id, "vocab_reviewed": 3})
    assert resp.status_code == 200
    assert resp.json()["streak"] >= 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_study.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写实现** — `backend/app/api/study.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Episode, GrammarPoint, Vocab
from app.services import session as sess

router = APIRouter(prefix="/api/study", tags=["study"])


@router.get("/today")
def today(db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    ep = sess.current_episode(db)
    return {
        "due": sess.due_counts(db, today_d),
        "current_episode": (
            {"id": ep.id, "number": ep.number, "title": ep.title,
             "read_position": ep.read_position, "total_lines": ep.total_lines,
             "reading_done": ep.reading_done}
            if ep else None
        ),
        "streak": sess.compute_streak(db, today_d),
    }


@router.post("/vocab/{vocab_id}/add-srs")
def add_vocab(vocab_id: int, db: Session = Depends(get_db)) -> dict:
    v = db.get(Vocab, vocab_id)
    if v is None:
        raise HTTPException(404, "词条不存在")
    v.in_srs = True
    if v.due_date is None:
        v.due_date = date.today()
    db.commit()
    return {"id": v.id, "in_srs": True}


@router.post("/grammar/{grammar_id}/add-srs")
def add_grammar(grammar_id: int, db: Session = Depends(get_db)) -> dict:
    gp = db.get(GrammarPoint, grammar_id)
    if gp is None:
        raise HTTPException(404, "语法点不存在")
    gp.in_srs = True
    gp.status = "learning"
    if gp.due_date is None:
        gp.due_date = date.today()
    db.commit()
    return {"id": gp.id, "in_srs": True, "status": gp.status}


class ReadingProgress(BaseModel):
    position: int


@router.post("/episodes/{episode_id}/reading-progress")
def reading_progress(episode_id: int, body: ReadingProgress,
                     db: Session = Depends(get_db)) -> dict:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    ep.read_position = body.position
    if body.position >= ep.total_lines:
        ep.reading_done = True
    db.commit()
    return {"id": ep.id, "read_position": ep.read_position,
            "reading_done": ep.reading_done}


class CompleteToday(BaseModel):
    episode_id: int | None = None
    vocab_reviewed: int = 0
    grammar_reviewed: int = 0
    lines_read: int = 0
    conversation_turns: int = 0
    summary: dict | None = None


@router.post("/complete-today")
def complete_today(body: CompleteToday, db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    stats = body.model_dump(exclude={"episode_id"}, exclude_none=True)
    sess.record_completion(db, today_d, body.episode_id, stats)
    return {"streak": sess.compute_streak(db, today_d)}
```

在 `main.py` 挂载：`from app.api import study` / `app.include_router(study.router)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_study.py -v`
Expected: 4 tests PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/study.py backend/app/main.py backend/tests/test_api_study.py
git commit -m "feat: 今日训练与学习动作路由"
```

---

## Task 8: SRS 复习路由 srs.py

**Files:**
- Create: `backend/app/api/srs.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_api_srs.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_srs.py`:

```python
from datetime import date

from app.models import GrammarPoint, Line, Vocab


def test_due_lists_only_due_in_srs_items(client, db_session):
    today = date.today()
    db_session.add_all([
        Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=today),
        Vocab(headword="犬", reading="いぬ", meaning_zh="狗", in_srs=False),
    ])
    db_session.commit()
    body = client.get("/api/srs/due").json()
    heads = [v["headword"] for v in body["vocab"]]
    assert heads == ["猫"]


def test_review_vocab_advances_state(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=date.today())
    db_session.add(v)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "good"})
    assert resp.status_code == 200
    db_session.refresh(v)
    assert v.interval_days == 1 and v.reps == 1


def test_review_rejects_bad_grade(client, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=date.today())
    db_session.add(v)
    db_session.commit()
    resp = client.post("/api/srs/review",
                       json={"item_type": "vocab", "item_id": v.id,
                             "grade": "perfect"})
    assert resp.status_code == 422
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_srs.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写实现** — `backend/app/api/srs.py`:

```python
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GrammarPoint, Line, Vocab
from app.services.srs import GRADES, apply_review

router = APIRouter(prefix="/api/srs", tags=["srs"])


@router.get("/due")
def due(db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vocab = (
        db.query(Vocab)
        .filter(Vocab.in_srs.is_(True), Vocab.due_date <= today)
        .order_by(Vocab.due_date)
        .all()
    )
    grammar = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True), GrammarPoint.due_date <= today)
        .order_by(GrammarPoint.due_date)
        .all()
    )
    vocab_out = []
    for v in vocab:
        line = db.get(Line, v.source_line_id) if v.source_line_id else None
        vocab_out.append({
            "id": v.id, "headword": v.headword, "reading": v.reading,
            "meaning_zh": v.meaning_zh, "pos": v.pos,
            "context": line.text_jp if line else None,
        })
    grammar_out = [
        {"id": g.id, "key": g.key, "name": g.name, "jlpt_level": g.jlpt_level,
         "explanation": g.explanation}
        for g in grammar
    ]
    return {"vocab": vocab_out, "grammar": grammar_out}


class ReviewBody(BaseModel):
    item_type: Literal["vocab", "grammar"]
    item_id: int
    grade: Literal["again", "hard", "good", "easy"]


@router.post("/review")
def review(body: ReviewBody, db: Session = Depends(get_db)) -> dict:
    model = Vocab if body.item_type == "vocab" else GrammarPoint
    item = db.get(model, body.item_id)
    if item is None:
        raise HTTPException(404, "复习项不存在")
    apply_review(item, body.grade)
    db.commit()
    return {"id": item.id, "interval_days": item.interval_days,
            "reps": item.reps, "due_date": item.due_date.isoformat()}
```

注：`GRADES` 仅用于文档对照；评分合法性由 Pydantic `Literal` 在 422 层把关（`test_review_rejects_bad_grade` 验证）。若 ruff 报 `GRADES` 未使用（F401），从 import 中删除它（保留 `apply_review`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_srs.py -v`
Expected: 3 tests PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/srs.py backend/app/main.py backend/tests/test_api_srs.py
git commit -m "feat: SRS 复习路由"
```

---

## Task 9: 语法清单路由 grammar.py

**Files:**
- Create: `backend/app/api/grammar.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_api_grammar.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_grammar.py`:

```python
from app.models import GrammarPoint
from app.services import grammar_quiz


def test_checklist_groups_by_level(client, db_session):
    db_session.add_all([
        GrammarPoint(key="g-n2", name="〜N2点", jlpt_level="N2",
                     explanation="x", curated=True, status="locked"),
        GrammarPoint(key="g-n1", name="〜N1点", jlpt_level="N1",
                     explanation="y", curated=True, status="seen"),
    ])
    db_session.commit()
    body = client.get("/api/grammar/checklist").json()
    assert "N2" in body and "N1" in body
    assert body["N2"][0]["key"] == "g-n2"
    assert body["N1"][0]["status"] == "seen"


def test_grammar_quiz_endpoint(client, db_session, monkeypatch):
    monkeypatch.setattr(
        grammar_quiz.llm, "call_json",
        lambda **kw: {"quiz": [{"question": "Q?", "options": ["a", "b", "c", "d"],
                                "answer": "a", "explain": "e"}]})
    gp = GrammarPoint(key="g1", name="〜g1", jlpt_level="N2", explanation="x",
                      curated=True)
    db_session.add(gp)
    db_session.commit()
    body = client.get(f"/api/grammar/{gp.id}/quiz").json()
    assert body["answer"] == "a" and len(body["options"]) == 4
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_grammar.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写实现** — `backend/app/api/grammar.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GrammarPoint
from app.services import grammar_quiz
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/grammar", tags=["grammar"])


@router.get("/checklist")
def checklist(db: Session = Depends(get_db)) -> dict:
    """内置语法清单，按 JLPT 等级分组，带掌握状态。"""
    points = (
        db.query(GrammarPoint)
        .filter_by(curated=True)
        .order_by(GrammarPoint.jlpt_level, GrammarPoint.id)
        .all()
    )
    grouped: dict[str, list[dict]] = {}
    for g in points:
        mastered = g.in_srs and g.interval_days >= MASTERED_INTERVAL
        grouped.setdefault(g.jlpt_level, []).append({
            "id": g.id, "key": g.key, "name": g.name,
            "explanation": g.explanation, "status": g.status,
            "in_srs": g.in_srs, "mastered": mastered,
        })
    return grouped


@router.get("/{grammar_id}/quiz")
def quiz(grammar_id: int, db: Session = Depends(get_db)) -> dict:
    gp = db.get(GrammarPoint, grammar_id)
    if gp is None:
        raise HTTPException(404, "语法点不存在")
    try:
        return grammar_quiz.get_quiz(db, gp)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
```

在 `main.py` 挂载。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_grammar.py -v`
Expected: 2 tests PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/grammar.py backend/app/main.py backend/tests/test_api_grammar.py
git commit -m "feat: 语法清单路由"
```

---

## Task 10: 角色对话路由 conversation.py

**Files:**
- Create: `backend/app/api/conversation.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_api_conversation.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_conversation.py`:

```python
from app.models import Episode, GrammarPoint, Series, Vocab
from app.services import conversation


def _episode(db_session):
    s = Series(title="サンプル", is_current=True)
    ep = Episode(series=s, number=1, source="upload", status="ready")
    db_session.add(s)
    db_session.commit()
    return ep


def test_conversation_turn(client, db_session, monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json",
                        lambda **kw: {"reply": "そうだね。"})
    ep = _episode(db_session)
    resp = client.post("/api/conversation/turn", json={
        "episode_id": ep.id, "character": "アキラ",
        "history": [], "user_text": "こんにちは"})
    assert resp.status_code == 200
    assert resp.json()["reply"] == "そうだね。"


def test_conversation_feedback_mines_srs(client, db_session, monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", lambda **kw: {
        "corrections": [{"original": "x", "fixed": "y", "explain": "z"}],
        "suggestions": ["s"],
        "new_vocab": [{"headword": "感想", "reading": "かんそう",
                       "meaning_zh": "感想"}],
        "weak_grammar_keys": ["wk-gram"],
    })
    ep = _episode(db_session)
    db_session.add(GrammarPoint(key="wk-gram", name="〜wk", jlpt_level="N2",
                                explanation="x", status="seen"))
    db_session.commit()

    resp = client.post("/api/conversation/feedback", json={
        "episode_id": ep.id,
        "history": [{"role": "user", "text": "x"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["corrections"][0]["fixed"] == "y"
    # 新词进了 Vocab 并入 SRS；薄弱语法点入 SRS
    v = db_session.query(Vocab).filter_by(headword="感想").one()
    assert v.in_srs is True
    gp = db_session.query(GrammarPoint).filter_by(key="wk-gram").one()
    assert gp.in_srs is True and gp.status == "learning"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_conversation.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写实现** — `backend/app/api/conversation.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Episode, GrammarPoint, Series, Vocab
from app.services import conversation

router = APIRouter(prefix="/api/conversation", tags=["conversation"])


class Turn(BaseModel):
    episode_id: int
    character: str = "登場人物"
    history: list[dict] = []
    user_text: str


class Feedback(BaseModel):
    episode_id: int
    history: list[dict] = []


def _episode_ctx(db: Session, episode_id: int) -> tuple[str, int]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    series = db.get(Series, ep.series_id)
    return (series.title if series else "动漫"), ep.number


@router.post("/turn")
def turn(body: Turn, db: Session = Depends(get_db)) -> dict:
    title, number = _episode_ctx(db, body.episode_id)
    return conversation.converse(
        series_title=title, episode_number=number, character=body.character,
        history=body.history, user_text=body.user_text)


@router.post("/feedback")
def feedback(body: Feedback, db: Session = Depends(get_db)) -> dict:
    title, number = _episode_ctx(db, body.episode_id)
    fb = conversation.conversation_feedback(
        series_title=title, episode_number=number, history=body.history)
    # 新词入库并加入 SRS
    for item in fb.get("new_vocab", []):
        hw, rd = item.get("headword"), item.get("reading")
        if not hw or not rd:
            continue
        existing = db.query(Vocab).filter_by(headword=hw, reading=rd).first()
        if existing is None:
            db.add(Vocab(headword=hw, reading=rd,
                         meaning_zh=item.get("meaning_zh", ""),
                         in_srs=True, due_date=date.today()))
        else:
            existing.in_srs = True
            if existing.due_date is None:
                existing.due_date = date.today()
    # 薄弱语法点加入 SRS
    for key in fb.get("weak_grammar_keys", []):
        gp = db.query(GrammarPoint).filter_by(key=key).first()
        if gp is not None:
            gp.in_srs = True
            gp.status = "learning"
            if gp.due_date is None:
                gp.due_date = date.today()
    db.commit()
    return fb
```

在 `main.py` 挂载。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_conversation.py -v`
Expected: 2 tests PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/conversation.py backend/app/main.py backend/tests/test_api_conversation.py
git commit -m "feat: 角色对话路由"
```

---

## Task 11: 进度路由 progress.py

**Files:**
- Create: `backend/app/api/progress.py`
- Modify: `backend/app/main.py`（挂载）
- Test: `backend/tests/test_api_progress.py`

- [ ] **Step 1: 写失败测试** — `backend/tests/test_api_progress.py`:

```python
from datetime import date, timedelta

from app.models import DailySession, GrammarPoint, Vocab


def test_progress_summary(client, db_session):
    today = date.today()
    db_session.add_all([
        DailySession(date=today, completed=True),
        DailySession(date=today - timedelta(days=1), completed=True),
        Vocab(headword="猫", reading="ねこ", meaning_zh="猫", in_srs=True,
              due_date=today),
        GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x",
                     curated=True, in_srs=True, interval_days=30),
        GrammarPoint(key="g2", name="g2", jlpt_level="N2", explanation="y",
                     curated=True),
    ])
    db_session.commit()
    body = client.get("/api/progress").json()
    assert body["streak"] == 2
    assert body["vocab"]["in_srs"] == 1
    assert body["grammar"]["mastered"] == 1
    assert body["grammar"]["total_curated"] == 2
    assert len(body["history"]) == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_api_progress.py -v`
Expected: FAIL（404）。

- [ ] **Step 3: 写实现** — `backend/app/api/progress.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DailySession, GrammarPoint, Vocab
from app.services.session import compute_streak
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("")
def progress(db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vocab_in_srs = db.query(Vocab).filter(Vocab.in_srs.is_(True)).count()
    vocab_total = db.query(Vocab).count()
    curated = db.query(GrammarPoint).filter_by(curated=True).count()
    seen = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.curated.is_(True),
                GrammarPoint.status.in_(("seen", "learning")))
        .count()
    )
    mastered = (
        db.query(GrammarPoint)
        .filter(GrammarPoint.in_srs.is_(True),
                GrammarPoint.interval_days >= MASTERED_INTERVAL)
        .count()
    )
    history = [
        {"date": r.date.isoformat(), "completed": r.completed,
         "vocab_reviewed": r.vocab_reviewed,
         "grammar_reviewed": r.grammar_reviewed,
         "lines_read": r.lines_read}
        for r in db.query(DailySession).order_by(DailySession.date.desc()).all()
    ]
    return {
        "streak": compute_streak(db, today),
        "vocab": {"total": vocab_total, "in_srs": vocab_in_srs},
        "grammar": {"total_curated": curated, "encountered": seen,
                    "mastered": mastered},
        "history": history,
    }
```

在 `main.py` 挂载。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_api_progress.py -v`
Expected: 1 test PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/progress.py backend/app/main.py backend/tests/test_api_progress.py
git commit -m "feat: 进度路由"
```

---

## Task 12: 全量回归与 API 总装校验

**Files:**
- Modify: `backend/app/main.py`（确认全部 7 个路由已挂载；补静态托管占位）
- Test: `backend/tests/test_api_smoke.py`

- [ ] **Step 1: 写测试** — `backend/tests/test_api_smoke.py`:

```python
def test_openapi_lists_all_routers(client):
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in ("/api/series", "/api/episodes/{episode_id}",
                   "/api/study/today", "/api/srs/due",
                   "/api/grammar/checklist", "/api/conversation/turn",
                   "/api/progress"):
        assert prefix in paths, f"缺少路由 {prefix}"
```

- [ ] **Step 2: 确认 `main.py` 路由挂载完整**

确认 `create_app()` 内挂载了全部 7 个路由：`series, episodes, study, srs, grammar, conversation, progress`。整理 import：

```python
    from app.api import (
        conversation, episodes, grammar, progress, series, srs, study,
    )
    for module in (series, episodes, study, srs, grammar, conversation, progress):
        app.include_router(module.router)
```

并在 `health` 路由后增加静态托管占位（前端构建产物目录可能尚不存在，需容错）：

```python
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True),
                  name="frontend")
```

（`frontend/dist` 由 Plan 3 产生；不存在时跳过挂载，后端 API 仍可独立运行。）

- [ ] **Step 3: 跑全量测试与 lint**

Run: `make test && make lint`
Expected: 全部 PASS，ruff 干净。

- [ ] **Step 4: 提交**

```bash
git add backend/app/main.py backend/tests/test_api_smoke.py
git commit -m "feat: API 总装与冒烟校验"
```

---

## 验收标准

- `make test` 全绿（Plan 1 的 36 个 + Plan 2 新增）。`make lint` 干净。
- 配好 `.env`（fox key）后，`make dev` 能起后端，`GET /api/health` 返回 `{"status":"ok"}`，`/docs` 可见全部路由。
- 真实可走通：建番 → 上传字幕导入并加工 → 取台词 → 加生词/语法进 SRS → `/api/srs/due` 取到 → 提交复习评分 → `/api/study/today`、`/api/progress` 反映状态。

## 交付物

一套完整、可独立运行与测试的后端 HTTP API。Plan 3 在此之上实现 React 前端页面，构建产物落到 `frontend/dist/` 由后端静态托管。

## 已知遗留（移交 Plan 3 或后续）

- 字幕解析"坏行计数"目前只跳过不计数（规格 §8）；导入路由可在 Plan 3 联调时把跳过数纳入返回体。
- 剧集加工在导入请求内同步执行（Phase 1 简化）；真实长剧集加工耗时较长，Plan 3 联调时如体验不佳，再改为后台任务 + 轮询 `GET /api/episodes/{id}` 的 `status`/`processed_lines`。
