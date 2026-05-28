# 剧情节点重构（段 1）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让首页从工具仪表盘变成剧情节点路径，把"集"细化为"场景节点"，AniList 自动注入角色头像，导航从 5 tab 降为 2 tab。完成后段 1 的产品改观已成立。

**Architecture:** 新增 `Scene` 表索引现有 `Line`；加工流水线前置一步 LLM 切场景；`Series` 添加 AniList 字段，创建时后台拉取角色资产；新增 `/api/today/journey` 与 `/api/episodes/{id}/scenes` 端点；前端重写 `Today.tsx` 与 `Layout.tsx`，小改 `Series.tsx` / `Reading.tsx`。共 5 个 commit，前后端解耦。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / SQLite / httpx / Anthropic SDK · React 18 / Vite / TypeScript / Tailwind / TanStack Query · pytest

**Spec:** `docs/superpowers/specs/2026-05-27-story-node-redesign-phase-1-design.md`

**Branch:** `feat/story-node-redesign-phase-1`（已存在）

---

## 文件清单

### 新增

- `backend/app/services/anilist.py` — AniList GraphQL 客户端
- `backend/app/api/today.py` — 新路由，前缀 `/api/today`，含 `GET /journey`
- `backend/tests/test_models_scene.py` — Scene 模型测试
- `backend/tests/test_db_migrations.py` — `_migrate_in_place` 幂等测试
- `backend/tests/test_anilist.py` — AniList 服务测试
- `backend/tests/test_pipeline_scenes.py` — 切场景测试
- `backend/tests/test_api_today_journey.py` — `/api/today/journey` 端点测试
- `frontend/src/components/CharacterHeader.tsx` — 首页角色头像与剧集摘要
- `frontend/src/components/SceneTimeline.tsx` — 章节书风场景列表

### 修改

- `backend/app/models/content.py` — Series/Episode 加字段，新增 Scene 类
- `backend/app/models/__init__.py` — 导出 Scene
- `backend/app/db.py` — 加 `_migrate_in_place` 与 `_add_column_if_missing`，串到 `init_app_db`
- `backend/app/services/pipeline.py` — `process_episode` 前置切场景步骤；新增 `_split_scenes` / `_validate_scenes` / `_write_scenes`
- `backend/app/api/series.py` — 响应加 AniList 字段；`POST /` 触发后台任务；新增 `GET /{id}` 与 `POST /{id}/refresh-anilist`
- `backend/app/api/episodes.py` — 新增 `GET /{id}/scenes`
- `backend/app/main.py` — 注册新 `today` 路由；commit #5 删除 `study.today`
- `backend/app/api/study.py` — commit #5 删除 `GET /today`
- `backend/tests/test_api_series.py` — 测试 BackgroundTasks 与 refresh-anilist
- `backend/tests/test_api_episodes.py` — 测试 `/scenes` 端点
- `frontend/src/types.ts` — 加 `JourneyResponse` / `SceneNode` / `Character` 等类型
- `frontend/src/lib/api.ts` — 加 `getJourney` / `getScenes` / `refreshAnilist`，commit #5 移除 `getToday`
- `frontend/src/pages/Today.tsx` — 重写：`CharacterHeader` + `SceneTimeline`
- `frontend/src/components/Layout.tsx` — 重写：2 主 tab + 次级链接
- `frontend/src/pages/Series.tsx` — 角色头像 + "重新匹配"按钮
- `frontend/src/pages/Reading.tsx` — `?scene=N` 滚动 + 回看 banner

---

## Task 1: 数据模型 + 幂等 migration

**Files:**
- Modify: `backend/app/models/content.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db.py`
- Create: `backend/tests/test_models_scene.py`
- Create: `backend/tests/test_db_migrations.py`

### Step 1.1: 失败测试 — Scene 基本字段与唯一性

- [ ] **写测试** `backend/tests/test_models_scene.py`：

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Episode, Scene, Series


def _episode(db_session):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="ready",
                total_lines=100)
    db_session.add(s)
    db_session.commit()
    return e


def test_scene_create_with_required_fields(db_session):
    ep = _episode(db_session)
    sc = Scene(episode_id=ep.id, idx=0, title_zh="便利店发抖",
               start_line_idx=0, end_line_idx=22, line_count=23)
    db_session.add(sc)
    db_session.commit()
    assert sc.id is not None


def test_scene_unique_per_episode_idx(db_session):
    ep = _episode(db_session)
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="A",
                         start_line_idx=0, end_line_idx=10, line_count=11))
    db_session.commit()
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="B",
                         start_line_idx=11, end_line_idx=20, line_count=10))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_scene_cascade_delete_with_episode(db_session):
    ep = _episode(db_session)
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="X",
                         start_line_idx=0, end_line_idx=5, line_count=6))
    db_session.commit()
    db_session.delete(ep)
    db_session.commit()
    assert db_session.query(Scene).count() == 0
```

### Step 1.2: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_models_scene.py -v`
Expected: ImportError on `Scene`（尚未定义）。

### Step 1.3: 实现 Scene 模型 + 关系 + 导出

- [ ] **修改** `backend/app/models/content.py`，在文件末尾追加：

```python
class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (UniqueConstraint("episode_id", "idx", name="uq_scene_episode_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]
    title_zh: Mapped[str]
    start_line_idx: Mapped[int]
    end_line_idx: Mapped[int]
    line_count: Mapped[int]

    episode: Mapped["Episode"] = relationship(back_populates="scenes")
```

- [ ] **修改** `backend/app/models/content.py`，在 `Episode` 类内 `lines` 关系之后追加：

```python
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", order_by="Scene.idx"
    )
```

- [ ] **修改** `backend/app/models/__init__.py`：

```python
from app.models.content import Episode, Line, Scene, Series
from app.models.study import AppSetting, DailySession, GrammarPoint, Vocab

__all__ = [
    "Series", "Episode", "Line", "Scene",
    "Vocab", "GrammarPoint", "DailySession", "AppSetting",
]
```

### Step 1.4: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_models_scene.py -v`
Expected: 3 个测试全部 PASS。

### Step 1.5: 失败测试 — Series 加 AniList 字段

- [ ] **追加到** `backend/tests/test_models_scene.py`：

```python
def test_series_has_anilist_fields_with_defaults(db_session):
    s = Series(title="孤独摇滚")
    db_session.add(s)
    db_session.commit()
    assert s.anilist_id is None
    assert s.anilist_status == "pending"
    assert s.characters is None


def test_series_characters_json_roundtrip(db_session):
    s = Series(title="A")
    s.characters = [{"name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
                     "image_url": "https://example/h.png", "role": "MAIN"}]
    s.anilist_id = 130003
    s.anilist_status = "matched"
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    assert s.characters[0]["name_jp"] == "後藤ひとり"
    assert s.anilist_id == 130003
```

### Step 1.6: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_models_scene.py -v -k anilist`
Expected: `AttributeError: 'Series' object has no attribute 'anilist_id'`。

### Step 1.7: 实现 Series 新字段

- [ ] **修改** `backend/app/models/content.py`，在 `Series` 类的 `created_at` 字段之后、`episodes` 关系之前追加：

```python
    anilist_id: Mapped[int | None] = mapped_column(default=None)
    anilist_status: Mapped[str] = mapped_column(default="pending")
    characters: Mapped[list | None] = mapped_column(JSON, default=None)
```

### Step 1.8: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_models_scene.py -v`
Expected: 5 个测试全部 PASS。

### Step 1.9: 失败测试 — Episode 加 `scenes_split`

- [ ] **追加到** `backend/tests/test_models_scene.py`：

```python
def test_episode_scenes_split_default_false(db_session):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="processing",
                total_lines=10)
    db_session.add(s)
    db_session.commit()
    assert e.scenes_split is False
```

### Step 1.10: 实现 Episode 新字段

- [ ] **修改** `backend/app/models/content.py`，在 `Episode` 类的 `reading_done` 字段之后追加：

```python
    scenes_split: Mapped[bool] = mapped_column(default=False)
```

### Step 1.11: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_models_scene.py -v`
Expected: 6 个测试全部 PASS。

### Step 1.12: 失败测试 — `_migrate_in_place` 幂等

- [ ] **写测试** `backend/tests/test_db_migrations.py`：

