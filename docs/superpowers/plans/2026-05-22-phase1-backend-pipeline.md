# 追番日语 Phase 1 · Plan 1：后端地基与内容流水线 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭好后端工程骨架，实现把一集动漫（字幕）导入并自动加工（分词注音 + LLM 翻译/语法/语体）落库的完整内容流水线。

**Architecture:** FastAPI + SQLAlchemy 2.0 + SQLite 的 Python 后端。服务层按职责拆分：字幕解析、Jimaku 客户端、SudachiPy 分词、LLM 调用、流水线编排各一个模块。服务函数显式接收 `Session` 参数（依赖注入），便于用内存 SQLite 单测。一条 CLI 命令串起"导入 → 加工"全链路用于验收。

**Tech Stack:** Python ≥3.11、FastAPI、SQLAlchemy 2.0、SQLite、anthropic SDK（指向 fox 网关）、httpx、SudachiPy + sudachidict-core、pytest。

参考规格：`docs/superpowers/specs/2026-05-22-anime-japanese-phase1-design.md`。
参考既有项目（同技术栈）：`~/Desktop/work/ai/trading`。

---

## 文件结构

本计划创建/涉及的文件：

```
backend/
  pyproject.toml              # 依赖与工具配置
  app/
    __init__.py
    config.py                 # pydantic-settings，读 .env
    db.py                     # SQLAlchemy engine/session/Base
    models/
      __init__.py             # 汇总导出全部模型
      content.py              # Series / Episode / Line
      study.py                # Vocab / GrammarPoint / DailySession / AppSetting
    services/
      subtitles.py            # .srt/.ass 解析 → ParsedLine 列表
      jimaku.py               # Jimaku API 客户端
      tokenizer.py            # SudachiPy 分词 + 注音
      llm.py                  # Anthropic 客户端封装 + JSON 调用
      pipeline.py             # 加工流水线编排
    data/
      grammar_seed.json       # 内置 N2/N1 语法清单种子
    grammar_loader.py         # 把 grammar_seed.json 写入数据库
    cli.py                    # import-episode / process-episode 命令
  tests/
    __init__.py
    conftest.py               # pytest 夹具：内存数据库 session
    fixtures/
      sample.srt
      sample.ass
    test_smoke.py
    test_config.py
    test_db.py
    test_models.py
    test_grammar_loader.py
    test_subtitles.py
    test_jimaku.py
    test_tokenizer.py
    test_llm.py
    test_pipeline.py
    test_cli_integration.py
Makefile                      # 仓库根：setup/dev/test/lint
.env.example                  # 仓库根
README.md                     # 仓库根
```

每个服务模块单一职责；模型按"内容/学习"两域分文件。

---

## Task 1: 后端工程骨架

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_smoke.py`
- Create: `Makefile`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: 写工程文件**

`backend/pyproject.toml`:

```toml
[project]
name = "anime-nihongo-backend"
version = "0.1.0"
description = "追番日语 - 后端"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "anthropic>=0.40.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "sudachipy>=0.6.8",
    "sudachidict-core>=20240409",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

`backend/app/__init__.py`: 空文件。
`backend/tests/__init__.py`: 空文件。

`backend/tests/test_smoke.py`:

```python
def test_app_package_imports():
    import app  # noqa: F401
```

`Makefile`（仓库根）:

```makefile
.PHONY: setup dev test lint

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check app tests
```

`.env.example`（仓库根）:

```
# AI 网关（fox）—— Anthropic 原生协议
ANTHROPIC_API_KEY=your_key
ANTHROPIC_BASE_URL=https://code.newcli.com/claude/aws
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MODEL_LIGHT=claude-haiku-4-5-20251001

# Jimaku 字幕 API
JIMAKU_API_TOKEN=your_token

# 数据库
DATABASE_URL=sqlite:///./data/anime-nihongo.db
```

`README.md`（仓库根）:

```markdown
# 追番日语

把你在追的动漫变成全方位日语训练的本地学习应用。设计见 `docs/superpowers/specs/`。

## 快速开始

1. `cp .env.example .env` 并填入 fox 网关 key 与 Jimaku token
2. `make setup` 安装后端依赖
3. `make test` 运行测试

**浏览器要求**：语音功能需用 Chrome 或 Edge。
```

- [ ] **Step 2: 安装依赖并跑冒烟测试**

Run: `make setup && make test`
Expected: 依赖安装成功，`test_app_package_imports` PASS。

- [ ] **Step 3: 提交**

```bash
git add backend Makefile .env.example README.md
git commit -m "chore: 后端工程骨架与依赖"
```

---

## Task 2: 配置模块 config.py

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_config.py`:

```python
from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.anthropic_model == "claude-sonnet-4-6"
    assert s.database_url.startswith("sqlite")


def test_validate_ai_false_when_unset():
    s = Settings(_env_file=None, anthropic_api_key="")
    assert s.validate_ai() is False


