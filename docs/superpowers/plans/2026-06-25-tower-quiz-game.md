# 日语修炼塔(N5→N1 闯关题库)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已入库的 N5–N1 词/语法做成一座闯关塔(小关→Boss→升层),用模板生成的多题型(词义/读音/活用/语法)驱动学习,答错与新词自动进 SRS。

**Architecture:** 后端三层——`quiz_bank.py` 纯函数生成题目、`tower.py` 负责塔布局/进度/结算/SRS 打通、`api/tower.py` 暴露接口;数据新增 `TowerProgress`、`PlayerStats` 两表(由 `create_all` 自动建)。前端新增 `Tower.tsx`(塔地图)+ `Quiz.tsx`(答题),主导航加入口。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + SQLite(后端);React 18 + TS + react-query v5 + Tailwind(前端);pytest / vitest。

## Global Constraints

- 始终用中文做 UI 文案与释义。
- 后端 ruff line-length 120;`select = ["E","F","I","N","W"]`。新文件须通过 `.venv/bin/ruff check`。
- 题目**确定性模板生成、不入库**;随机性用 `random.Random(seed)` 注入以便测试。
- 通过线:小关正确率 ≥0.6/0.8/1.0 → 1/2/3 星,≥0.6 算通关;Boss ≥0.8 通过。**无红心**。
- XP:每答对 +10;番剧词(`Vocab.source_line_id` 非空)1.5×。服务端权威计算。
- SRS 打通复用 `app/services/srs.py`;新词 `in_srs=True`、`due_date=今天`;错题 `due_date=今天`,语法额外 `status="learning"`。
- 测试用内存库夹具 `db_session` / `client`(见 `tests/conftest.py`),不触发 startup。

---

## 文件结构

**后端**
- Create `app/models/game.py` — `TowerProgress`、`PlayerStats` 模型。
- Modify `app/models/__init__.py` — 导出新模型。
- Create `app/services/quiz_bank.py` — 题型生成纯函数。
- Create `app/services/tower.py` — 布局/进度/结算/SRS。
- Create `app/api/tower.py` — 接口。
- Modify `app/main.py` — 注册 router。

**前端**
- Modify `src/types.ts` — 类型。
- Modify `src/lib/api.ts` — 接口封装。
- Create `src/pages/Tower.tsx` — 塔地图。
- Create `src/pages/Quiz.tsx` — 答题界面。
- Modify `src/App.tsx` — 路由。
- Modify `src/components/Layout.tsx` — 导航入口。

**测试**:`tests/test_quiz_bank.py`、`tests/test_tower.py`、`tests/test_api_tower.py`;前端 `tests/tower.test.tsx`。

### 题目字典契约(全程一致)

```python
{
  "id": str,            # 如 "v123-meaning" / "g45-grammar"
  "type": str,          # "meaning" | "reading" | "conjugation" | "grammar"
  "prompt": str,        # 题面主文
  "hint": str | None,   # 副提示(如活用题的目标形 "て形")
  "options": list[str], # 4 个选项
  "answer": str,        # 正确选项(必在 options 内)
  "item": {"kind": str, "id": int},  # "vocab"|"grammar" + 主键,供 SRS
}
```

---

## Phase A — 题型引擎 `quiz_bank.py`

### Task 1: 词义选择题

**Files:**
- Create: `app/services/quiz_bank.py`
- Test: `tests/test_quiz_bank.py`

**Interfaces:**
- Produces: `vocab_meaning_q(target, pool, rng) -> dict`。`target`/`pool` 为 `Vocab` 模型(或具 `.id/.headword/.reading/.meaning_zh/.pos` 的鸭子对象);`pool` 为同级别候选(含或不含 target 均可);`rng` 为 `random.Random`。

- [ ] **Step 1: Write the failing test**

```python
import random

from app.services.quiz_bank import vocab_meaning_q


class V:
    def __init__(self, id, headword, reading, meaning_zh, pos="名", source_line_id=None):
        self.id = id; self.headword = headword; self.reading = reading
        self.meaning_zh = meaning_zh; self.pos = pos; self.source_line_id = source_line_id


def _pool():
    return [V(i, f"词{i}", f"よみ{i}", f"释义{i}") for i in range(1, 8)]


def test_vocab_meaning_q_basic():
    target = V(1, "高校", "こうこう", "高中")
    rng = random.Random(0)
    q = vocab_meaning_q(target, _pool() + [target], rng)
    assert q["type"] == "meaning"
    assert q["prompt"] == "高校（こうこう）"
    assert q["answer"] == "高中"
    assert q["answer"] in q["options"]
    assert len(q["options"]) == 4
    assert len(set(q["options"])) == 4          # 无重复
    assert q["item"] == {"kind": "vocab", "id": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py::test_vocab_meaning_q_basic -v`
Expected: FAIL（ModuleNotFoundError: app.services.quiz_bank）

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/quiz_bank.py
import random


def _distractors(target, pool, key, n=3):
    """从 pool 取 n 个与 target[key] 不同的值,去重。"""
    seen = {key(target)}
    out = []
    for item in pool:
        v = key(item)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out[:n]


def _assemble(correct, distractors, rng):
    opts = [correct, *distractors]
    rng.shuffle(opts)
    return opts