```python
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.db import _migrate_in_place


def _engine_with_old_series_table():
    """模拟"旧库"：没有新加列的 series 表。"""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE series (id INTEGER PRIMARY KEY, title VARCHAR)"
        ))
        conn.execute(text(
            "CREATE TABLE episode (id INTEGER PRIMARY KEY, total_lines INTEGER)"
        ))
    return engine


def _columns(engine, table):
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def test_migrate_adds_missing_columns():
    engine = _engine_with_old_series_table()
    _migrate_in_place(engine)
    assert {"anilist_id", "anilist_status", "characters"} <= _columns(engine, "series")
    assert "scenes_split" in _columns(engine, "episode")


def test_migrate_is_idempotent():
    engine = _engine_with_old_series_table()
    _migrate_in_place(engine)
    # 第二次调用不应抛错
    _migrate_in_place(engine)
    assert {"anilist_id", "anilist_status", "characters"} <= _columns(engine, "series")
```

### Step 1.13: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_db_migrations.py -v`
Expected: `ImportError: cannot import name '_migrate_in_place'`。

### Step 1.14: 实现 `_migrate_in_place`

- [ ] **修改** `backend/app/db.py`，把现有 `init_app_db` 替换为以下整段（保留 `init_db`、`make_engine`、`make_session_factory`、`get_db` 等原有函数）：

```python
from sqlalchemy import text


def _add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    """幂等加列。SQLite 没 IF NOT EXISTS 的 ADD COLUMN，靠捕错来识别。"""
    try:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            return
        raise


def _migrate_in_place(engine: Engine) -> None:
    """补齐 create_all 不会处理的新增列。每次启动跑一次。"""
    _add_column_if_missing(engine, "series", "anilist_id", "INTEGER")
    _add_column_if_missing(engine, "series", "anilist_status",
                           "VARCHAR DEFAULT 'pending'")
    _add_column_if_missing(engine, "series", "characters", "JSON")
    _add_column_if_missing(engine, "episode", "scenes_split",
                           "BOOLEAN DEFAULT 0")


def init_app_db() -> None:
    """应用启动时建表 + 补列。"""
    init_db(_engine)
    _migrate_in_place(_engine)
```

文件顶部已 `from sqlalchemy import Engine, create_engine`，现在加上 `text`：把
`from sqlalchemy import Engine, create_engine` 改为
`from sqlalchemy import Engine, create_engine, text`（去掉重复 import）。

### Step 1.15: 运行所有 backend 测试

Run: `cd backend && uv run pytest -q`
Expected: 全绿，包括新测试和原有的 24+ 测试文件。

### Step 1.16: 提交

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add backend/app/models/ backend/app/db.py backend/tests/test_models_scene.py backend/tests/test_db_migrations.py
git commit -m "feat(db): add Scene table, anilist fields, scenes_split

- new Scene model with (episode_id, idx) unique constraint and cascade
- Series gains anilist_id / anilist_status / characters JSON
- Episode gains scenes_split flag for resumable pipeline
- init_app_db now runs idempotent ALTER TABLE for new columns

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: AniList GraphQL 客户端

**Files:**
- Create: `backend/app/services/anilist.py`
- Create: `backend/tests/test_anilist.py`

### Step 2.1: 失败测试 — 匹配成功提取主角

- [ ] **写测试** `backend/tests/test_anilist.py`：

```python
import httpx
import pytest

from app.services import anilist


def _client_with(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url=anilist.API_BASE)


def test_fetch_returns_id_and_characters_on_match():
    def handler(request):
        assert request.url.path == "/"
        payload = httpx.Response.json
        body = request.read()
        assert b"$search" in body
        return httpx.Response(200, json={
            "data": {"Media": {
                "id": 130003,
                "characters": {"edges": [
                    {"role": "MAIN", "node": {
                        "name": {"full": "Hitori Gotoh", "native": "後藤ひとり"},
                        "image": {"large": "https://img.anili.st/h.png"}}},
                    {"role": "SUPPORTING", "node": {
                        "name": {"full": "Nijika Ijichi", "native": "伊地知虹夏"},
                        "image": {"large": "https://img.anili.st/n.png"}}},
                ]}
            }}
        })

    with _client_with(handler) as http:
        out = anilist.fetch_series_metadata("Bocchi the Rock", http=http)

    assert out is not None
    assert out["anilist_id"] == 130003
    assert out["characters"][0] == {
        "name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
        "image_url": "https://img.anili.st/h.png", "role": "MAIN",
    }
    assert out["characters"][1]["role"] == "SUPPORTING"


def test_fetch_returns_none_on_no_match():
    def handler(request):
        # AniList GraphQL：无匹配时 data.Media 为 null
        return httpx.Response(200, json={"data": {"Media": None}})

    with _client_with(handler) as http:
        assert anilist.fetch_series_metadata("no-such-anime-xxxx", http=http) is None


def test_fetch_raises_on_http_5xx():
    def handler(request):
        return httpx.Response(503, text="upstream down")

    with _client_with(handler) as http:
        with pytest.raises(anilist.AniListError):
            anilist.fetch_series_metadata("x", http=http)


def test_fetch_raises_on_graphql_errors():
    def handler(request):
        return httpx.Response(200, json={
            "errors": [{"message": "validation failed"}],
            "data": None,
        })

    with _client_with(handler) as http:
        with pytest.raises(anilist.AniListError):
            anilist.fetch_series_metadata("x", http=http)


def test_fetch_handles_missing_native_name():
    def handler(request):
        return httpx.Response(200, json={"data": {"Media": {
            "id": 1,
            "characters": {"edges": [{"role": "MAIN", "node": {
                "name": {"full": "Some Char", "native": None},
                "image": {"large": "https://x/c.png"}}}]}}}})

    with _client_with(handler) as http:
        out = anilist.fetch_series_metadata("x", http=http)
    assert out["characters"][0]["name_jp"] is None
    assert out["characters"][0]["name_en"] == "Some Char"
```

### Step 2.2: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_anilist.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.anilist'`。

### Step 2.3: 实现 AniList 客户端

- [ ] **写文件** `backend/app/services/anilist.py`：

```python
"""AniList GraphQL 客户端。公开免 key 端点 https://graphql.anilist.co。

单部番一次调用，无 batch，无 retry —— 单用户本地无并发压力。
返回主角 + 前若干配角的姓名与头像 URL。
"""
import httpx

API_BASE = "https://graphql.anilist.co"
TIMEOUT = 10.0

_QUERY = """
query ($search: String) {
  Media(search: $search, type: ANIME) {
    id
    characters(sort: ROLE, page: 1, perPage: 5) {
      edges {
        role
        node {
          name { full native }
          image { large }
        }
      }
    }
  }
}
""".strip()


class AniListError(RuntimeError):
    pass


def fetch_series_metadata(title: str, http: httpx.Client | None = None) -> dict | None:
    """查 AniList，返回 {"anilist_id": int, "characters": [...]}；无匹配返回 None。

    HTTP / GraphQL / JSON 错误一律抛 AniListError 由调用方处理。
    """
    owns_client = http is None
    if http is None:
        http = httpx.Client(base_url=API_BASE, timeout=TIMEOUT)
    try:
        resp = http.post("/", json={"query": _QUERY, "variables": {"search": title}})
    except httpx.HTTPError as exc:
        raise AniListError(f"AniList 网络错误: {exc}") from exc
    finally:
        if owns_client:
            http.close()

    if resp.status_code != 200:
        raise AniListError(
            f"AniList 返回 {resp.status_code}: {resp.text[:200]}"
        )
    try:
        body = resp.json()
    except ValueError as exc:
        raise AniListError(f"AniList 响应非 JSON: {resp.text[:200]}") from exc

    if body.get("errors"):
        raise AniListError(f"AniList GraphQL 错误: {body['errors']}")

    media = (body.get("data") or {}).get("Media")
    if media is None:
        return None

    chars = []
    for edge in (media.get("characters") or {}).get("edges") or []:
        node = edge.get("node") or {}
        name = node.get("name") or {}
        image = node.get("image") or {}
        chars.append({
            "name_en": name.get("full"),
            "name_jp": name.get("native"),
            "image_url": image.get("large"),
            "role": edge.get("role"),
        })

    return {"anilist_id": media.get("id"), "characters": chars}
```

### Step 2.4: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_anilist.py -v`
Expected: 5 个测试全部 PASS。

### Step 2.5: 提交

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add backend/app/services/anilist.py backend/tests/test_anilist.py
git commit -m "feat(services): add AniList GraphQL client

Single-shot Media + characters query, returns (id, characters[])
or None on no-match. Raises AniListError on HTTP / GraphQL / JSON
errors so callers can set Series.anilist_status='failed' cleanly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 加工流水线切场景

**Files:**
- Modify: `backend/app/services/pipeline.py`
- Create: `backend/tests/test_pipeline_scenes.py`