def test_validate_ai_true_when_set():
    s = Settings(_env_file=None, anthropic_api_key="real-key")
    assert s.validate_ai() is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.config'`。

- [ ] **Step 3: 写实现**

`backend/app/config.py`:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # fox 网关 / Anthropic 原生协议
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_model_light: str = "claude-haiku-4-5-20251001"

    # Jimaku
    jimaku_api_token: str = ""

    # 数据库
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'anime-nihongo.db'}"

    def validate_ai(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key != "your_key")


settings = Settings()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: 3 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: 配置模块"
```

---

## Task 3: 数据库基础设施 db.py

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_db.py`:

```python
from sqlalchemy import inspect

from app.db import Base, init_db, make_engine, make_session_factory


def test_make_engine_and_session():
    engine = make_engine("sqlite://")
    SessionFactory = make_session_factory(engine)
    init_db(engine)
    with SessionFactory() as session:
        assert session.is_active


def test_init_db_is_idempotent():
    engine = make_engine("sqlite://")
    init_db(engine)
    init_db(engine)  # 第二次不应报错
    assert inspect(engine) is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_db.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.db'`。

- [ ] **Step 3: 写实现**

`backend/app/db.py`:

```python
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """建表。导入 models 以注册到 Base.metadata。"""
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_db.py -v`
Expected: 2 个测试 PASS（依赖 Task 4 的 `app.models`；若此刻 `app.models` 不存在，先建空的 `backend/app/models/__init__.py` 再跑）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: 数据库基础设施"
```

---

## Task 4: ORM 数据模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/content.py`
- Create: `backend/app/models/study.py`
- Test: `backend/tests/test_models.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 写 conftest 夹具**

`backend/tests/conftest.py`:

```python
import pytest

from app.db import init_db, make_engine, make_session_factory


@pytest.fixture
def db_session():
    engine = make_engine("sqlite://")
    init_db(engine)
    SessionFactory = make_session_factory(engine)
    session = SessionFactory()
    yield session
    session.close()
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_models.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Episode, GrammarPoint, Line, Series, Vocab


def test_series_episode_line_chain(db_session):
    series = Series(title="测试番", title_jp="テスト")
    episode = Episode(series=series, number=1, source="upload", status="processing")
    line = Line(episode=episode, idx=0, text_jp="これはテストだ", processed=False)
    db_session.add(series)
    db_session.commit()
    assert line.id is not None
    assert episode.series.title == "测试番"
    assert series.episodes[0].lines[0].text_jp == "これはテストだ"