def vocab_meaning_q(target, pool, rng) -> dict:
    others = [v for v in pool if v.id != target.id]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda v: v.meaning_zh)
    options = _assemble(target.meaning_zh, distractors, rng)
    return {
        "id": f"v{target.id}-meaning",
        "type": "meaning",
        "prompt": f"{target.headword}（{target.reading}）",
        "hint": "选择正确的中文释义",
        "options": options,
        "answer": target.meaning_zh,
        "item": {"kind": "vocab", "id": target.id},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quiz_bank.py backend/tests/test_quiz_bank.py
git commit -m "feat(quiz): vocab meaning question generator"
```

---

### Task 2: 读音选择题

**Files:**
- Modify: `app/services/quiz_bank.py`
- Test: `tests/test_quiz_bank.py`

**Interfaces:**
- Produces: `vocab_reading_q(target, pool, rng) -> dict | None`。无汉字(写法==读音)返回 `None`。

- [ ] **Step 1: Write the failing test**

```python
from app.services.quiz_bank import vocab_reading_q


def test_vocab_reading_q_basic():
    target = V(1, "高校", "こうこう", "高中")
    rng = random.Random(0)
    q = vocab_reading_q(target, _pool() + [target], rng)
    assert q["type"] == "reading"
    assert q["prompt"] == "高校"
    assert q["answer"] == "こうこう"
    assert q["answer"] in q["options"] and len(q["options"]) == 4


def test_vocab_reading_q_none_when_kana_only():
    target = V(1, "ラーメン", "ラーメン", "拉面")
    assert vocab_reading_q(target, _pool(), random.Random(0)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py::test_vocab_reading_q_basic -v`
Expected: FAIL（ImportError: cannot import name 'vocab_reading_q'）

- [ ] **Step 3: Write minimal implementation**

```python
# 追加到 app/services/quiz_bank.py
def vocab_reading_q(target, pool, rng):
    if target.headword == target.reading:   # 纯假名,无读音可考
        return None
    others = [v for v in pool if v.id != target.id and v.reading != target.reading]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda v: v.reading)
    if len(distractors) < 3:
        return None
    options = _assemble(target.reading, distractors, rng)
    return {
        "id": f"v{target.id}-reading",
        "type": "reading",
        "prompt": target.headword,
        "hint": "选择正确的假名读音",
        "options": options,
        "answer": target.reading,
        "item": {"kind": "vocab", "id": target.id},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py -v`
Expected: PASS（2 个新测试）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quiz_bank.py backend/tests/test_quiz_bank.py
git commit -m "feat(quiz): vocab reading question generator"
```

---

### Task 3: 活用填空题(干扰项=同词其它活用形)

**Files:**
- Modify: `app/services/quiz_bank.py`
- Test: `tests/test_quiz_bank.py`

**Interfaces:**
- Produces: `vocab_conjugation_q(target, rng) -> dict | None`。不可活用或可用活用形不足 4 个返回 `None`。依赖 `app.services.conjugation.conjugate`。

- [ ] **Step 1: Write the failing test**

```python
from app.services.quiz_bank import vocab_conjugation_q


def test_vocab_conjugation_q_godan():
    target = V(1, "飲む", "のむ", "喝", pos="他動1")
    q = vocab_conjugation_q(target, random.Random(0))
    assert q["type"] == "conjugation"
    assert q["prompt"] == "飲む"
    assert q["hint"].endswith("形") or "形" in q["hint"]      # 目标活用形标签
    assert q["answer"] in q["options"] and len(q["options"]) == 4
    assert len(set(q["options"])) == 4
    # 答案应为该词某活用形的表层
    from app.services.conjugation import conjugate
    surfaces = {f["surface"] for f in conjugate("飲む", "のむ", "他動1")["forms"]}
    assert q["answer"] in surfaces


def test_vocab_conjugation_q_none_for_noun():
    target = V(1, "天気", "てんき", "天气", pos="名")
    assert vocab_conjugation_q(target, random.Random(0)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py::test_vocab_conjugation_q_godan -v`
Expected: FAIL（ImportError: vocab_conjugation_q）

- [ ] **Step 3: Write minimal implementation**

```python
# 追加到 app/services/quiz_bank.py（文件顶部加 import）
from app.services.conjugation import conjugate


def vocab_conjugation_q(target, rng):
    table = conjugate(target.headword, target.reading, target.pos or "")
    if table is None:
        return None
    forms = [f for f in table["forms"] if f["key"] != "dictionary"]
    # 表层去重,确保有 ≥4 个互不相同的选项
    uniq = []
    seen = set()
    for f in forms:
        if f["surface"] not in seen:
            seen.add(f["surface"])
            uniq.append(f)
    if len(uniq) < 4:
        return None
    rng.shuffle(uniq)
    answer_form = uniq[0]
    distractors = [f["surface"] for f in uniq[1:4]]
    options = _assemble(answer_form["surface"], distractors, rng)
    return {
        "id": f"v{target.id}-conj-{answer_form['key']}",
        "type": "conjugation",
        "prompt": target.headword,
        "hint": f"请选出「{answer_form['label']}」",
        "options": options,
        "answer": answer_form["surface"],
        "item": {"kind": "vocab", "id": target.id},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quiz_bank.py backend/tests/test_quiz_bank.py
git commit -m "feat(quiz): conjugation fill question with same-word distractors"
```

---

### Task 4: 语法选择题 + 词条/语法分发器

**Files:**
- Modify: `app/services/quiz_bank.py`
- Test: `tests/test_quiz_bank.py`

**Interfaces:**
- Produces:
  - `grammar_meaning_q(target, pool, rng) -> dict`（`target`/`pool` 为 `GrammarPoint` 鸭子对象,具 `.id/.name/.explanation`）。
  - `make_vocab_question(target, pool, rng) -> dict`：在可用的 meaning/reading/conjugation 中随机选一个(必至少回退到 meaning)。
  - `make_grammar_question(target, pool, rng) -> dict`：当前等于 `grammar_meaning_q`。

- [ ] **Step 1: Write the failing test**

```python
from app.services.quiz_bank import (
    grammar_meaning_q, make_grammar_question, make_vocab_question,
)


class G:
    def __init__(self, id, name, explanation):
        self.id = id; self.name = name; self.explanation = explanation


def _gpool():
    return [G(i, f"〜语法{i}", f"含义{i}") for i in range(1, 8)]


def test_grammar_meaning_q():
    target = G(1, "〜にあたって", "在…之际")
    q = grammar_meaning_q(target, _gpool() + [target], random.Random(0))
    assert q["type"] == "grammar"
    assert q["prompt"] == "〜にあたって"
    assert q["answer"] == "在…之际" and len(q["options"]) == 4
    assert q["item"] == {"kind": "grammar", "id": 1}


def test_make_vocab_question_always_returns():
    target = V(1, "天気", "てんき", "天气", pos="名")   # 仅 meaning 可用
    q = make_vocab_question(target, _pool() + [target], random.Random(0))
    assert q["type"] in {"meaning", "reading", "conjugation"}
    assert q["item"]["kind"] == "vocab"


def test_make_grammar_question():
    target = G(1, "〜にあたって", "在…之际")
    assert make_grammar_question(target, _gpool() + [target], random.Random(0))["type"] == "grammar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py::test_grammar_meaning_q -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: Write minimal implementation**

```python
# 追加到 app/services/quiz_bank.py
def grammar_meaning_q(target, pool, rng):
    others = [g for g in pool if g.id != target.id and g.explanation != target.explanation]
    rng.shuffle(others)
    distractors = _distractors(target, others, key=lambda g: g.explanation)
    options = _assemble(target.explanation, distractors, rng)
    return {
        "id": f"g{target.id}-grammar",
        "type": "grammar",
        "prompt": target.name,
        "hint": "选择正确的中文含义",
        "options": options,
        "answer": target.explanation,
        "item": {"kind": "grammar", "id": target.id},
    }


def make_vocab_question(target, pool, rng):
    builders = [lambda: vocab_conjugation_q(target, rng),
                lambda: vocab_reading_q(target, pool, rng)]
    rng.shuffle(builders)
    for build in builders:
        q = build()
        if q is not None and rng.random() < 0.7:   # 偏向变化,但保证有回退
            return q
    return vocab_meaning_q(target, pool, rng)


def make_grammar_question(target, pool, rng):
    return grammar_meaning_q(target, pool, rng)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_quiz_bank.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/quiz_bank.py backend/tests/test_quiz_bank.py
git commit -m "feat(quiz): grammar question + vocab/grammar dispatchers"
```

---

## Phase B — 模型与塔服务 `tower.py`

### Task 5: 新增 `TowerProgress` / `PlayerStats` 模型

**Files:**
- Create: `app/models/game.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_models_game.py`

**Interfaces:**
- Produces: `TowerProgress(level, zone_idx, stage_idx, is_boss, cleared, stars, best_accuracy, attempts)`、`PlayerStats(id, total_xp, player_level)`。经 `app.models` 导出。

- [ ] **Step 1: Write the failing test**

```python
from app.models import PlayerStats, TowerProgress


def test_tower_progress_persists(db_session):
    p = TowerProgress(level="N5", zone_idx=0, stage_idx=1, is_boss=False,
                      cleared=True, stars=2, best_accuracy=0.8, attempts=1)
    db_session.add(p)
    db_session.commit()
    got = db_session.query(TowerProgress).one()
    assert got.level == "N5" and got.stars == 2 and got.is_boss is False


def test_player_stats_defaults(db_session):
    s = PlayerStats(id=1)
    db_session.add(s)
    db_session.commit()
    assert db_session.get(PlayerStats, 1).total_xp == 0
    assert db_session.get(PlayerStats, 1).player_level == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_models_game.py -v`
Expected: FAIL（ImportError: TowerProgress）

- [ ] **Step 3: Write minimal implementation**

```python
# app/models/game.py
from datetime import datetime

from sqlalchemy import UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TowerProgress(Base):
    __tablename__ = "tower_progress"
    __table_args__ = (
        UniqueConstraint("level", "zone_idx", "stage_idx", "is_boss",
                         name="uq_tower_cell"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str]
    zone_idx: Mapped[int]
    stage_idx: Mapped[int]
    is_boss: Mapped[bool] = mapped_column(default=False)
    cleared: Mapped[bool] = mapped_column(default=False)
    stars: Mapped[int] = mapped_column(default=0)
    best_accuracy: Mapped[float] = mapped_column(default=0.0)
    attempts: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    total_xp: Mapped[int] = mapped_column(default=0)
    player_level: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

```python
# app/models/__init__.py —— 在现有导出后追加
from app.models.game import PlayerStats, TowerProgress  # noqa: E402,F401
```

> 注:确认 `app/models/__init__.py` 把新名字加入 `__all__`(若存在该列表)。新表由 `init_db` 的 `create_all` 自动建,无需迁移。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_models_game.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/game.py backend/app/models/__init__.py backend/tests/test_models_game.py
git commit -m "feat(game): TowerProgress and PlayerStats models"
```

---

### Task 6: 塔布局(确定性切分)

**Files:**
- Create: `app/services/tower.py`
- Test: `tests/test_tower.py`

**Interfaces:**
- Produces:
  - 常量 `LEVELS`、`STAGE_VOCAB=8`、`STAGE_GRAMMAR=2`、`STAGES_PER_ZONE=5`。
  - `level_items(db, level) -> tuple[list[Vocab], list[GrammarPoint]]`（按 id 升序）。
  - `num_stages(vocab_count) -> int`、`num_zones(stage_count) -> int`。
  - `stage_items(db, level, zone_idx, stage_idx) -> tuple[list[Vocab], list[GrammarPoint]]`。
  - `zone_items(db, level, zone_idx) -> tuple[list[Vocab], list[GrammarPoint]]`。

- [ ] **Step 1: Write the failing test**

```python
from app.models import GrammarPoint, Vocab
from app.services import tower


def _seed_level(db, n_vocab=20, n_gram=6, level="N5"):
    for i in range(n_vocab):
        db.add(Vocab(headword=f"語{i}", reading=f"よ{i}", meaning_zh=f"义{i}",
                     pos="名", jlpt_level=level))
    for i in range(n_gram):
        db.add(GrammarPoint(key=f"{level}-g{i}", name=f"〜文法{i}",
                            jlpt_level=level, explanation=f"含义{i}", curated=True))
    db.commit()


def test_stage_slice_sizes(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    v, g = tower.stage_items(db_session, "N5", 0, 0)
    assert [x.headword for x in v] == [f"語{i}" for i in range(8)]
    assert [x.name for x in g] == ["〜文法0", "〜文法1"]
    v2, _ = tower.stage_items(db_session, "N5", 0, 1)
    assert [x.headword for x in v2] == [f"語{i}" for i in range(8, 16)]


def test_zone_items_unions_five_stages(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    v, g = tower.zone_items(db_session, "N5", 0)
    assert len(v) == 40 and len(g) == 10        # 5 关 × (8 词 + 2 语法)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py -v`
Expected: FAIL（ModuleNotFoundError: app.services.tower）

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/tower.py
from math import ceil

from sqlalchemy import select

from app.models import GrammarPoint, Vocab

LEVELS = ["N5", "N4", "N3", "N2", "N1"]
STAGE_VOCAB = 8
STAGE_GRAMMAR = 2
STAGES_PER_ZONE = 5


def level_items(db, level):
    vocab = db.scalars(
        select(Vocab).where(Vocab.jlpt_level == level).order_by(Vocab.id)
    ).all()
    grammar = db.scalars(
        select(GrammarPoint).where(GrammarPoint.jlpt_level == level).order_by(GrammarPoint.id)
    ).all()
    return list(vocab), list(grammar)


def num_stages(vocab_count: int) -> int:
    return max(1, ceil(vocab_count / STAGE_VOCAB))


def num_zones(stage_count: int) -> int:
    return max(1, ceil(stage_count / STAGES_PER_ZONE))


def _global_stage(zone_idx: int, stage_idx: int) -> int:
    return zone_idx * STAGES_PER_ZONE + stage_idx


def stage_items(db, level, zone_idx, stage_idx):
    vocab, grammar = level_items(db, level)
    g = _global_stage(zone_idx, stage_idx)
    v_slice = vocab[g * STAGE_VOCAB:(g + 1) * STAGE_VOCAB]
    g_slice = grammar[g * STAGE_GRAMMAR:(g + 1) * STAGE_GRAMMAR]
    return v_slice, g_slice


def zone_items(db, level, zone_idx):
    vs, gs = [], []
    for s in range(STAGES_PER_ZONE):
        v, g = stage_items(db, level, zone_idx, s)
        vs.extend(v)
        gs.extend(g)
    return vs, gs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tower.py backend/tests/test_tower.py
git commit -m "feat(tower): deterministic level/zone/stage layout"
```

---

### Task 7: 出题与评星

**Files:**
- Modify: `app/services/tower.py`
- Test: `tests/test_tower.py`

**Interfaces:**
- Produces:
  - `build_quiz(db, level, zone_idx, stage_idx, is_boss, rng) -> list[dict]`：小关用本关词/语法各出 1 题(词题用 `make_vocab_question`、语法用 `make_grammar_question`),Boss 用整区内容混合 ~20 题。pool 用同级别全部词/语法。
  - `stars_for(accuracy: float) -> int`：≥1.0→3,≥0.8→2,≥0.6→1,否则 0。

- [ ] **Step 1: Write the failing test**

```python
import random

from app.services import tower


def test_stars_for_thresholds():
    assert tower.stars_for(1.0) == 3
    assert tower.stars_for(0.8) == 2
    assert tower.stars_for(0.6) == 1
    assert tower.stars_for(0.59) == 0


def test_build_quiz_stage_has_questions(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    qs = tower.build_quiz(db_session, "N5", 0, 0, False, random.Random(1))
    assert len(qs) == 10                       # 8 词 + 2 语法
    assert all(q["answer"] in q["options"] for q in qs)
    assert {q["item"]["kind"] for q in qs} == {"vocab", "grammar"}


def test_build_quiz_boss_is_bigger(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    qs = tower.build_quiz(db_session, "N5", 0, 0, True, random.Random(1))
    assert len(qs) >= 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py::test_build_quiz_stage_has_questions -v`
Expected: FAIL（AttributeError: build_quiz）

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/tower.py 顶部追加 import
from app.services.quiz_bank import make_grammar_question, make_vocab_question

BOSS_MAX_Q = 20


def stars_for(accuracy: float) -> int:
    if accuracy >= 1.0:
        return 3
    if accuracy >= 0.8:
        return 2
    if accuracy >= 0.6:
        return 1
    return 0


def build_quiz(db, level, zone_idx, stage_idx, is_boss, rng):
    vocab_pool, grammar_pool = level_items(db, level)
    if is_boss:
        vs, gs = zone_items(db, level, zone_idx)
    else:
        vs, gs = stage_items(db, level, zone_idx, stage_idx)
    questions = []
    for v in vs:
        questions.append(make_vocab_question(v, vocab_pool, rng))
    for g in gs:
        questions.append(make_grammar_question(g, grammar_pool, rng))
    rng.shuffle(questions)
    if is_boss:
        questions = questions[:BOSS_MAX_Q]
    return questions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tower.py backend/tests/test_tower.py
git commit -m "feat(tower): build_quiz + star grading"
```

---

### Task 8: 交卷结算(进度 + XP + SRS 打通)

**Files:**
- Modify: `app/services/tower.py`
- Test: `tests/test_tower.py`

**Interfaces:**
- Consumes: `app.services.srs`(可不用,直接改字段),`Vocab`/`GrammarPoint` 的 SRS 字段,`TowerProgress`/`PlayerStats`。
- Produces:
  - `submit_result(db, level, zone_idx, stage_idx, is_boss, results, today=None) -> dict`。
    `results: list[dict]`,每项 `{"item": {"kind","id"}, "correct": bool}`。
    返回 `{"stars": int, "accuracy": float, "passed": bool, "xp_gained": int, "total_xp": int}`。
    副作用:写 `TowerProgress`(取更好成绩)、累加 `PlayerStats.total_xp`、把所有作答项 `in_srs=True`,答错项 `due_date=今天`(语法另置 `status="learning"`)。

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from app.models import GrammarPoint, PlayerStats, TowerProgress, Vocab
from app.services import tower


def test_submit_updates_progress_xp_and_srs(db_session):
    v = Vocab(headword="飲む", reading="のむ", meaning_zh="喝", pos="他動1",
              jlpt_level="N5", source_line_id=None)
    g = GrammarPoint(key="N5-g0", name="〜て", jlpt_level="N5",
                     explanation="表示", curated=True)
    db_session.add_all([v, g]); db_session.commit()

    results = [
        {"item": {"kind": "vocab", "id": v.id}, "correct": True},
        {"item": {"kind": "grammar", "id": g.id}, "correct": False},
    ]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results, today=date(2026, 6, 25))

    assert out["accuracy"] == 0.5
    assert out["stars"] == 0 and out["passed"] is False
    assert out["xp_gained"] == 10            # 1 对 × 10
    # 进度落库
    tp = db_session.query(TowerProgress).filter_by(level="N5", zone_idx=0,
                                                   stage_idx=0, is_boss=False).one()
    assert tp.attempts == 1 and tp.best_accuracy == 0.5
    # SRS:都入池;答错的语法 due=今天且 learning
    assert db_session.get(Vocab, v.id).in_srs is True
    gg = db_session.get(GrammarPoint, g.id)
    assert gg.in_srs is True and gg.status == "learning"
    assert gg.due_date == date(2026, 6, 25)


def test_submit_keeps_best_and_anime_bonus(db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", pos="名",
              jlpt_level="N5", source_line_id=999)        # 番剧词
    db_session.add(v); db_session.commit()
    results = [{"item": {"kind": "vocab", "id": v.id}, "correct": True}]
    out = tower.submit_result(db_session, "N5", 0, 0, False, results, today=date(2026, 6, 25))
    assert out["xp_gained"] == 15            # 10 × 1.5 番剧加成
    assert out["stars"] == 3 and out["passed"] is True
    # 再交一次更差成绩,best 不应下降
    tower.submit_result(db_session, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": v.id}, "correct": False}],
                        today=date(2026, 6, 25))
    tp = db_session.query(TowerProgress).filter_by(level="N5", zone_idx=0,
                                                   stage_idx=0, is_boss=False).one()
    assert tp.stars == 3 and tp.best_accuracy == 1.0 and tp.attempts == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py::test_submit_updates_progress_xp_and_srs -v`
Expected: FAIL（AttributeError: submit_result）

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/tower.py 顶部追加 import
from datetime import date as _date

from app.models import GrammarPoint, PlayerStats, TowerProgress, Vocab

BOSS_PASS = 0.8
STAGE_PASS = 0.6
XP_PER_CORRECT = 10


def _get_or_create_progress(db, level, zone_idx, stage_idx, is_boss):
    tp = db.query(TowerProgress).filter_by(
        level=level, zone_idx=zone_idx, stage_idx=stage_idx, is_boss=is_boss).one_or_none()
    if tp is None:
        tp = TowerProgress(level=level, zone_idx=zone_idx, stage_idx=stage_idx,
                           is_boss=is_boss)
        db.add(tp)
    return tp


def _player(db):
    p = db.get(PlayerStats, 1)
    if p is None:
        p = PlayerStats(id=1)
        db.add(p)
    return p


def submit_result(db, level, zone_idx, stage_idx, is_boss, results, today=None):
    today = today or _date.today()
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total else 0.0
    stars = stars_for(accuracy)
    passed = accuracy >= (BOSS_PASS if is_boss else STAGE_PASS)

    xp_gained = 0
    for r in results:
        kind, iid = r["item"]["kind"], r["item"]["id"]
        model = Vocab if kind == "vocab" else GrammarPoint
        obj = db.get(model, iid)
        if obj is None:
            continue
        obj.in_srs = True
        if kind == "grammar":
            obj.status = "learning"
        if not r["correct"]:
            obj.due_date = today
        elif obj.due_date is None:
            obj.due_date = today
        if r["correct"]:
            anime = kind == "vocab" and getattr(obj, "source_line_id", None) is not None
            xp_gained += round(XP_PER_CORRECT * (1.5 if anime else 1))

    tp = _get_or_create_progress(db, level, zone_idx, stage_idx, is_boss)
    tp.attempts += 1
    if accuracy >= tp.best_accuracy:
        tp.best_accuracy = accuracy
        tp.stars = stars
    if passed:
        tp.cleared = True

    player = _player(db)
    player.total_xp += xp_gained
    player.player_level = 1 + player.total_xp // 500     # 每 500 XP 升 1 级

    db.commit()
    return {"stars": stars, "accuracy": accuracy, "passed": passed,
            "xp_gained": xp_gained, "total_xp": player.total_xp}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tower.py backend/tests/test_tower.py
git commit -m "feat(tower): submit_result with progress, XP and SRS wiring"
```

---

### Task 9: 塔地图(进度 + 锁状态)

**Files:**
- Modify: `app/services/tower.py`
- Test: `tests/test_tower.py`

**Interfaces:**
- Produces: `tower_map(db) -> dict`。结构:
  ```python
  {"levels": [
     {"level": "N5", "unlocked": True, "zones": [
        {"zone_idx": 0, "stages": [
           {"stage_idx": 0, "is_boss": False, "unlocked": True,
            "cleared": False, "stars": 0}, ...,
           {"stage_idx": 0, "is_boss": True, "unlocked": False,
            "cleared": False, "stars": 0}]}]}]}
  ```
  解锁规则:N5 与各层第 0 区第 0 关默认解锁;关在区内顺序解锁(前一关 cleared→解锁下一关);5 小关全 cleared→解锁 Boss;Boss cleared→解锁下一区第 0 关;某层最后一区 Boss cleared→解锁下一层。

- [ ] **Step 1: Write the failing test**

```python
from app.services import tower


def test_tower_map_initial_locks(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")   # 1 区 5 关 + Boss
    m = tower.tower_map(db_session)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["unlocked"] is True
    stage0 = n5["zones"][0]["stages"][0]
    assert stage0["unlocked"] is True and stage0["stage_idx"] == 0
    stage1 = n5["zones"][0]["stages"][1]
    assert stage1["unlocked"] is False           # 未过第 0 关
    n4 = next(lv for lv in m["levels"] if lv["level"] == "N4")
    assert n4["unlocked"] is False


def test_tower_map_unlocks_next_after_clear(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")
    tower.submit_result(db_session, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab",
                          "id": db_session.query(Vocab).first().id}, "correct": True}])
    m = tower.tower_map(db_session)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["zones"][0]["stages"][1]["unlocked"] is True     # 第 1 关解锁
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py::test_tower_map_initial_locks -v`
Expected: FAIL（AttributeError: tower_map）

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/tower.py 追加
def _progress_index(db):
    idx = {}
    for tp in db.query(TowerProgress).all():
        idx[(tp.level, tp.zone_idx, tp.stage_idx, tp.is_boss)] = tp
    return idx


def tower_map(db):
    idx = _progress_index(db)

    def cell(level, zone, stage, is_boss, unlocked):
        tp = idx.get((level, zone, stage, is_boss))
        return {"stage_idx": stage, "is_boss": is_boss, "unlocked": unlocked,
                "cleared": bool(tp and tp.cleared), "stars": (tp.stars if tp else 0)}

    def cleared(level, zone, stage, is_boss):
        tp = idx.get((level, zone, stage, is_boss))
        return bool(tp and tp.cleared)

    levels_out = []
    prev_level_done = True
    for level in LEVELS:
        vocab, _ = level_items(db, level)
        stage_count = num_stages(len(vocab))
        zone_count = num_zones(stage_count)
        level_unlocked = prev_level_done
        zones_out = []
        prev_zone_boss_done = True
        for z in range(zone_count):
            zone_unlocked = level_unlocked and prev_zone_boss_done
            stages_out = []
            prev_stage_done = True
            for s in range(STAGES_PER_ZONE):
                unlocked = zone_unlocked and prev_stage_done
                stages_out.append(cell(level, z, s, False, unlocked))
                prev_stage_done = cleared(level, z, s, False)
            all_stages_done = all(cleared(level, z, s, False)
                                  for s in range(STAGES_PER_ZONE))
            boss_unlocked = zone_unlocked and all_stages_done
            stages_out.append(cell(level, z, 0, True, boss_unlocked))
            zones_out.append({"zone_idx": z, "stages": stages_out})
            prev_zone_boss_done = cleared(level, z, 0, True)
        levels_out.append({"level": level, "unlocked": level_unlocked,
                           "zones": zones_out})
        # 整层完成 = 最后一区 Boss 通过
        prev_level_done = prev_zone_boss_done
    return {"levels": levels_out}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_tower.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tower.py backend/tests/test_tower.py
git commit -m "feat(tower): tower_map with unlock logic"
```

---

## Phase C — API `api/tower.py`

### Task 10: 塔地图 / 取题 / 玩家接口

**Files:**
- Create: `app/api/tower.py`
- Modify: `app/main.py`（注册 router）
- Test: `tests/test_api_tower.py`

**Interfaces:**
- Produces:
  - `GET /api/tower` → `tower.tower_map(db)`。
  - `GET /api/tower/quiz?level=&zone=&stage=&boss=` → `{"questions": [...]}`(题目去掉 `answer` 字段,避免泄题;`answer` 仅服务端校验时不需要——前端凭 `correct` 自评,见下)。
  - `GET /api/player` → `{"total_xp", "player_level"}`。
- 说明:为简化,前端拿到题目含 `answer`(本地自评对错),交卷只回传每题 `correct`。这是单机学习应用,可接受;`answer` 随题下发。

- [ ] **Step 1: Write the failing test**

```python
from app.models import GrammarPoint, Vocab


def _seed(db):
    for i in range(12):
        db.add(Vocab(headword=f"語{i}", reading=f"よ{i}", meaning_zh=f"义{i}",
                     pos="名", jlpt_level="N5"))
    for i in range(4):
        db.add(GrammarPoint(key=f"N5-g{i}", name=f"〜文法{i}", jlpt_level="N5",
                            explanation=f"含义{i}", curated=True))
    db.commit()


def test_get_tower_map(client, db_session):
    _seed(db_session)
    body = client.get("/api/tower").json()
    assert body["levels"][0]["level"] == "N5"
    assert body["levels"][0]["unlocked"] is True


def test_get_quiz(client, db_session):
    _seed(db_session)
    body = client.get("/api/tower/quiz?level=N5&zone=0&stage=0").json()
    assert len(body["questions"]) >= 1
    q = body["questions"][0]
    assert q["answer"] in q["options"]
    assert q["item"]["kind"] in {"vocab", "grammar"}


def test_get_player(client, db_session):
    body = client.get("/api/player").json()
    assert body["total_xp"] == 0 and body["player_level"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api_tower.py -v`
Expected: FAIL（404 / ModuleNotFoundError）

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/tower.py
import random

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PlayerStats
from app.services import tower

router = APIRouter(tags=["tower"])


@router.get("/api/tower")
def get_tower(db: Session = Depends(get_db)) -> dict:
    return tower.tower_map(db)


@router.get("/api/tower/quiz")
def get_quiz(level: str = Query(...), zone: int = Query(0), stage: int = Query(0),
             boss: bool = Query(False), db: Session = Depends(get_db)) -> dict:
    questions = tower.build_quiz(db, level, zone, stage, boss, random.Random())
    return {"questions": questions}


@router.get("/api/player")
def get_player(db: Session = Depends(get_db)) -> dict:
    p = db.get(PlayerStats, 1)
    return {"total_xp": p.total_xp if p else 0,
            "player_level": p.player_level if p else 1}
```

```python
# app/main.py —— 在 from app.api import (...) 里加入 tower,并 include
# 1) 导入行追加 tower
# 2) for module in (...) 元组追加 tower
```

> 具体:把 `from app.api import (... tts, vocab,)` 改为 `... tts, vocab, tower,`(保持字母序则放 `tower` 于 `tts` 前:`today, tower, tts, vocab`);循环元组同样加入 `tower`。改后运行 `ruff check app/main.py` 确认 import 排序。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api_tower.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/tower.py backend/app/main.py backend/tests/test_api_tower.py
git commit -m "feat(api): tower map, quiz and player endpoints"
```

---

### Task 11: 交卷接口

**Files:**
- Modify: `app/api/tower.py`
- Test: `tests/test_api_tower.py`

**Interfaces:**
- Produces: `POST /api/tower/submit`,body:
  ```python
  {"level": str, "zone": int, "stage": int, "boss": bool,
   "results": [{"item": {"kind": str, "id": int}, "correct": bool}]}
  ```
  返回 `tower.submit_result(...)` 的结果。

- [ ] **Step 1: Write the failing test**

```python
def test_submit_quiz_updates_and_returns(client, db_session):
    _seed(db_session)
    vid = db_session.query(Vocab).first().id
    body = {
        "level": "N5", "zone": 0, "stage": 0, "boss": False,
        "results": [{"item": {"kind": "vocab", "id": vid}, "correct": True}],
    }
    out = client.post("/api/tower/submit", json=body).json()
    assert out["stars"] == 3 and out["passed"] is True
    assert out["xp_gained"] == 10
    # 地图应解锁下一关
    m = client.get("/api/tower").json()
    assert m["levels"][0]["zones"][0]["stages"][1]["unlocked"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/test_api_tower.py::test_submit_quiz_updates_and_returns -v`
Expected: FAIL（405/404）

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/tower.py 追加
from pydantic import BaseModel


class QItem(BaseModel):
    kind: str
    id: int


class QResult(BaseModel):
    item: QItem
    correct: bool


class SubmitBody(BaseModel):
    level: str
    zone: int = 0
    stage: int = 0
    boss: bool = False
    results: list[QResult]


@router.post("/api/tower/submit")
def submit(body: SubmitBody, db: Session = Depends(get_db)) -> dict:
    results = [{"item": {"kind": r.item.kind, "id": r.item.id}, "correct": r.correct}
               for r in body.results]
    return tower.submit_result(db, body.level, body.zone, body.stage, body.boss, results)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest tests/test_api_tower.py -v && .venv/bin/pytest -q`
Expected: PASS（全量后端绿)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/tower.py backend/tests/test_api_tower.py
git commit -m "feat(api): tower submit endpoint"
```

---

## Phase D — 前端

### Task 12: 类型与 API 封装

**Files:**
- Modify: `src/types.ts`
- Modify: `src/lib/api.ts`

**Interfaces:**
- Produces: `QuizQuestion`、`TowerMap`、`SubmitResult` 类型;`getTower()`、`getTowerQuiz()`、`submitQuiz()`、`getPlayer()`。

- [ ] **Step 1: Write the failing test**

```typescript
// tests/tower-api.test.ts
import { describe, expect, it } from "vitest";

import { getTower } from "../src/lib/api";

describe("tower api", () => {
  it("getTower returns levels", async () => {
    const m = await getTower();
    expect(m.levels[0].level).toBe("N5");
  });
});
```

> 需要在 `tests/handlers.ts` 增 `http.get("/api/tower", ...)` mock(下一步 Step 3 给出)。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tower-api`
Expected: FAIL（getTower 未定义 / 无 mock）

- [ ] **Step 3: Write minimal implementation**

```typescript
// src/types.ts 追加
export type QuizQuestion = {
  id: string; type: "meaning" | "reading" | "conjugation" | "grammar";
  prompt: string; hint: string | null; options: string[]; answer: string;
  item: { kind: "vocab" | "grammar"; id: number };
};

export type TowerStage = {
  stage_idx: number; is_boss: boolean; unlocked: boolean;
  cleared: boolean; stars: number;
};
export type TowerZone = { zone_idx: number; stages: TowerStage[] };
export type TowerLevel = { level: string; unlocked: boolean; zones: TowerZone[] };
export type TowerMap = { levels: TowerLevel[] };

export type SubmitResult = {
  stars: number; accuracy: number; passed: boolean;
  xp_gained: number; total_xp: number;
};
```

```typescript
// src/lib/api.ts 追加(并在顶部 import 类型)
// import type { QuizQuestion, SubmitResult, TowerMap } from "../types";
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
```

```typescript
// tests/handlers.ts 追加
http.get("/api/tower", () => HttpResponse.json({
  levels: [{ level: "N5", unlocked: true, zones: [{ zone_idx: 0, stages: [
    { stage_idx: 0, is_boss: false, unlocked: true, cleared: false, stars: 0 },
    { stage_idx: 0, is_boss: true, unlocked: false, cleared: false, stars: 0 },
  ] }] }] },
)),
http.get("/api/tower/quiz", () => HttpResponse.json({ questions: [
  { id: "v1-meaning", type: "meaning", prompt: "高校（こうこう）", hint: "选释义",
    options: ["高中", "小学", "大学", "公司"], answer: "高中",
    item: { kind: "vocab", id: 1 } },
] })),
http.post("/api/tower/submit", () => HttpResponse.json({
  stars: 3, accuracy: 1, passed: true, xp_gained: 10, total_xp: 10 })),
http.get("/api/player", () => HttpResponse.json({ total_xp: 0, player_level: 1 })),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- tower-api && npm run lint`
Expected: PASS + tsc 无错

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types.ts frontend/src/lib/api.ts frontend/tests/handlers.ts frontend/tests/tower-api.test.ts
git commit -m "feat(web): tower types and api client"
```

---

### Task 13: 答题页 `Quiz.tsx`

**Files:**
- Create: `src/pages/Quiz.tsx`
- Test: `tests/quiz.test.tsx`

**Interfaces:**
- Consumes: `getTowerQuiz`、`submitQuiz`、`QuizQuestion`、`SubmitResult`。
- Produces: 路由组件 `<Quiz />`,读 URL query `?level=&zone=&stage=&boss=`;逐题作答(点选项即判对错并进入下一题),末尾调 `submitQuiz` 显示结算(星级 + XP)。

- [ ] **Step 1: Write the failing test**

```tsx
// tests/quiz.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Quiz from "../src/pages/Quiz";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/quiz?level=N5&zone=0&stage=0"]}>
        <Quiz />
      </MemoryRouter>
    </QueryClientProvider>);
}

describe("Quiz page", () => {
  it("shows a question then result after answering", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText("高校（こうこう）")).toBeInTheDocument());
    fireEvent.click(screen.getByText("高中"));
    await waitFor(() => expect(screen.getByText(/本关结算|结算|XP/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- quiz`
Expected: FAIL（无法解析 Quiz）

- [ ] **Step 3: Write minimal implementation**

```tsx
// src/pages/Quiz.tsx
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Loading from "../components/Loading";
import { getTowerQuiz, submitQuiz } from "../lib/api";
import type { QuizQuestion, SubmitResult } from "../types";

export default function Quiz() {
  const [sp] = useSearchParams();
  const level = sp.get("level") ?? "N5";
  const zone = Number(sp.get("zone") ?? 0);
  const stage = Number(sp.get("stage") ?? 0);
  const boss = sp.get("boss") === "1";

  const { data, isLoading } = useQuery({
    queryKey: ["tower-quiz", level, zone, stage, boss],
    queryFn: () => getTowerQuiz({ level, zone, stage, boss }),
    refetchOnWindowFocus: false,
  });

  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [results, setResults] = useState<{ item: QuizQuestion["item"]; correct: boolean }[]>([]);
  const [result, setResult] = useState<SubmitResult | null>(null);

  const questions = useMemo(() => data?.questions ?? [], [data]);
  const q = questions[idx];

  async function choose(opt: string) {
    if (picked || !q) return;
    setPicked(opt);
    const correct = opt === q.answer;
    const next = [...results, { item: q.item, correct }];
    setResults(next);
    setTimeout(async () => {
      setPicked(null);
      if (idx + 1 < questions.length) {
        setIdx(idx + 1);
      } else {
        setResult(await submitQuiz({ level, zone, stage, boss, results: next }));
      }
    }, 600);
  }

  if (isLoading || !data) return <Loading />;
  if (result) {
    return (
      <div className="max-w-md mx-auto text-center space-y-4 py-10">
        <h1 className="text-2xl font-bold text-ink-900">本关结算</h1>
        <div className="text-4xl">{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</div>
        <p className="text-ink-600">正确率 {Math.round(result.accuracy * 100)}%</p>
        <p className="text-brand-700 font-semibold">+{result.xp_gained} XP</p>
        <p className={result.passed ? "text-emerald-600" : "text-amber-600"}>
          {result.passed ? "通关!" : "未达标,再来一次"}
        </p>
      </div>
    );
  }
  if (!q) return <p className="text-ink-400">本关暂无题目</p>;

  return (
    <div className="max-w-md mx-auto space-y-6 py-6">
      <div className="text-xs text-ink-400">第 {idx + 1} / {questions.length} 题</div>
      <div className="text-center">
        <div className="text-3xl font-bold text-ink-900 ja">{q.prompt}</div>
        {q.hint && <div className="text-sm text-ink-500 mt-2">{q.hint}</div>}
      </div>
      <div className="grid gap-3">
        {q.options.map((opt) => {
          const state = !picked ? "" : opt === q.answer ? "correct"
            : opt === picked ? "wrong" : "";
          const cls = state === "correct" ? "border-emerald-400 bg-emerald-50"
            : state === "wrong" ? "border-rose-400 bg-rose-50" : "border-ink-200 hover:border-brand-400";
          return (
            <button key={opt} onClick={() => choose(opt)} disabled={!!picked}
                    className={`ja border rounded-xl px-4 py-3 text-lg text-left transition-colors ${cls}`}>
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- quiz && npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Quiz.tsx frontend/tests/quiz.test.tsx
git commit -m "feat(web): quiz play page"
```

---

### Task 14: 塔地图页 `Tower.tsx` + 路由 + 导航

**Files:**
- Create: `src/pages/Tower.tsx`
- Modify: `src/App.tsx`（加 `/tower`、`/quiz` 路由）
- Modify: `src/components/Layout.tsx`（主导航加「🗼 修炼塔」)
- Test: `tests/tower.test.tsx`

**Interfaces:**
- Consumes: `getTower`、`getPlayer`、`TowerMap`。
- Produces: `<Tower />`,展示层/区/关节点,点未锁关跳 `/quiz?...`(用 `useNavigate`);锁定关不可点。

- [ ] **Step 1: Write the failing test**

```tsx
// tests/tower.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import Tower from "../src/pages/Tower";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><Tower /></MemoryRouter>
    </QueryClientProvider>);
}

describe("Tower page", () => {
  it("renders N5 level and a stage node", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText("N5")).toBeInTheDocument());
    expect(screen.getByText(/第 1 关|1关|关 1/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tower.test`
Expected: FAIL（无法解析 Tower）

- [ ] **Step 3: Write minimal implementation**

```tsx
// src/pages/Tower.tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Loading from "../components/Loading";
import { getPlayer, getTower } from "../lib/api";
import type { TowerStage } from "../types";

export default function Tower() {
  const nav = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["tower"], queryFn: getTower });
  const { data: player } = useQuery({ queryKey: ["player"], queryFn: getPlayer });
  const [active, setActive] = useState(0);

  if (isLoading || !data) return <Loading />;
  const level = data.levels[active];

  function open(stage: TowerStage, zoneIdx: number) {
    if (!stage.unlocked) return;
    const boss = stage.is_boss ? "&boss=1" : "";
    nav(`/quiz?level=${level.level}&zone=${zoneIdx}&stage=${stage.stage_idx}${boss}`);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-ink-900">修炼塔</h1>
        {player && <span className="text-sm text-brand-700">Lv.{player.player_level} · {player.total_xp} XP</span>}
      </div>

      <div className="flex gap-2">
        {data.levels.map((lv, i) => (
          <button key={lv.level} onClick={() => lv.unlocked && setActive(i)}
                  disabled={!lv.unlocked}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                    i === active ? "bg-brand-600 text-white"
                    : lv.unlocked ? "bg-ink-100 text-ink-700" : "bg-ink-50 text-ink-300"}`}>
            {lv.unlocked ? lv.level : `🔒${lv.level}`}
          </button>
        ))}
      </div>

      <div className="space-y-6">
        {level.zones.map((zone) => (
          <section key={zone.zone_idx} className="space-y-2">
            <h2 className="text-sm font-semibold text-ink-500">第 {zone.zone_idx + 1} 区</h2>
            <div className="flex flex-wrap gap-3">
              {zone.stages.map((st) => (
                <button key={`${st.stage_idx}-${st.is_boss}`} onClick={() => open(st, zone.zone_idx)}
                        disabled={!st.unlocked}
                        className={`w-20 h-20 rounded-xl flex flex-col items-center justify-center text-sm border-2 ${
                          !st.unlocked ? "border-ink-100 bg-ink-50 text-ink-300"
                          : st.is_boss ? "border-rose-300 bg-rose-50 text-rose-700"
                          : st.cleared ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                          : "border-brand-300 bg-white text-brand-700"}`}>
                  <span>{st.is_boss ? "👹 Boss" : `第 ${st.stage_idx + 1} 关`}</span>
                  <span className="text-xs">
                    {st.unlocked ? "★".repeat(st.stars) + "☆".repeat((st.is_boss ? 3 : 3) - st.stars) : "🔒"}
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
```

```tsx
// src/App.tsx —— 加 import 与路由
// import Tower from "./pages/Tower";
// import Quiz from "./pages/Quiz";
// 在 <Route element={<Layout />}> 内加:
//   <Route path="tower" element={<Tower />} />
//   <Route path="quiz" element={<Quiz />} />
```

```tsx
// src/components/Layout.tsx —— MAIN_NAV 追加
//   { to: "/tower", label: "修炼塔", icon: "🗼" },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- tower.test && npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Tower.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/tests/tower.test.tsx
git commit -m "feat(web): tower map page, route and nav entry"
```

---

### Task 15: 全量回归 + 构建

**Files:** 无新增,仅验证。

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && .venv/bin/ruff check app && .venv/bin/pytest -q`
Expected: 全绿,无 ruff 错误。

- [ ] **Step 2: 前端测试 + 构建**

Run: `cd frontend && npm test && npm run build`
Expected: 全部 PASS,`vite build` 成功。

- [ ] **Step 3: 实跑冒烟**

Run（后端 reload 已起或重启):
```bash
curl -s "http://localhost:8000/api/tower" | head -c 200
curl -s "http://localhost:8000/api/tower/quiz?level=N5&zone=0&stage=0" | head -c 200
```
Expected: 返回 JSON(levels / questions)。

- [ ] **Step 4: Commit(若有微调)**

```bash
git add -A && git commit -m "test: tower game full regression green"
```

---

## Self-Review(对照 spec)

**1. Spec 覆盖检查**
- 塔结构/区/关/Boss(spec §2)→ Task 6/7/9 ✓
- 4 题型(spec §3)→ Task 1–4 ✓
- 追番加成 XP 1.5×(spec §4/§6)→ Task 8(`source_line_id` 判定)✓;「📺 优先排早期关」**v1 简化为加成,排序仍按 id**(spec §2 已注明词频排序属后续)——一致。
- SRS 打通(spec §5)→ Task 8 ✓
- XP/连击/星级(spec §6)→ Task 7/8(星级/XP);**连击 combo 为前端视觉**,Task 13 未实现倍率动画——**缺口**:留作 Quiz 增强,不影响 XP 正确性(服务端权威)。已在此标注。
- 数据模型 TowerProgress/PlayerStats(spec §7)→ Task 5 ✓
- 架构分层(spec §8)→ Task 1–14 ✓
- 每日番剧挑战(spec §4/§10 v1)→ **缺口**:本计划未含 `/api/tower/daily-anime` 与今天卡片。**决定移至紧邻的后续小计划**(避免本计划过长),v1 先交付塔主体。如需并入,补一个与 Task 10 同构的接口 + 今天页卡片任务。

**2. 占位扫描**:无 TBD/TODO;每步含完整代码。

**3. 类型一致性**:题目字典字段(`id/type/prompt/hint/options/answer/item`)在 Task 1–4、Task 12 类型、Task 13 使用处一致;`submit_result` 返回键(`stars/accuracy/passed/xp_gained/total_xp`)在 Task 8、Task 11、Task 12 `SubmitResult`、Task 13 渲染处一致。

> 两处 spec 缺口(连击动画、每日番剧挑战)已显式标注为紧邻后续工作,不阻塞 v1 塔主体交付。