### Step 3.1: 失败测试 — 正常切场景 + 写表 + 置位 `scenes_split`

- [ ] **写测试** `backend/tests/test_pipeline_scenes.py`：

```python
import json

import pytest

from app.grammar_loader import load_grammar_seed
from app.models import Episode, Line, Scene, Series
from app.services import pipeline


def _make_episode(db_session, n_lines: int):
    s = Series(title="番")
    e = Episode(series=s, number=1, source="upload", status="processing",
                total_lines=n_lines)
    for i in range(n_lines):
        e.lines.append(Line(idx=i, text_jp=f"行{i}", processed=False))
    db_session.add(s)
    db_session.commit()
    return e


def _route_llm(split_response, *, annotate=None):
    """返回一个假 llm.call_json：第一次（切场景）返回 split_response，
    之后（注标）按 annotate 函数回填。annotate=None 时返回最小合法注标。"""
    state = {"calls": 0}

    def fake(system, user, model=None, max_tokens=4000):
        state["calls"] += 1
        if state["calls"] == 1:
            return split_response
        if annotate is not None:
            return annotate(system, user)
        # 默认注标：按 user 里 idx 回填空注释
        payload = json.loads(user)
        return {"lines": [{"idx": ln["idx"], "translation_zh": "",
                           "grammar_notes": [], "register_tag": "casual",
                           "grammar_point_keys": []} for ln in payload["lines"]],
                "vocab": []}

    fake.state = state
    return fake


def test_splits_scenes_writes_rows_and_flips_flag(db_session, monkeypatch):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 30)
    split = {"scenes": [
        {"title_zh": "开场", "start_idx": 0, "end_idx": 9},
        {"title_zh": "冲突", "start_idx": 10, "end_idx": 19},
        {"title_zh": "结尾", "start_idx": 20, "end_idx": 29},
    ]}
    monkeypatch.setattr(pipeline.llm, "call_json", _route_llm(split))

    pipeline.process_episode(db_session, ep.id, batch_size=100)

    db_session.refresh(ep)
    assert ep.scenes_split is True
    assert ep.status == "ready"
    scenes = db_session.query(Scene).filter_by(episode_id=ep.id).order_by(Scene.idx).all()
    assert [s.title_zh for s in scenes] == ["开场", "冲突", "结尾"]
    assert [(s.start_line_idx, s.end_line_idx) for s in scenes] == [
        (0, 9), (10, 19), (20, 29),
    ]
    assert [s.line_count for s in scenes] == [10, 10, 10]
```

### Step 3.2: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_pipeline_scenes.py::test_splits_scenes_writes_rows_and_flips_flag -v`
Expected: `AttributeError`（`ep.scenes_split` 已存在，但 `pipeline.process_episode` 还没切场景逻辑）→ 实际表现：scenes 表为空、`scenes_split` 仍 False，断言失败。

### Step 3.3: 实现切场景步骤

- [ ] **修改** `backend/app/services/pipeline.py`，在文件顶部 import 区追加 `Scene`：

```python
from app.models import Episode, GrammarPoint, Line, Scene, Vocab
```

- [ ] **修改** `backend/app/services/pipeline.py`，在 `_SYSTEM` 之后追加：

```python
_SCENE_SYSTEM = """你是动漫剧本场景切分助手。给定一集的全部台词，按对话聚集和角色切换切成 5–8 个场景（极少台词时 2–3 个也可）。
只返回 JSON 对象，不要多余文字。结构：
{"scenes": [{"title_zh": "5-10 字中文短标题", "start_idx": 整数, "end_idx": 整数}]}
要求：覆盖全部 idx 无空隙、无重叠；start_idx <= end_idx；title_zh 非空。"""


def _split_scenes(lines: list[Line]) -> list[dict]:
    """调 LLM 切场景，返回 [{title_zh, start_idx, end_idx}] 列表（未校验）。"""
    user = json.dumps({
        "lines": [{"idx": ln.idx, "text": ln.text_jp, "speaker": ln.speaker}
                  for ln in lines],
    }, ensure_ascii=False)
    result = llm.call_json(system=_SCENE_SYSTEM, user=user)
    return result.get("scenes") or []


def _validate_scenes(scenes: list[dict], total_lines: int) -> list[dict]:
    """校验场景列表覆盖性。失败抛 ValueError；返回按 start_idx 排序后的列表。"""
    if not scenes:
        raise ValueError("切场景返回空列表")
    ordered = sorted(scenes, key=lambda s: s.get("start_idx", -1))
    for sc in ordered:
        if not sc.get("title_zh"):
            raise ValueError(f"场景缺少 title_zh: {sc}")
        if sc.get("start_idx") is None or sc.get("end_idx") is None:
            raise ValueError(f"场景缺少 idx: {sc}")
        if sc["start_idx"] > sc["end_idx"]:
            raise ValueError(f"场景 start_idx > end_idx: {sc}")
    if ordered[0]["start_idx"] != 0:
        raise ValueError(f"首场景必须从 idx=0 开始: {ordered[0]}")
    if ordered[-1]["end_idx"] != total_lines - 1:
        raise ValueError(
            f"末场景必须到 idx={total_lines - 1}: {ordered[-1]}"
        )
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt["start_idx"] != prev["end_idx"] + 1:
            raise ValueError(
                f"场景之间空隙或重叠: prev.end={prev['end_idx']}, next.start={nxt['start_idx']}"
            )
    return ordered


def _write_scenes(session: Session, episode_id: int, scenes: list[dict]) -> None:
    for idx, sc in enumerate(scenes):
        session.add(Scene(
            episode_id=episode_id, idx=idx, title_zh=sc["title_zh"],
            start_line_idx=sc["start_idx"], end_line_idx=sc["end_idx"],
            line_count=sc["end_idx"] - sc["start_idx"] + 1,
        ))
```

- [ ] **修改** `backend/app/services/pipeline.py`，在 `process_episode` 函数体里、设置 `episode.status = "processing"` 与 `grammar_index = _grammar_index(...)` 之间插入切场景步骤：

```python
    if not episode.scenes_split:
        all_lines = (
            session.query(Line)
            .filter_by(episode_id=episode_id)
            .order_by(Line.idx)
            .all()
        )
        try:
            raw_scenes = _split_scenes(all_lines)
            ordered = _validate_scenes(raw_scenes, episode.total_lines)
            _write_scenes(session, episode_id, ordered)
            episode.scenes_split = True
            session.commit()
        except Exception:
            try:
                session.rollback()
                ep = session.get(Episode, episode_id)
                if ep is not None:
                    ep.status = "failed"
                    session.commit()
            except Exception:
                pass
            raise
```

### Step 3.4: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_pipeline_scenes.py -v`
Expected: PASS。

### Step 3.5: 失败测试 — 校验：空场景 / 空隙 / 重叠 / 不覆盖

- [ ] **追加到** `backend/tests/test_pipeline_scenes.py`：

```python
@pytest.mark.parametrize("bad_scenes,reason", [
    ({"scenes": []}, "empty"),
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 4},
                 {"title_zh": "B", "start_idx": 6, "end_idx": 9}]}, "gap"),  # 缺 idx=5
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 6},
                 {"title_zh": "B", "start_idx": 5, "end_idx": 9}]}, "overlap"),
    ({"scenes": [{"title_zh": "A", "start_idx": 0, "end_idx": 5}]},
     "incomplete"),  # 只覆盖 6 行，total=10
    ({"scenes": [{"title_zh": "", "start_idx": 0, "end_idx": 9}]}, "empty-title"),
])
def test_split_validation_failures_mark_episode_failed(
        db_session, monkeypatch, bad_scenes, reason):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 10)
    monkeypatch.setattr(pipeline.llm, "call_json", _route_llm(bad_scenes))

    with pytest.raises(ValueError):
        pipeline.process_episode(db_session, ep.id, batch_size=100)

    db_session.refresh(ep)
    assert ep.status == "failed", f"reason={reason}"
    assert ep.scenes_split is False
    assert db_session.query(Scene).filter_by(episode_id=ep.id).count() == 0
```

### Step 3.6: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_pipeline_scenes.py -v`
Expected: 全部 PASS（已实现的 `_validate_scenes` 应覆盖这些情况）。

### Step 3.7: 失败测试 — `scenes_split=True` 时不重切

- [ ] **追加到** `backend/tests/test_pipeline_scenes.py`：