def test_vocab_unique_headword_reading(db_session):
    db_session.add(Vocab(headword="本", reading="ほん", meaning_zh="书"))
    db_session.commit()
    db_session.add(Vocab(headword="本", reading="ほん", meaning_zh="重复"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_grammar_point_defaults(db_session):
    gp = GrammarPoint(key="ni-atatte", name="〜にあたって", jlpt_level="N2",
                      explanation="在…之际", curated=True)
    db_session.add(gp)
    db_session.commit()
    assert gp.status == "locked"
    assert gp.in_srs is False
    assert gp.ease == 2.5
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_models.py -v`
Expected: FAIL，`ImportError: cannot import name 'Episode' from 'app.models'`。

- [ ] **Step 4: 写实现**

`backend/app/models/content.py`:

```python
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    title_jp: Mapped[str | None]
    jimaku_entry_id: Mapped[int | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Episode(Base):
    __tablename__ = "episode"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.id"))
    number: Mapped[int]
    title: Mapped[str | None]
    source: Mapped[str]  # jimaku / upload
    status: Mapped[str] = mapped_column(default="importing")  # importing/processing/ready/failed
    processed_lines: Mapped[int] = mapped_column(default=0)
    total_lines: Mapped[int] = mapped_column(default=0)
    read_position: Mapped[int] = mapped_column(default=0)
    reading_done: Mapped[bool] = mapped_column(default=False)
    imported_at: Mapped[datetime] = mapped_column(server_default=func.now())

    series: Mapped["Series"] = relationship(back_populates="episodes")
    lines: Mapped[list["Line"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", order_by="Line.idx"
    )


class Line(Base):
    __tablename__ = "line"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    speaker: Mapped[str | None]
    text_jp: Mapped[str]
    furigana: Mapped[list | None] = mapped_column(JSON, default=None)
    translation_zh: Mapped[str | None]
    grammar_notes: Mapped[list | None] = mapped_column(JSON, default=None)
    register_tag: Mapped[str | None]
    grammar_point_keys: Mapped[list | None] = mapped_column(JSON, default=None)
    processed: Mapped[bool] = mapped_column(default=False)

    episode: Mapped["Episode"] = relationship(back_populates="lines")
```

`backend/app/models/study.py`:

```python
from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Vocab(Base):
    __tablename__ = "vocab"
    __table_args__ = (UniqueConstraint("headword", "reading", name="uq_vocab_word"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    headword: Mapped[str]
    reading: Mapped[str]
    meaning_zh: Mapped[str]
    pos: Mapped[str | None]
    jlpt_level: Mapped[str | None]
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("line.id"))
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[date | None]
    last_reviewed: Mapped[datetime | None]


class GrammarPoint(Base):
    __tablename__ = "grammar_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    jlpt_level: Mapped[str]
    explanation: Mapped[str]
    curated: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="locked")  # locked/seen/learning
    quiz_cache: Mapped[list | None] = mapped_column(JSON, default=None)
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("line.id"))
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[date | None]
    last_reviewed: Mapped[datetime | None]


class DailySession(Base):
    __tablename__ = "daily_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(unique=True)
    completed: Mapped[bool] = mapped_column(default=False)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episode.id"))
    vocab_reviewed: Mapped[int] = mapped_column(default=0)
    grammar_reviewed: Mapped[int] = mapped_column(default=0)
    lines_read: Mapped[int] = mapped_column(default=0)
    conversation_turns: Mapped[int] = mapped_column(default=0)
    summary: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
```

`backend/app/models/__init__.py`:

```python
from app.models.content import Episode, Line, Series
from app.models.study import AppSetting, DailySession, GrammarPoint, Vocab

__all__ = [
    "Series", "Episode", "Line",
    "Vocab", "GrammarPoint", "DailySession", "AppSetting",
]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_models.py tests/test_db.py -v`
Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models backend/tests/test_models.py backend/tests/conftest.py
git commit -m "feat: ORM 数据模型"
```

---

## Task 5: N2/N1 语法清单种子与加载器

**Files:**
- Create: `backend/app/data/grammar_seed.json`
- Create: `backend/app/grammar_loader.py`
- Test: `backend/tests/test_grammar_loader.py`

- [ ] **Step 1: 写种子数据文件**

`backend/app/data/grammar_seed.json` —— 数组，每条字段 `key`（kebab-case 稳定标识）、`name`、`jlpt_level`、`explanation`。先写入以下 20 条真实条目：

```json
[
  {"key": "ni-atatte", "name": "〜にあたって", "jlpt_level": "N2", "explanation": "在…之际、面临…的时候（郑重）"},
  {"key": "ni-oite", "name": "〜において", "jlpt_level": "N2", "explanation": "在…方面、在…场合"},
  {"key": "wo-hajime", "name": "〜をはじめ", "jlpt_level": "N2", "explanation": "以…为首、…等等"},
  {"key": "tsutsu-aru", "name": "〜つつある", "jlpt_level": "N2", "explanation": "正在逐渐…"},
  {"key": "kano-you-da", "name": "〜かのようだ", "jlpt_level": "N2", "explanation": "仿佛、好像…一样"},
  {"key": "bakari-ka", "name": "〜ばかりか", "jlpt_level": "N2", "explanation": "不仅…而且…"},
  {"key": "dokoro-ka", "name": "〜どころか", "jlpt_level": "N2", "explanation": "别说…、岂止…反而…"},
  {"key": "nimo-kakawarazu", "name": "〜にもかかわらず", "jlpt_level": "N2", "explanation": "尽管…却…"},
  {"key": "koto-naku", "name": "〜ことなく", "jlpt_level": "N2", "explanation": "不…（地）、未曾…"},
  {"key": "nuki-de", "name": "〜ぬきで", "jlpt_level": "N2", "explanation": "去掉…、省去…"},
  {"key": "yara-yara", "name": "〜やら〜やら", "jlpt_level": "N2", "explanation": "又…又…（列举，含麻烦语气）"},
  {"key": "age-suffix", "name": "〜げ", "jlpt_level": "N2", "explanation": "显得…的样子"},
  {"key": "ageku", "name": "〜あげく", "jlpt_level": "N2", "explanation": "…的结果（多为不好结局）"},
  {"key": "sue-ni", "name": "〜末に", "jlpt_level": "N2", "explanation": "经过…最终…"},
  {"key": "shidai", "name": "〜次第", "jlpt_level": "N2", "explanation": "一…就立刻…；取决于…"},
  {"key": "ue-de", "name": "〜上で", "jlpt_level": "N2", "explanation": "在…之后再…；在…方面"},
  {"key": "uru-eru", "name": "〜得る", "jlpt_level": "N2", "explanation": "可能…、能够…"},
  {"key": "kanenai", "name": "〜かねない", "jlpt_level": "N2", "explanation": "有可能…（不好的事）"},
  {"key": "zaru-wo-enai", "name": "〜ざるを得ない", "jlpt_level": "N2", "explanation": "不得不…"},
  {"key": "mai", "name": "〜まい", "jlpt_level": "N2", "explanation": "不会…吧、绝不…"}
]
```

随后**继续补全至少到 150 条**，覆盖标准 N2 语法大纲，并加入约 30 条高频 N1 语法点（`jlpt_level` 标 `N1`）。每条严格遵循上述四字段 schema，`key` 全局唯一、kebab-case。这是标准化的公开日语语法大纲，按大纲逐条录入即可。

- [ ] **Step 2: 写失败测试**

`backend/tests/test_grammar_loader.py`:

```python
from app.grammar_loader import load_grammar_seed
from app.models import GrammarPoint


def test_loads_seed(db_session):
    n = load_grammar_seed(db_session)
    assert n >= 150
    gp = db_session.query(GrammarPoint).filter_by(key="ni-atatte").one()
    assert gp.name == "〜にあたって"
    assert gp.curated is True
    assert gp.status == "locked"


def test_loader_is_idempotent(db_session):
    load_grammar_seed(db_session)
    first = db_session.query(GrammarPoint).count()
    load_grammar_seed(db_session)
    assert db_session.query(GrammarPoint).count() == first
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_grammar_loader.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.grammar_loader'`。

- [ ] **Step 4: 写实现**

`backend/app/grammar_loader.py`:

```python
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import GrammarPoint

SEED_PATH = Path(__file__).parent / "data" / "grammar_seed.json"


def load_grammar_seed(session: Session) -> int:
    """把 grammar_seed.json 写入数据库（按 key 幂等）。返回种子总条数。"""
    entries = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    existing = {k for (k,) in session.query(GrammarPoint.key).all()}
    for e in entries:
        if e["key"] in existing:
            continue
        session.add(GrammarPoint(
            key=e["key"], name=e["name"], jlpt_level=e["jlpt_level"],
            explanation=e["explanation"], curated=True, status="locked",
        ))
    session.commit()
    return len(entries)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_grammar_loader.py -v`
Expected: 2 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/data backend/app/grammar_loader.py backend/tests/test_grammar_loader.py
git commit -m "feat: N2/N1 语法清单种子与加载器"
```

---

## Task 6: 字幕解析 subtitles.py

**Files:**
- Create: `backend/app/services/__init__.py`（空文件）
- Create: `backend/app/services/subtitles.py`
- Create: `backend/tests/fixtures/sample.srt`
- Create: `backend/tests/fixtures/sample.ass`
- Test: `backend/tests/test_subtitles.py`

- [ ] **Step 1: 写测试夹具文件**

`backend/tests/fixtures/sample.srt`:

```
1
00:00:01,000 --> 00:00:04,000
おはよう、元気？

2
00:00:05,500 --> 00:00:08,000
うん、まあまあかな。
今日はいい天気だね。
```

`backend/tests/fixtures/sample.ass`:

```
[Script Info]
Title: sample

[V4+ Styles]
Format: Name, Fontname
Style: Default,Arial

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,アキラ,0,0,0,,{\i1}おはよう{\i0}、元気？
Dialogue: 0,0:00:05.50,0:00:08.00,Default,,0,0,0,,うん、\Nまあまあ。
```

- [ ] **Step 2: 写失败测试**

`backend/tests/test_subtitles.py`:

```python
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
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_subtitles.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.subtitles'`。

- [ ] **Step 4: 写实现**

`backend/app/services/subtitles.py`:

```python
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
    text = text.replace("\\N", " ").replace("\\n", " ").replace("\n", " ")
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
        start, end = rows[1].split("-->")
        text = _clean(" ".join(rows[2:]))
        if not text:
            continue
        out.append(ParsedLine(len(out), _srt_time_to_ms(start), _srt_time_to_ms(end),
                              None, text))
    return out


def _parse_ass(content: str) -> list[ParsedLine]:
    out: list[ParsedLine] = []
    fmt: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if line.lower().startswith("format:") and not fmt:
            fmt = [c.strip().lower() for c in line.split(":", 1)[1].split(",")]
        elif line.startswith("Dialogue:") and fmt:
            parts = line.split(":", 1)[1].split(",", len(fmt) - 1)
            row = dict(zip(fmt, parts))
            text = _clean(row.get("text", ""))
            if not text:
                continue
            speaker = (row.get("name") or "").strip() or None
            out.append(ParsedLine(
                len(out), _ass_time_to_ms(row.get("start", "0:0:0.0")),
                _ass_time_to_ms(row.get("end", "0:0:0.0")), speaker, text))
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
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_subtitles.py -v`
Expected: 3 个测试 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services backend/tests/test_subtitles.py backend/tests/fixtures
git commit -m "feat: 字幕解析（.srt/.ass）"
```

---

## Task 7: Jimaku API 客户端 jimaku.py

**Files:**
- Create: `backend/app/services/jimaku.py`
- Test: `backend/tests/test_jimaku.py`

> 注：端点与字段以 [jimaku.cc/api/docs](https://jimaku.cc/api/docs) 为准，实现时核对；本任务按已知 API 形态实现，鉴权为 `Authorization` 头携带 token。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_jimaku.py`:

```python
import httpx
import pytest

from app.services.jimaku import JimakuClient, JimakuError


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="https://jimaku.cc/api")
    return JimakuClient(token="t", http=http)


def test_search_entries():
    def handler(request):
        assert request.url.path == "/api/entries/search"
        assert request.headers["Authorization"] == "t"
        return httpx.Response(200, json=[{"id": 9, "name": "Test Anime"}])

    entries = _client(handler).search_entries("test")
    assert entries[0]["id"] == 9


def test_list_files():
    def handler(request):
        assert request.url.path == "/api/entries/9/files"
        return httpx.Response(200, json=[{"name": "ep1.srt", "url": "https://x/ep1.srt"}])

    files = _client(handler).list_files(9)
    assert files[0]["name"] == "ep1.srt"


def test_download_file():
    def handler(request):
        if request.url.host == "x":
            return httpx.Response(200, text="1\n00:00:01,000 --> 00:00:02,000\nやあ\n")
        return httpx.Response(404)

    content = _client(handler).download_file("https://x/ep1.srt")
    assert "やあ" in content


def test_error_on_non_200():
    def handler(request):
        return httpx.Response(500, text="boom")

    with pytest.raises(JimakuError):
        _client(handler).search_entries("test")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_jimaku.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.jimaku'`。

- [ ] **Step 3: 写实现**

`backend/app/services/jimaku.py`:

```python
import httpx

API_BASE = "https://jimaku.cc/api"


class JimakuError(RuntimeError):
    pass


class JimakuClient:
    """Jimaku 字幕 API 客户端。鉴权：Authorization 头携带 API token。"""

    def __init__(self, token: str, http: httpx.Client | None = None):
        self._token = token
        self._http = http or httpx.Client(base_url=API_BASE, timeout=30.0)

    def _get(self, path: str, **kwargs):
        resp = self._http.get(path, headers={"Authorization": self._token}, **kwargs)
        if resp.status_code != 200:
            raise JimakuError(f"Jimaku {path} 返回 {resp.status_code}: {resp.text[:200]}")
        return resp

    def search_entries(self, query: str) -> list[dict]:
        return self._get("/api/entries/search", params={"query": query}).json()

    def list_files(self, entry_id: int) -> list[dict]:
        return self._get(f"/api/entries/{entry_id}/files").json()

    def download_file(self, url: str) -> str:
        resp = self._http.get(url, headers={"Authorization": self._token})
        if resp.status_code != 200:
            raise JimakuError(f"下载字幕失败 {resp.status_code}: {url}")
        return resp.text
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_jimaku.py -v`
Expected: 4 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/jimaku.py backend/tests/test_jimaku.py
git commit -m "feat: Jimaku API 客户端"
```

---

## Task 8: 分词与注音 tokenizer.py

**Files:**
- Create: `backend/app/services/tokenizer.py`
- Test: `backend/tests/test_tokenizer.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_tokenizer.py`:

```python
from app.services.tokenizer import extract_vocab_candidates, to_furigana


def test_furigana_attaches_reading_to_kanji():
    segs = to_furigana("今日は学校に行く")
    # 含汉字的段带读音 r；纯假名段不带
    kanji_segs = [s for s in segs if "r" in s]
    assert any(s["t"] == "今日" for s in kanji_segs)
    joined = "".join(s["t"] for s in segs)
    assert joined == "今日は学校に行く"
    for s in kanji_segs:
        assert all("぀" <= c <= "ゟ" for c in s["r"])  # 读音为平假名


def test_furigana_pure_kana_has_no_reading():
    segs = to_furigana("おはよう")
    assert all("r" not in s for s in segs)


def test_extract_vocab_candidates_returns_dictionary_forms():
    cands = extract_vocab_candidates("猫が走った")
    forms = {c["headword"] for c in cands}
    assert "猫" in forms
    assert "走る" in forms          # 辞书形
    assert all("reading" in c and "pos" in c for c in cands)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_tokenizer.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.tokenizer'`。

- [ ] **Step 3: 写实现**

`backend/app/services/tokenizer.py`:

```python
from functools import lru_cache

from sudachipy import Dictionary, SplitMode

# 用于挑候选词的实义词性
_CONTENT_POS = {"名詞", "動詞", "形容詞", "副詞"}
# 太基础、不值得进复习的词性细类（助动词性名词等）可后续扩充
_STOP_FORMS = {"する", "ある", "いる", "なる", "これ", "それ", "あれ", "こと", "もの"}


@lru_cache(maxsize=1)
def _tokenizer():
    return Dictionary().create()


def _kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _has_kanji(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def to_furigana(text: str) -> list[dict]:
    """把文本切成段：含汉字的段为 {"t": 表层, "r": 平假名读音}，纯假名为 {"t": 表层}。"""
    segs: list[dict] = []
    for m in _tokenizer().tokenize(text, SplitMode.C):
        surface = m.surface()
        if _has_kanji(surface):
            segs.append({"t": surface, "r": _kata_to_hira(m.reading_form())})
        else:
            segs.append({"t": surface})
    return segs


def extract_vocab_candidates(text: str) -> list[dict]:
    """抽取实义词候选：辞书形、读音、词性。同一辞书形去重。"""
    seen: dict[str, dict] = {}
    for m in _tokenizer().tokenize(text, SplitMode.C):
        pos = m.part_of_speech()[0]
        if pos not in _CONTENT_POS:
            continue
        form = m.dictionary_form()
        if form in _STOP_FORMS or len(form) < 1:
            continue
        if form not in seen:
            seen[form] = {
                "headword": form,
                "reading": _kata_to_hira(m.reading_form()),
                "pos": pos,
            }
    return list(seen.values())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_tokenizer.py -v`
Expected: 3 个测试 PASS（首次运行会加载 sudachidict）。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/tokenizer.py backend/tests/test_tokenizer.py
git commit -m "feat: SudachiPy 分词与注音"
```

---

## Task 9: LLM 服务 llm.py

**Files:**
- Create: `backend/app/services/llm.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_llm.py`:

```python
import pytest

from app.services import llm
from app.services.llm import LLMError, extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_in_code_fence():
    text = 'ここ:\n```json\n{"a": [1, 2]}\n```\n以上'
    assert extract_json(text) == {"a": [1, 2]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(LLMError):
        extract_json("no json here")


def test_call_json_uses_client(monkeypatch):
    class FakeBlock:
        text = '{"ok": true}'

    class FakeResp:
        content = [FakeBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            assert kwargs["model"] == "test-model"
            assert kwargs["system"] == "sys"
            return FakeResp()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(llm, "_client", lambda: FakeClient())
    out = llm.call_json(system="sys", user="hi", model="test-model")
    assert out == {"ok": True}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.llm'`。

- [ ] **Step 3: 写实现**

`backend/app/services/llm.py`:

```python
import json
import re
from functools import lru_cache

from anthropic import Anthropic

from app.config import settings

_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client() -> Anthropic:
    return Anthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url or None,
        max_retries=5,  # 扛 fox 网关突发限流
    )


def extract_json(text: str) -> dict:
    """从模型输出里抽出 JSON 对象：优先代码围栏，其次首个 {...}。"""
    candidates = []
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    obj = _OBJ_RE.search(text)
    if obj:
        candidates.append(obj.group(0))
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise LLMError(f"无法从模型输出解析 JSON: {text[:200]}")


def call_json(system: str, user: str, model: str | None = None,
              max_tokens: int = 4000) -> dict:
    """调用 Claude，要求返回 JSON 对象并解析。失败抛 LLMError。"""
    try:
        resp = _client().messages.create(
            model=model or settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"LLM 调用失败: {exc}") from exc
    text = "".join(getattr(b, "text", "") for b in resp.content)
    return extract_json(text)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_llm.py -v`
Expected: 4 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/llm.py backend/tests/test_llm.py
git commit -m "feat: LLM 服务（fox 网关 + JSON 调用）"
```

---

## Task 10: 加工流水线 pipeline.py

**Files:**
- Create: `backend/app/services/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

流水线对一个 `Episode` 的未加工 `Line` 分批处理：本地分词出注音、LLM 批量产出翻译/语法/语体/语法点匹配，落库并更新 `Episode`、`Vocab`、`GrammarPoint`。可断点续跑（按 `Line.processed`）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_pipeline.py`:

```python
from app.grammar_loader import load_grammar_seed
from app.models import Episode, GrammarPoint, Line, Series, Vocab
from app.services import pipeline


def _episode_with_lines(db_session, texts):
    series = Series(title="番")
    ep = Episode(series=series, number=1, source="upload", status="processing",
                 total_lines=len(texts))
    for i, t in enumerate(texts):
        ep.lines.append(Line(idx=i, text_jp=t, processed=False))
    db_session.add(series)
    db_session.commit()
    return ep


def _fake_llm(system, user, model=None, max_tokens=4000):
    # 按 user 里给出的行 idx 回填注释；测试不关心真实语义
    import json
    payload = json.loads(user)
    return {
        "lines": [
            {"idx": ln["idx"], "translation_zh": "译:" + ln["text"],
             "grammar_notes": [{"point": "〜にあたって", "explain": "示例"}],
             "register_tag": "casual",
             "grammar_point_keys": ["ni-atatte"]}
            for ln in payload["lines"]
        ],
        "vocab": [{"headword": "猫", "reading": "ねこ", "meaning_zh": "猫",
                   "pos": "名詞", "jlpt_level": "N5"}],
    }


def test_process_episode_annotates_lines(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る", "今日はいい天気だ"])

    pipeline.process_episode(db_session, ep.id, batch_size=10)

    db_session.refresh(ep)
    assert ep.status == "ready"
    assert ep.processed_lines == 2
    lines = db_session.query(Line).filter_by(episode_id=ep.id).all()
    assert all(ln.processed for ln in lines)
    assert all(ln.translation_zh and ln.furigana for ln in lines)
    assert all(ln.grammar_point_keys == ["ni-atatte"] for ln in lines)


def test_process_episode_creates_vocab_and_flips_grammar(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る"])

    pipeline.process_episode(db_session, ep.id, batch_size=10)

    assert db_session.query(Vocab).filter_by(headword="猫").count() == 1
    gp = db_session.query(GrammarPoint).filter_by(key="ni-atatte").one()
    assert gp.status == "seen"
    assert gp.source_line_id is not None


def test_process_episode_is_resumable(db_session, monkeypatch):
    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)
    ep = _episode_with_lines(db_session, ["猫が走る", "犬が寝る"])
    # 预先把第 0 行标记为已加工
    ep.lines[0].processed = True
    ep.processed_lines = 1
    db_session.commit()

    calls = []
    orig = _fake_llm

    def counting_llm(system, user, model=None, max_tokens=4000):
        import json
        calls.append(len(json.loads(user)["lines"]))
        return orig(system, user, model, max_tokens)

    monkeypatch.setattr(pipeline.llm, "call_json", counting_llm)
    pipeline.process_episode(db_session, ep.id, batch_size=10)
    # 只应处理剩下的 1 行
    assert calls == [1]
    assert ep.status == "ready"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.pipeline'`。

- [ ] **Step 3: 写实现**

`backend/app/services/pipeline.py`:

```python
import json

from sqlalchemy.orm import Session

from app.models import Episode, GrammarPoint, Line, Vocab
from app.services import llm
from app.services.tokenizer import extract_vocab_candidates, to_furigana

_SYSTEM = """你是日语教学助手。给定动漫台词，逐句产出面向中文母语 N2 学习者的标注。
只返回 JSON 对象，不要多余文字。结构：
{
  "lines": [
    {"idx": 整数, "translation_zh": "中文翻译",
     "grammar_notes": [{"point": "语法点名", "explain": "中文讲解"}],
     "register_tag": "polite|casual|rough|feminine|dialect|archaic 之一",
     "grammar_point_keys": ["命中下方语法清单的 key，可空数组"]}
  ],
  "vocab": [{"headword": "辞书形", "reading": "假名", "meaning_zh": "中文释义",
             "pos": "词性", "jlpt_level": "N5..N1 或 null"}]
}
对 register_tag 为 rough/feminine/dialect 的句子，在 grammar_notes 里附一条现实礼貌场合的等价说法。"""


def _build_user(batch: list[Line], grammar_index: list[dict]) -> str:
    return json.dumps({
        "grammar_checklist": grammar_index,
        "lines": [{"idx": ln.idx, "text": ln.text_jp} for ln in batch],
    }, ensure_ascii=False)


def _grammar_index(session: Session) -> list[dict]:
    rows = session.query(GrammarPoint.key, GrammarPoint.name).filter_by(curated=True).all()
    return [{"key": k, "name": n} for k, n in rows]


def _upsert_vocab(session: Session, items: list[dict], source_line_id: int) -> None:
    for it in items:
        hw, rd = it.get("headword"), it.get("reading")
        if not hw or not rd:
            continue
        exists = session.query(Vocab).filter_by(headword=hw, reading=rd).first()
        if exists:
            continue
        session.add(Vocab(
            headword=hw, reading=rd, meaning_zh=it.get("meaning_zh", ""),
            pos=it.get("pos"), jlpt_level=it.get("jlpt_level"),
            source_line_id=source_line_id, in_srs=False,
        ))


def _mark_grammar_seen(session: Session, keys: list[str], source_line_id: int) -> None:
    for key in keys:
        gp = session.query(GrammarPoint).filter_by(key=key).first()
        if gp and gp.status == "locked":
            gp.status = "seen"
            gp.source_line_id = source_line_id


def process_episode(session: Session, episode_id: int, batch_size: int = 15) -> None:
    """加工一集：分批处理未加工的行。可重复调用（断点续跑）。"""
    episode = session.get(Episode, episode_id)
    if episode is None:
        raise ValueError(f"episode {episode_id} 不存在")
    episode.status = "processing"
    session.commit()

    grammar_index = _grammar_index(session)
    pending = [ln for ln in episode.lines if not ln.processed]

    try:
        for start in range(0, len(pending), batch_size):
            batch = pending[start:start + batch_size]
            result = llm.call_json(
                system=_SYSTEM, user=_build_user(batch, grammar_index))
            by_idx = {item["idx"]: item for item in result.get("lines", [])}
            for ln in batch:
                ann = by_idx.get(ln.idx, {})
                ln.furigana = to_furigana(ln.text_jp)
                ln.translation_zh = ann.get("translation_zh")
                ln.grammar_notes = ann.get("grammar_notes") or []
                ln.register_tag = ann.get("register_tag")
                keys = ann.get("grammar_point_keys") or []
                ln.grammar_point_keys = keys
                ln.processed = True
                session.flush()  # 取得 ln.id
                _mark_grammar_seen(session, keys, ln.id)
            # vocab 归到该批首行作为语境来源
            if batch:
                _upsert_vocab(session, result.get("vocab", []), batch[0].id)
            episode.processed_lines = sum(1 for x in episode.lines if x.processed)
            session.commit()
        episode.status = "ready"
        session.commit()
    except Exception:
        episode.status = "failed"
        session.commit()
        raise
```

> 说明：注音 `to_furigana` 由本地 SudachiPy 生成（不耗 LLM）；`extract_vocab_candidates` 已实现，作为 Phase 2 候选词补充入口保留，Phase 1 词条以 LLM 返回的 `vocab` 为准。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: 3 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: 加工流水线"
```

---

## Task 11: CLI 导入命令与端到端集成测试

**Files:**
- Create: `backend/app/cli.py`
- Test: `backend/tests/test_cli_integration.py`

CLI 把"建番 → 导入字幕 → 落库 Line → 加工"串起来，用于人工验收。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_cli_integration.py`:

```python
from pathlib import Path

from app.models import Episode, Line, Series
from app.services import pipeline
from app.cli import import_episode_from_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_from_file_then_process(db_session, monkeypatch):
    from app.grammar_loader import load_grammar_seed
    from tests.test_pipeline import _fake_llm

    load_grammar_seed(db_session)
    monkeypatch.setattr(pipeline.llm, "call_json", _fake_llm)

    episode = import_episode_from_file(
        db_session, series_title="测试番", number=1,
        file_path=str(FIXTURES / "sample.srt"))

    assert db_session.query(Series).filter_by(title="测试番").count() == 1
    lines = db_session.query(Line).filter_by(episode_id=episode.id).all()
    assert len(lines) == 2

    pipeline.process_episode(db_session, episode.id)
    db_session.refresh(episode)
    assert episode.status == "ready"
    assert all(ln.processed for ln in lines)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_cli_integration.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.cli'`。

- [ ] **Step 3: 写实现**

`backend/app/cli.py`:

```python
import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.db import init_db, make_engine, make_session_factory
from app.grammar_loader import load_grammar_seed
from app.models import Episode, Line, Series
from app.services import pipeline
from app.services.subtitles import parse_subtitle


def import_episode_from_file(session: Session, series_title: str, number: int,
                             file_path: str) -> Episode:
    """从本地字幕文件导入一集，落库 Series/Episode/Line（未加工）。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_subtitle(content, path.suffix)

    series = session.query(Series).filter_by(title=series_title).first()
    if series is None:
        series = Series(title=series_title)
        session.add(series)
        session.flush()

    episode = Episode(series_id=series.id, number=number, source="upload",
                      status="processing", total_lines=len(parsed))
    for p in parsed:
        episode.lines.append(Line(
            idx=p.idx, start_ms=p.start_ms, end_ms=p.end_ms,
            speaker=p.speaker, text_jp=p.text, processed=False))
    session.add(episode)
    session.commit()
    return episode


def main() -> None:
    parser = argparse.ArgumentParser(description="追番日语 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import-episode", help="从字幕文件导入并加工一集")
    imp.add_argument("--series", required=True)
    imp.add_argument("--number", type=int, required=True)
    imp.add_argument("--file", required=True)

    args = parser.parse_args()

    engine = make_engine(settings.database_url)
    init_db(engine)
    session = make_session_factory(engine)()
    try:
        load_grammar_seed(session)
        if args.cmd == "import-episode":
            ep = import_episode_from_file(session, args.series, args.number, args.file)
            print(f"已导入 episode id={ep.id}，{ep.total_lines} 行。开始加工…")
            pipeline.process_episode(session, ep.id)
            print(f"加工完成，状态={ep.status}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && .venv/bin/pytest tests/test_cli_integration.py -v`
Expected: 1 个测试 PASS。

- [ ] **Step 5: 跑全量测试**

Run: `make test`
Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/cli.py backend/tests/test_cli_integration.py
git commit -m "feat: CLI 导入命令与端到端集成测试"
```

---

## 验收标准

- `make test` 全绿。
- 配好 `.env`（fox key）后，可执行真实端到端验证：
  `cd backend && .venv/bin/python -m app.cli import-episode --series "测试番" --number 1 --file <某字幕文件>`
  → 数据库中生成 `Series` / `Episode(status=ready)` / 全部 `Line(processed=true，含注音/翻译/语法标注)`、相应 `Vocab` 与点亮的 `GrammarPoint`。

## 交付物

一个能把动漫整集导入并加工入库的后端。下一份计划（Plan 2）在此之上实现 SRS 算法、今日训练编排与全部 API 路由。