```python
def test_does_not_resplit_when_already_split(db_session, monkeypatch):
    load_grammar_seed(db_session)
    ep = _make_episode(db_session, 10)
    # 预置一个已切好的场景，并把 flag 打 True
    db_session.add(Scene(episode_id=ep.id, idx=0, title_zh="预存",
                         start_line_idx=0, end_line_idx=9, line_count=10))
    ep.scenes_split = True
    db_session.commit()

    fake = _route_llm({"scenes": [
        {"title_zh": "不应被使用", "start_idx": 0, "end_idx": 9}]})
    monkeypatch.setattr(pipeline.llm, "call_json", fake)

    pipeline.process_episode(db_session, ep.id, batch_size=100)

    # 切场景 LLM 路径不应被走（fake 第一次调用是注标）
    titles = [s.title_zh for s in
              db_session.query(Scene).filter_by(episode_id=ep.id).order_by(Scene.idx)]
    assert titles == ["预存"]
```

### Step 3.8: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_pipeline_scenes.py -v`
Expected: 全部 PASS。

### Step 3.9: 运行全部 backend 测试

Run: `cd backend && uv run pytest -q`
Expected: 全绿。注意确认 `tests/test_pipeline.py` 的旧用例仍 PASS——原有的 `_fake_llm` 第一次调用现在会被当成"切场景"。

- [ ] 如果 `test_pipeline.py` 失败，**修改** `backend/tests/test_pipeline.py` 的 `_episode_with_lines`，在写 Episode 后立即 `ep.scenes_split = True` 并 commit（旧用例不关心切场景逻辑，提前置位绕过即可）。再 run pytest 直到全绿。

### Step 3.10: 提交

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add backend/app/services/pipeline.py backend/tests/test_pipeline_scenes.py backend/tests/test_pipeline.py
git commit -m "feat(pipeline): scene splitting before line annotation

- process_episode now calls _split_scenes first when scenes_split=False
- _validate_scenes enforces coverage (no gap / overlap / partial / empty)
- failed split marks episode failed; never silently degrades to one scene
- resumable: scenes_split=True skips the split step on retry

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: API 端点（today/journey · scenes · anilist hooks）

**Files:**
- Modify: `backend/app/api/series.py`
- Modify: `backend/app/api/episodes.py`
- Create: `backend/app/api/today.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api_series.py`
- Modify: `backend/tests/test_api_episodes.py`
- Create: `backend/tests/test_api_today_journey.py`

### Step 4.1: 失败测试 — `POST /api/series` 返回 `pending` + 后台调用 AniList

- [ ] **覆盖** `backend/tests/test_api_series.py` 内容为：

```python
from unittest.mock import patch

from app.models import Series


def test_create_and_list_series(client, db_session):
    resp = client.post("/api/series", json={"title": "鬼灭之刃"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "鬼灭之刃"
    assert body["anilist_status"] == "pending"
    assert body["anilist_id"] is None
    assert body["characters"] is None

    listed = client.get("/api/series").json()
    assert any(s["id"] == body["id"] for s in listed)


def test_set_current_series(client, db_session):
    a = client.post("/api/series", json={"title": "A"}).json()["id"]
    b = client.post("/api/series", json={"title": "B"}).json()["id"]
    client.post(f"/api/series/{a}/set-current")
    client.post(f"/api/series/{b}/set-current")
    rows = {s.id: s.is_current for s in db_session.query(Series).all()}
    assert rows[a] is False and rows[b] is True


def test_create_series_triggers_anilist_background(client, db_session):
    captured = {}

    def fake_fetch(title, http=None):
        captured["title"] = title
        return {"anilist_id": 130003, "characters": [
            {"name_en": "Hitori Gotoh", "name_jp": "後藤ひとり",
             "image_url": "https://x/h.png", "role": "MAIN"}]}

    with patch("app.api.series.fetch_series_metadata", fake_fetch):
        resp = client.post("/api/series", json={"title": "Bocchi the Rock"})

    assert resp.status_code == 200
    sid = resp.json()["id"]
    # FastAPI TestClient 会同步跑 BackgroundTasks；查库验证已写回
    db_session.expire_all()
    s = db_session.get(Series, sid)
    assert s.anilist_status == "matched"
    assert s.anilist_id == 130003
    assert s.characters[0]["name_jp"] == "後藤ひとり"
    assert captured["title"] == "Bocchi the Rock"


def test_create_series_anilist_not_found(client, db_session):
    with patch("app.api.series.fetch_series_metadata", lambda t, http=None: None):
        sid = client.post("/api/series", json={"title": "no-such"}).json()["id"]
    db_session.expire_all()
    assert db_session.get(Series, sid).anilist_status == "not_found"


def test_create_series_anilist_error_marks_failed(client, db_session):
    from app.services.anilist import AniListError

    def boom(title, http=None):
        raise AniListError("upstream down")

    with patch("app.api.series.fetch_series_metadata", boom):
        sid = client.post("/api/series", json={"title": "X"}).json()["id"]
    db_session.expire_all()
    assert db_session.get(Series, sid).anilist_status == "failed"


def test_get_series_detail_includes_anilist_fields(client, db_session):
    s = Series(title="A", anilist_id=42, anilist_status="matched",
               characters=[{"name_en": "C", "name_jp": None,
                            "image_url": "https://x/c.png", "role": "MAIN"}])
    db_session.add(s); db_session.commit()
    body = client.get(f"/api/series/{s.id}").json()
    assert body["anilist_status"] == "matched"
    assert body["anilist_id"] == 42
    assert body["characters"][0]["image_url"] == "https://x/c.png"


def test_refresh_anilist_endpoint(client, db_session):
    s = Series(title="A", anilist_status="not_found")
    db_session.add(s); db_session.commit()

    def fake(title, http=None):
        return {"anilist_id": 1, "characters": []}

    with patch("app.api.series.fetch_series_metadata", fake):
        resp = client.post(f"/api/series/{s.id}/refresh-anilist")
    assert resp.status_code == 200
    assert resp.json()["anilist_status"] == "matched"
    db_session.expire_all()
    assert db_session.get(Series, s.id).anilist_id == 1
```

### Step 4.2: 运行测试验证失败

Run: `cd backend && uv run pytest tests/test_api_series.py -v`
Expected: 多数失败（响应缺字段、端点不存在）。

### Step 4.3: 实现 series.py 改动

- [ ] **覆盖** `backend/app/api/series.py` 内容为：

```python
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, get_db
from app.models import Series
from app.services.anilist import AniListError, fetch_series_metadata
from app.services.jimaku import JimakuClient, JimakuError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/series", tags=["series"])


class SeriesCreate(BaseModel):
    title: str
    title_jp: str | None = None
    jimaku_entry_id: int | None = None


def _series_dict(s: Series) -> dict:
    return {
        "id": s.id, "title": s.title, "title_jp": s.title_jp,
        "jimaku_entry_id": s.jimaku_entry_id, "is_current": s.is_current,
        "anilist_id": s.anilist_id, "anilist_status": s.anilist_status,
        "characters": s.characters,
    }


def _run_anilist_lookup(series_id: int, title: str) -> None:
    """后台任务：拉 AniList 并写回 Series。绝不让异常逃出。

    刻意自建 Session（不复用请求级 session）：BackgroundTasks 在响应发回后才跑，
    请求级 session 已关闭。
    """
    db = SessionLocal()
    try:
        try:
            result = fetch_series_metadata(title)
        except AniListError as exc:
            logger.warning("AniList lookup failed for %r: %s", title, exc)
            s = db.get(Series, series_id)
            if s is not None:
                s.anilist_status = "failed"
                db.commit()
            return
        s = db.get(Series, series_id)
        if s is None:
            return
        if result is None:
            s.anilist_status = "not_found"
        else:
            s.anilist_id = result["anilist_id"]
            s.characters = result["characters"]
            s.anilist_status = "matched"
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("AniList background task crashed for series %s", series_id)
    finally:
        db.close()


@router.get("")
def list_series(db: Session = Depends(get_db)) -> list[dict]:
    return [_series_dict(s) for s in db.query(Series).order_by(Series.id).all()]


@router.post("")
def create_series(body: SeriesCreate, bg: BackgroundTasks,
                  db: Session = Depends(get_db)) -> dict:
    s = Series(title=body.title, title_jp=body.title_jp,
               jimaku_entry_id=body.jimaku_entry_id)
    db.add(s)
    db.commit()
    bg.add_task(_run_anilist_lookup, s.id, s.title)
    return _series_dict(s)


@router.get("/{series_id}")
def get_series(series_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
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


@router.post("/{series_id}/refresh-anilist")
def refresh_anilist(series_id: int, db: Session = Depends(get_db)) -> dict:
    """同步重跑 AniList 查询。错误转 anilist_status=failed，HTTP 仍 200。"""
    s = db.get(Series, series_id)
    if s is None:
        raise HTTPException(404, "番剧不存在")
    try:
        result = fetch_series_metadata(s.title)
    except AniListError as exc:
        logger.warning("AniList refresh failed for %r: %s", s.title, exc)
        s.anilist_status = "failed"
        db.commit()
        return _series_dict(s)
    if result is None:
        s.anilist_status = "not_found"
    else:
        s.anilist_id = result["anilist_id"]
        s.characters = result["characters"]
        s.anilist_status = "matched"
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

注意：后台任务用 `SessionLocal()` 自建 session 而不是 `Depends(get_db)`（请求级 session 已关闭）。在测试里，`conftest.py` 的 `client` fixture 覆盖了 `get_db` 但**没有覆盖** `SessionLocal`。需要修 conftest 让 BackgroundTasks 也走测试 session。

- [ ] **修改** `backend/tests/conftest.py`，把 `client` fixture 改成：

```python
@pytest.fixture
def client(db_session, monkeypatch):
    """TestClient，get_db 与 SessionLocal 都覆盖为测试用的内存会话。

    刻意不使用 `with TestClient(...)`：不触发 startup/shutdown 生命周期事件，
    避免 startup 里的 init_app_db / load_grammar_seed 操作真实文件库。
    测试库由 db_session 夹具建表；需要语法种子的测试自行调用 load_grammar_seed。
    BackgroundTasks 用的 SessionLocal 也指向同一 db_session，使后台写入在测试内可见。
    """
    app.dependency_overrides[get_db] = lambda: db_session
    # 后台任务自建 session 也指向同一内存库
    monkeypatch.setattr("app.api.series.SessionLocal",
                        lambda: _NoCloseSession(db_session))
    yield TestClient(app)
    app.dependency_overrides.clear()


class _NoCloseSession:
    """把 db_session 包一层：close() 是 no-op，避免 BackgroundTasks 关掉夹具会话。"""
    def __init__(self, session):
        self._s = session

    def __getattr__(self, name):
        return getattr(self._s, name)

    def close(self):
        pass
```

把 `_NoCloseSession` 放到 conftest.py 文件顶部（在 fixtures 之前）。

### Step 4.4: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_api_series.py -v`
Expected: 全部 PASS。

### Step 4.5: 失败测试 — `GET /api/episodes/{id}/scenes` 三态 + 锁定脱敏

- [ ] **追加到** `backend/tests/test_api_episodes.py`：

```python
def test_scenes_endpoint_returns_three_states_with_redaction(client, db_session):
    from app.models import Episode, Line, Scene, Series

    s = Series(title="番"); db_session.add(s); db_session.commit()
    ep = Episode(series_id=s.id, number=1, source="upload", status="ready",
                 total_lines=30, read_position=15, scenes_split=True)
    for i in range(30):
        ep.lines.append(Line(idx=i, text_jp=f"行{i}", processed=True))
    db_session.add(ep); db_session.commit()
    db_session.add_all([
        Scene(episode_id=ep.id, idx=0, title_zh="开场",
              start_line_idx=0, end_line_idx=9, line_count=10),
        Scene(episode_id=ep.id, idx=1, title_zh="冲突",
              start_line_idx=10, end_line_idx=19, line_count=10),
        Scene(episode_id=ep.id, idx=2, title_zh="结尾",
              start_line_idx=20, end_line_idx=29, line_count=10),
    ])
    db_session.commit()

    body = client.get(f"/api/episodes/{ep.id}/scenes").json()
    assert len(body) == 3
    assert body[0]["state"] == "done"
    assert body[0]["title_zh"] == "开场"
    assert body[1]["state"] == "current"
    assert body[1]["preview_lines"] == ["行10", "行11"]
    # 锁定脱敏
    locked = body[2]
    assert locked["state"] == "locked"
    assert locked["title_zh"] is None
    assert locked["line_count"] is None
    assert locked["start_line_idx"] is None
    assert locked["end_line_idx"] is None
    assert locked["idx"] == 2


def test_scenes_endpoint_returns_empty_when_not_split(client, db_session):
    from app.models import Episode, Series

    s = Series(title="A"); db_session.add(s); db_session.commit()
    ep = Episode(series_id=s.id, number=1, source="upload", status="processing",
                 total_lines=10, scenes_split=False)
    db_session.add(ep); db_session.commit()
    assert client.get(f"/api/episodes/{ep.id}/scenes").json() == []
```

### Step 4.6: 实现 `/scenes` 端点

- [ ] **修改** `backend/app/api/episodes.py`，在文件 import 区加入 `Scene`：

```python
from app.models import Episode, Line, Scene, Series
```

- [ ] **修改** `backend/app/api/episodes.py`，在文件末尾追加：

```python
def _scene_state(scene: Scene, read_position: int) -> str:
    if scene.end_line_idx < read_position:
        return "done"
    if scene.start_line_idx <= read_position <= scene.end_line_idx:
        return "current"
    return "locked"


def _scene_dict(scene: Scene, state: str, preview: list[str] | None = None) -> dict:
    if state == "locked":
        return {"id": scene.id, "idx": scene.idx, "state": "locked",
                "title_zh": None, "line_count": None,
                "start_line_idx": None, "end_line_idx": None}
    out = {
        "id": scene.id, "idx": scene.idx, "state": state,
        "title_zh": scene.title_zh, "line_count": scene.line_count,
        "start_line_idx": scene.start_line_idx, "end_line_idx": scene.end_line_idx,
    }
    if state == "current" and preview is not None:
        out["preview_lines"] = preview
    return out


@router.get("/{episode_id}/scenes")
def get_scenes(episode_id: int, db: Session = Depends(get_db)) -> list[dict]:
    ep = db.get(Episode, episode_id)
    if ep is None:
        raise HTTPException(404, "剧集不存在")
    if not ep.scenes_split or ep.status != "ready":
        return []
    scenes = (
        db.query(Scene).filter_by(episode_id=episode_id)
        .order_by(Scene.idx).all()
    )
    out: list[dict] = []
    for sc in scenes:
        state = _scene_state(sc, ep.read_position)
        preview = None
        if state == "current":
            lines = (
                db.query(Line).filter_by(episode_id=episode_id)
                .filter(Line.idx >= sc.start_line_idx, Line.idx <= sc.end_line_idx)
                .order_by(Line.idx).limit(2).all()
            )
            preview = [ln.text_jp for ln in lines]
        out.append(_scene_dict(sc, state, preview))
    return out
```

### Step 4.7: 运行测试验证通过

Run: `cd backend && uv run pytest tests/test_api_episodes.py -v`
Expected: 全部 PASS（旧测试 + 2 个新测试）。

### Step 4.8: 失败测试 — `GET /api/today/journey`

- [ ] **写测试** `backend/tests/test_api_today_journey.py`：

```python
from app.models import Episode, Line, Scene, Series


def test_journey_no_series(client, db_session):
    body = client.get("/api/today/journey").json()
    assert body["series"] is None
    assert body["current_episode"] is None
    assert body["scenes"] == []
    assert body["streak"] == 0
    assert body["due_total"] == 0


def test_journey_series_no_episode(client, db_session):
    s = Series(title="番", is_current=True); db_session.add(s); db_session.commit()
    body = client.get("/api/today/journey").json()
    assert body["series"]["id"] == s.id
    assert body["series"]["main_character"] is None
    assert body["current_episode"] is None


def test_journey_full_flow_with_main_character(client, db_session):
    s = Series(title="孤独摇滚", is_current=True, anilist_status="matched",
               anilist_id=130003,
               characters=[
                   {"name_en": "Hitori", "name_jp": "後藤ひとり",
                    "image_url": "https://x/h.png", "role": "MAIN"},
                   {"name_en": "Niko", "name_jp": "伊地知虹夏",
                    "image_url": "https://x/n.png", "role": "SUPPORTING"},
               ])
    db_session.add(s); db_session.commit()
    ep = Episode(series_id=s.id, number=5, source="upload", status="ready",
                 total_lines=30, read_position=15, scenes_split=True)
    for i in range(30):
        ep.lines.append(Line(idx=i, text_jp=f"行{i}", processed=True))
    db_session.add(ep); db_session.commit()
    db_session.add_all([
        Scene(episode_id=ep.id, idx=0, title_zh="A",
              start_line_idx=0, end_line_idx=9, line_count=10),
        Scene(episode_id=ep.id, idx=1, title_zh="B",
              start_line_idx=10, end_line_idx=19, line_count=10),
        Scene(episode_id=ep.id, idx=2, title_zh="C",
              start_line_idx=20, end_line_idx=29, line_count=10),
    ])
    db_session.commit()

    body = client.get("/api/today/journey").json()
    assert body["series"]["main_character"]["name_jp"] == "後藤ひとり"
    assert body["series"]["main_character"]["image_url"] == "https://x/h.png"
    assert body["series"]["main_character"]["fallback_initial"] == "後"
    assert body["current_episode"]["id"] == ep.id
    assert body["current_episode"]["completed_scenes"] == 1
    assert body["current_episode"]["total_scenes"] == 3
    assert [s["state"] for s in body["scenes"]] == ["done", "current", "locked"]


def test_journey_main_character_fallback_initial_from_series_title(
        client, db_session):
    s = Series(title="孤独摇滚", is_current=True, anilist_status="not_found")
    db_session.add(s); db_session.commit()
    body = client.get("/api/today/journey").json()
    # series 没 character → main_character 为 null；前端读 series.fallback_initial？
    # 按 spec §5.5：main_character 为 null 时取 series.title 首字符作 fallback_initial。
    # 实现选择：main_character 始终是 {name_jp, image_url, fallback_initial}，
    # 在没 character 时 name/image 为 null、fallback_initial 取 series.title 首字符。
    mc = body["series"]["main_character"]
    assert mc is not None
    assert mc["name_jp"] is None
    assert mc["name_en"] is None
    assert mc["image_url"] is None
    assert mc["fallback_initial"] == "孤"


def test_journey_main_character_picks_first_with_image(client, db_session):
    s = Series(title="A", is_current=True, anilist_status="matched",
               characters=[
                   {"name_en": "NoImg", "name_jp": "無画",
                    "image_url": None, "role": "MAIN"},
                   {"name_en": "Has", "name_jp": "画あり",
                    "image_url": "https://x/h.png", "role": "SUPPORTING"},
               ])
    db_session.add(s); db_session.commit()
    mc = client.get("/api/today/journey").json()["series"]["main_character"]
    assert mc["name_jp"] == "画あり"
    assert mc["image_url"] == "https://x/h.png"
```

### Step 4.9: 实现 today.py 路由

- [ ] **写文件** `backend/app/api/today.py`：

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Line, Scene, Series
from app.services import session as sess

from app.api.episodes import _scene_dict, _scene_state

router = APIRouter(prefix="/api/today", tags=["today"])


def _pick_main_character(s: Series) -> dict | None:
    """按 spec §5.5：始终返回 {name_jp, name_en, image_url, fallback_initial}。
    没匹配 character 时 name/image 为 null，fallback_initial 取 series.title 首字符。"""
    chars = s.characters or []
    with_img = next((c for c in chars if c.get("image_url")), None)
    pick = with_img or (chars[0] if chars else None)
    if pick is None:
        first = (s.title or "?")[:1]
        return {"name_en": None, "name_jp": None, "image_url": None,
                "fallback_initial": first}
    name_jp = pick.get("name_jp")
    name_en = pick.get("name_en")
    fallback_source = name_jp or name_en or s.title or "?"
    return {
        "name_en": name_en, "name_jp": name_jp,
        "image_url": pick.get("image_url"),
        "fallback_initial": fallback_source[:1],
    }


@router.get("/journey")
def journey(db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    s = db.query(Series).filter_by(is_current=True).first()
    streak = sess.compute_streak(db, today_d)
    due = sess.due_counts(db, today_d)
    due_total = due["vocab"] + due["grammar"]

    if s is None:
        return {"streak": streak, "due_total": due_total,
                "series": None, "current_episode": None, "scenes": []}

    series_block = {
        "id": s.id, "title": s.title,
        "main_character": _pick_main_character(s),
    }

    ep = sess.current_episode(db)
    if ep is None or ep.series_id != s.id:
        return {"streak": streak, "due_total": due_total,
                "series": series_block, "current_episode": None, "scenes": []}

    scenes = (
        db.query(Scene).filter_by(episode_id=ep.id)
        .order_by(Scene.idx).all()
    )
    completed = sum(1 for sc in scenes if sc.end_line_idx < ep.read_position)

    scene_out: list[dict] = []
    for sc in scenes:
        state = _scene_state(sc, ep.read_position)
        preview = None
        if state == "current":
            lines = (
                db.query(Line).filter_by(episode_id=ep.id)
                .filter(Line.idx >= sc.start_line_idx,
                        Line.idx <= sc.end_line_idx)
                .order_by(Line.idx).limit(2).all()
            )
            preview = [ln.text_jp for ln in lines]
        scene_out.append(_scene_dict(sc, state, preview))

    return {
        "streak": streak, "due_total": due_total,
        "series": series_block,
        "current_episode": {
            "id": ep.id, "number": ep.number, "title": ep.title,
            "read_position": ep.read_position, "total_lines": ep.total_lines,
            "completed_scenes": completed, "total_scenes": len(scenes),
            "status": ep.status,
        },
        "scenes": scene_out,
    }
```

- [ ] **修改** `backend/app/main.py`，在 import 区加入 `today`：

```python
    from app.api import (
        conversation, episodes, grammar, progress, series, srs, study, today, tts,
    )
    for module in (series, episodes, study, srs, grammar, conversation,
                   progress, today, tts):
        app.include_router(module.router)
```

注意：`sess.current_episode` 现在按"当前 series 的最该推进集"返回。若 episode 不属于当前 series（边界），我们也不显示——已用 `ep.series_id != s.id` 兜底。

### Step 4.10: 运行所有 backend 测试

Run: `cd backend && uv run pytest -q`
Expected: 全绿。

### Step 4.11: 提交

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add backend/app/api/series.py backend/app/api/episodes.py backend/app/api/today.py backend/app/main.py backend/tests/conftest.py backend/tests/test_api_series.py backend/tests/test_api_episodes.py backend/tests/test_api_today_journey.py
git commit -m "feat(api): today/journey, scenes endpoint, anilist hooks

- POST /api/series triggers AniList lookup via BackgroundTasks, returns
  anilist_status=pending immediately
- POST /api/series/{id}/refresh-anilist for manual retry (no body)
- GET /api/series/{id} now includes anilist fields
- GET /api/episodes/{id}/scenes returns three-state list with locked
  scenes redacted server-side
- GET /api/today/journey consolidates streak / due / series / current
  episode / scene path for the new home page
- conftest patches SessionLocal so BackgroundTasks see the test DB

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 前端重写 + 旧端点清理

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/CharacterHeader.tsx`
- Create: `frontend/src/components/SceneTimeline.tsx`
- Modify: `frontend/src/pages/Today.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/pages/Series.tsx`
- Modify: `frontend/src/pages/Reading.tsx`
- Modify: `backend/app/api/study.py` — 删除 `GET /today`
- Modify: `backend/tests/test_api_study.py` — 删除 `today` 相关用例

### Step 5.1: 新类型

- [ ] **追加到** `frontend/src/types.ts`：

```typescript
export type Character = {
  name_en: string | null;
  name_jp: string | null;
  image_url: string | null;
  role: "MAIN" | "SUPPORTING" | null;
};

export type MainCharacter = {
  name_en: string | null;
  name_jp: string | null;
  image_url: string | null;
  fallback_initial: string;
};

export type AnilistStatus = "pending" | "matched" | "not_found" | "failed";

export type SeriesWithAniList = Series & {
  anilist_id: number | null;
  anilist_status: AnilistStatus;
  characters: Character[] | null;
};

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
```

把现有的 `Series` 类型也同步加上字段：

```typescript
export type Series = {
  id: number; title: string; title_jp: string | null;
  jimaku_entry_id: number | null; is_current: boolean;
  anilist_id: number | null;
  anilist_status: AnilistStatus;
  characters: Character[] | null;
};
```

并删除老的 `Today` 类型（不再用）。

### Step 5.2: 新 API 调用

- [ ] **修改** `frontend/src/lib/api.ts`：把 `import type` 行同步更新（移除 `Today`，加 `JourneyResponse`、`SceneNode`、`SeriesWithAniList`）；把 `getToday` 整段删除；新增：

```typescript
export const getJourney = () => http<JourneyResponse>("/api/today/journey");

export const getSeries = (id: number) =>
  http<SeriesWithAniList>(`/api/series/${id}`);

export const refreshAnilist = (id: number) =>
  http<SeriesWithAniList>(`/api/series/${id}/refresh-anilist`, { method: "POST" });

export const getScenes = (episodeId: number) =>
  http<SceneNode[]>(`/api/episodes/${episodeId}/scenes`);
```

import 行整理为：

```typescript
import type {
  ConvTurn, Critique, DueItems, Episode, Grade, GrammarPoint,
  JourneyResponse, Line, Progress, SceneNode, Series, SeriesWithAniList,
  SpeakerCharacter,
} from "../types";
```

### Step 5.3: `CharacterHeader.tsx`

- [ ] **写文件** `frontend/src/components/CharacterHeader.tsx`：

```typescript
import type { MainCharacter } from "../types";

type Props = {
  seriesTitle: string;
  character: MainCharacter | null;
  episodeLabel?: string;        // e.g. "第 5 集 · 4/8 通关 · 162/247 行"
  rightSlot?: React.ReactNode;  // streak / due chip
};

export default function CharacterHeader({
  seriesTitle, character, episodeLabel, rightSlot,
}: Props) {
  const initial = character?.fallback_initial ?? seriesTitle.slice(0, 1) ?? "?";
  const displayName = character?.name_jp ?? character?.name_en;

  return (
    <div className="card-padded flex items-center gap-4">
      {character?.image_url ? (
        <img
          src={character.image_url}
          alt={displayName ?? "character"}
          className="w-16 h-16 rounded-full object-cover border border-ink-200"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
      ) : (
        <div className="w-16 h-16 rounded-full bg-sakura-100 text-sakura-700 font-bold text-2xl ja flex items-center justify-center shrink-0">
          {initial}
        </div>
      )}
      <div className="flex-1 min-w-0">
        {character && displayName && (
          <div className="text-xs text-ink-500">
            今天和你一起练的是 ·{" "}
            <span className="ja text-ink-700 font-medium">{displayName}</span>
          </div>
        )}
        <div className="text-lg font-semibold text-ink-900 truncate">
          {seriesTitle}
        </div>
        {episodeLabel && (
          <div className="text-sm text-ink-600 mt-0.5">{episodeLabel}</div>
        )}
      </div>
      {rightSlot}
    </div>
  );
}
```

### Step 5.4: `SceneTimeline.tsx`

- [ ] **写文件** `frontend/src/components/SceneTimeline.tsx`：

```typescript
import { useNavigate } from "react-router-dom";

import type { SceneNode } from "../types";

type Props = {
  episodeId: number;
  scenes: SceneNode[];
};

export default function SceneTimeline({ episodeId, scenes }: Props) {
  const navigate = useNavigate();

  if (scenes.length === 0) {
    return (
      <div className="card-padded">
        <div className="skeleton h-5 w-2/3 mb-3" />
        <div className="skeleton h-5 w-1/2 mb-3" />
        <div className="text-sm text-ink-500 mt-3">
          正在加工本集，约需 30–60 秒…
        </div>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {scenes.map((sc) => {
        if (sc.state === "locked") {
          return (
            <li
              key={sc.id}
              className="card-padded py-3 text-ink-400 italic select-none cursor-default"
            >
              🔒 场景 {sc.idx + 1} · ???
            </li>
          );
        }
        if (sc.state === "done") {
          return (
            <li
              key={sc.id}
              onClick={() => navigate(`/episodes/${episodeId}/reading?scene=${sc.idx}`)}
              className="card-padded py-3 card-hover cursor-pointer text-ink-500 flex items-center justify-between"
              title="重读这一场（不会改动进度）"
            >
              <span>
                <span className="text-emerald-600 font-semibold mr-2">✓</span>
                场景 {sc.idx + 1} · {sc.title_zh}
              </span>
              <span className="text-xs text-ink-400">{sc.line_count} 行</span>
            </li>
          );
        }
        // current
        return (
          <li
            key={sc.id}
            className="card-padded border-brand-300 ring-2 ring-brand-100 space-y-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-ink-900 font-semibold">
                <span className="text-brand-600 mr-2">▶</span>
                场景 {sc.idx + 1} · {sc.title_zh}
              </span>
              <span className="text-xs text-ink-500">{sc.line_count} 行</span>
            </div>
            {sc.preview_lines && sc.preview_lines.length > 0 && (
              <div className="ja text-sm text-ink-700 space-y-1 pl-1 border-l-2 border-brand-200">
                {sc.preview_lines.map((ln, i) => (
                  <div key={i} className="pl-2">「{ln}」</div>
                ))}
              </div>
            )}
            <button
              onClick={() => navigate(`/episodes/${episodeId}/reading?scene=${sc.idx}`)}
              className="btn-primary btn-sm"
            >
              继续读这一场 →
            </button>
          </li>
        );
      })}
    </ul>
  );
}
```

### Step 5.5: 重写 `Today.tsx`

- [ ] **覆盖** `frontend/src/pages/Today.tsx` 内容为：

```typescript
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import CharacterHeader from "../components/CharacterHeader";
import EmptyState from "../components/EmptyState";
import Loading from "../components/Loading";
import SceneTimeline from "../components/SceneTimeline";
import { getJourney } from "../lib/api";

export default function Today() {
  const { data, isLoading } = useQuery({
    queryKey: ["journey"],
    queryFn: getJourney,
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      const epPending = d.current_episode &&
        (d.current_episode.status === "processing" ||
         d.current_episode.status === "importing");
      const anilistPending = d.series?.main_character &&
        // 主角文字 fallback + 没图链 = 可能 pending；轮询 series
        !d.series.main_character.image_url;
      return epPending ? 5000 : anilistPending ? 3000 : false;
    },
  });

  if (isLoading || !data) return <Loading />;

  if (!data.series) {
    return (
      <EmptyState
        icon="📺"
        title="还没有番剧"
        hint={<>去 <Link to="/series" className="text-brand-600 hover:underline">导入你在追的第一部番 →</Link></>}
      />
    );
  }

  const ep = data.current_episode;
  const seriesTitle = data.series.title;

  const rightChip = (
    <div className="flex flex-col items-end gap-1 text-xs shrink-0">
      <span className="badge-amber">🔥 {data.streak} 天</span>
      {data.due_total > 0 ? (
        <Link to="/review" className="badge-brand hover:bg-brand-200">
          🧠 {data.due_total} 到期 →
        </Link>
      ) : (
        <span className="text-ink-400">无到期复习</span>
      )}
    </div>
  );

  const episodeLabel = ep
    ? `第 ${ep.number} 集 · ${ep.completed_scenes}/${ep.total_scenes} 通关 · ${ep.read_position}/${ep.total_lines} 行`
    : undefined;

  return (
    <div className="space-y-6">
      <CharacterHeader
        seriesTitle={seriesTitle}
        character={data.series.main_character}
        episodeLabel={episodeLabel}
        rightSlot={rightChip}
      />

      {!ep ? (
        <EmptyState
          icon="📚"
          title={`《${seriesTitle}》还没有任何一集`}
          hint={<>去 <Link to="/series" className="text-brand-600 hover:underline">导入第一集 →</Link></>}
        />
      ) : ep.status === "failed" ? (
        <div className="card-padded border-rose-200 bg-rose-50 text-rose-800 text-sm">
          本集加工失败。请到番剧库重新触发导入。
        </div>
      ) : ep.read_position >= ep.total_lines ? (
        <div className="card-padded border-emerald-200 bg-emerald-50 text-emerald-800 text-sm">
          本集已读完 · <Link to="/series" className="underline">开始下一集 →</Link>
        </div>
      ) : (
        <SceneTimeline episodeId={ep.id} scenes={data.scenes} />
      )}
    </div>
  );
}
```

### Step 5.6: 重写 `Layout.tsx`

- [ ] **覆盖** `frontend/src/components/Layout.tsx` 内容为：

```typescript
import { NavLink, Outlet } from "react-router-dom";

import SpeakerPicker from "./SpeakerPicker";

const MAIN_NAV = [
  { to: "/", label: "今天", end: true, icon: "🔥" },
  { to: "/series", label: "我的番剧库", icon: "📺" },
];

const SECONDARY_NAV = [
  { to: "/grammar", label: "语法", icon: "📚" },
  { to: "/progress", label: "进度", icon: "📈" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <nav className="bg-white/85 backdrop-blur border-b border-ink-200/70 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
          <span className="font-bold text-brand-700 mr-3">追番日语</span>
          {MAIN_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `nav-link ${isActive ? "nav-link-active" : ""}`
              }
            >
              <span className="mr-1 opacity-80">{n.icon}</span>{n.label}
            </NavLink>
          ))}
          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1 text-xs">
              {SECONDARY_NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    `text-ink-400 hover:text-brand-600 transition-colors px-1.5 py-1 ${
                      isActive ? "text-brand-600 font-medium" : ""
                    }`
                  }
                >
                  <span className="mr-0.5 opacity-70">{n.icon}</span>{n.label}
                </NavLink>
              ))}
            </div>
            <SpeakerPicker />
          </div>
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
```

### Step 5.7: `Series.tsx` 加角色头像 + "重新匹配"

- [ ] **修改** `frontend/src/pages/Series.tsx`，把现有 `import { ... }` 行替换为：

```typescript
import { createSeries, generateDemoEpisode, importEpisodeFile, listSeries,
         refreshAnilist, setCurrentSeries } from "../lib/api";
```

- [ ] **修改** `frontend/src/pages/Series.tsx`，把渲染列表的 `data.map((s) => (...))` 替换为：

```typescript
        {data.map((s) => (
          <div key={s.id} className="card-padded card-hover">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <SeriesAvatar series={s} />
                <div className="font-semibold text-ink-800 flex items-center gap-2 truncate">
                  {s.title}
                  {s.is_current && <span className="badge-sakura">当前</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {s.anilist_status === "not_found" || s.anilist_status === "failed" ? (
                  <RefreshAnilistButton seriesId={s.id} />
                ) : null}
                {!s.is_current && (
                  <button
                    onClick={() => setCurrent.mutate(s.id)}
                    className="btn-ghost btn-sm"
                  >设为当前</button>
                )}
              </div>
            </div>
            <ImportEpisode seriesId={s.id} />
          </div>
        ))}
```

并在文件末尾追加：

```typescript
function SeriesAvatar({ series }: { series: import("../types").Series }) {
  const chars = series.characters ?? [];
  const main = chars.find((c) => c.image_url) ?? chars[0];
  const initial = main?.name_jp?.[0] ?? main?.name_en?.[0] ?? series.title[0] ?? "?";
  if (main?.image_url) {
    return (
      <img
        src={main.image_url}
        alt={main.name_jp ?? main.name_en ?? series.title}
        className="w-10 h-10 rounded-full object-cover border border-ink-200 shrink-0"
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
      />
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-sakura-100 text-sakura-700 font-bold ja flex items-center justify-center shrink-0">
      {initial}
    </div>
  );
}

function RefreshAnilistButton({ seriesId }: { seriesId: number }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => refreshAnilist(seriesId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["series"] }),
  });
  return (
    <button
      onClick={() => m.mutate()}
      className="btn-ghost btn-sm"
      disabled={m.isPending}
      title="重新尝试 AniList 角色匹配"
    >{m.isPending ? "匹配中…" : "重新匹配"}</button>
  );
}
```

### Step 5.8: `Reading.tsx` 加 `?scene=N` 滚动 + 回看 banner

- [ ] **修改** `frontend/src/pages/Reading.tsx`，把 `import { useParams }` 行改为：

```typescript
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
```

并把 `import { getEpisode, getLines, setReadingProgress } from "../lib/api";` 改为：

```typescript
import { getEpisode, getLines, getScenes, setReadingProgress } from "../lib/api";
```

- [ ] **修改** `frontend/src/pages/Reading.tsx`，在 `useQuery({ queryKey: ["lines", epId] ... })` 之后增加：

```typescript
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sceneIdx = params.get("scene") !== null ? Number(params.get("scene")) : null;
  const { data: scenes } = useQuery({
    queryKey: ["scenes", epId],
    queryFn: () => getScenes(epId),
    enabled: !!ep,
  });
```

- [ ] **修改** `frontend/src/pages/Reading.tsx`，在 `useEffect`（J/K 键盘那个）之后追加新 useEffect：

```typescript
  // 进入时若指定 ?scene=N 且场景元素存在，滚到该场首行
  useEffect(() => {
    if (sceneIdx === null || !scenes || !lines) return;
    const sc = scenes.find((s) => s.idx === sceneIdx);
    if (!sc || sc.state === "locked" || sc.start_line_idx === null) return;
    setFocused(sc.start_line_idx);
    requestAnimationFrame(() => {
      const ul = listRef.current;
      const el = ul?.children?.[sc.start_line_idx!];
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [sceneIdx, scenes, lines]);
```

- [ ] **修改** `frontend/src/pages/Reading.tsx`，在返回 JSX 的根 `<div className="space-y-5">` 内、`<header ...>` 之前插入回看 banner：

```typescript
      {sceneIdx !== null && scenes && ep && (() => {
        const sc = scenes.find((s) => s.idx === sceneIdx);
        if (!sc || sc.state !== "done" || sc.end_line_idx === null) return null;
        const cur = scenes.find((s) => s.state === "current");
        const curIdx = cur?.idx ?? -1;
        return (
          <div className="card-padded bg-amber-50 border-amber-200 text-amber-800 text-sm flex items-center justify-between gap-3 py-2">
            <span>
              你在回看场景 {sc.idx + 1} · 当前进度在场景 {curIdx + 1}
            </span>
            <button
              className="btn-ghost btn-sm text-amber-700"
              onClick={() => {
                if (!cur || cur.start_line_idx === null) return;
                navigate(`/episodes/${epId}/reading?scene=${cur.idx}`, { replace: true });
              }}
            >回到当前 →</button>
          </div>
        );
      })()}
```

### Step 5.9: 删后端旧 `study.today`

- [ ] **修改** `backend/app/api/study.py`，删掉 `@router.get("/today")` 装饰器及其 `today(...)` 函数体（约第 14–27 行）。`from datetime import date` 仍被其它 endpoint 用着，保留。

- [ ] **修改** `backend/tests/test_api_study.py`，删除任何 `client.get("/api/study/today")` 相关用例（保留 SRS / reading-progress / complete-today 的测试）。

### Step 5.10: 前端构建

Run: `cd frontend && npm run build`
Expected: TypeScript 编译通过；Vite 产出 `dist/`。

### Step 5.11: 跑全部 backend 测试

Run: `cd backend && uv run pytest -q`
Expected: 全绿。

### Step 5.12: 手动验证清单（写进 commit message）

按 spec §8.3 逐项手动验证。前置：

```bash
# 后端
cd backend && uv run uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd frontend && npm run dev
```

清单（spec §8.3 逐项核对）：

- [ ] 全新 SQLite 启动、`POST /api/series` 一部主流番（"Bocchi the Rock"），观察 Today 文字 fallback → 30s 内变真头像
- [ ] 导入或 generate-demo 一集字幕，加工中显示骨架 + "正在加工…"
- [ ] 加工完，Timeline 出 5–8 场景；当前场展开 + preview + 大按钮
- [ ] 点"继续读这一场"→ Reading 滚到本场；中途 `setReadingProgress` 后回首页，时间线还在同一场
- [ ] 点已读场景重读 → URL 带 `?scene=N`；顶部出现"回看"banner；点"回到当前"返回当前场
- [ ] 锁定场景灰色不可点
- [ ] 输一个假番名 → `anilist_status=not_found`；Series 列表行显示"重新匹配"按钮
- [ ] 加工失败（手动改 episode.status='failed' 或 mock）→ Today 出 banner
- [ ] 5 tab 完全消失 → 主导航只剩"今天 / 我的番剧库"；右上角小字"语法 / 进度"；`/review` 直接访问仍可用

### Step 5.13: 提交

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add frontend/ backend/app/api/study.py backend/tests/test_api_study.py
git commit -m "feat(web): scene timeline home, 2-tab nav, AniList header

- new Today page: CharacterHeader (AniList avatar w/ text fallback) +
  SceneTimeline (done/current/locked three-state list)
- Layout cut from 5 tabs to 2 main tabs + secondary links;
  /review accessible only via the due-chip on Today
- Series page shows character avatars and 'refresh anilist' for
  not_found / failed
- Reading honors ?scene=N: scrolls to scene start and shows a
  re-read banner when navigating past scenes
- removes the obsolete GET /api/study/today endpoint

Manual verification checklist (spec §8.3) passed on Chrome.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review Notes

- 所有 spec §2.1 包含项（9 条）均有对应 task 步骤覆盖。
- 所有 spec §8.1 测试文件均在 plan 中创建或修改。
- spec §8.3 手动清单整体收纳为 Step 5.12。
- spec §7 边界场景：Today 页 4 种空/错状态（无番、无集、failed、读完）均在 Step 5.5 实现。
- 文件路径与 spec §3、§4、§5 一一对应，无歧义。
