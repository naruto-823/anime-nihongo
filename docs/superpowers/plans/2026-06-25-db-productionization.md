# 数据库生产化(PostgreSQL + Alembic + Docker)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端从「SQLite + create_all + 手写加列 hack」升级为生产级:PostgreSQL 主库、Alembic 版本化迁移、Docker Compose 容器编排;本地/CI 测试仍用内存 SQLite。

**Architecture:** `DATABASE_URL` 驱动方言;JSON 列用 `with_variant(JSONB,"postgresql")` 一份模型两边通吃;Alembic 初始迁移直接 `Base.metadata.create_all`(保证与模型零偏差、JSONB 随方言渲染),pg_trgm 索引为 postgres-only 守卫迁移;多阶段 Dockerfile 把前端打进后端镜像,entrypoint 跑 `alembic upgrade head` 再起 uvicorn。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 / psycopg3 · Alembic · Docker Compose · pytest(内存 SQLite)。

## Global Constraints

- `DATABASE_URL` 是唯一数据库配置来源;测试/本地 `sqlite:///…`,生产 `postgresql+psycopg://user:pass@db:5432/anime`。
- 代码保持**方言无关**:不写裸方言 SQL(pg_trgm 迁移除外,且按 `dialect.name` 守卫)。
- JSON 列统一用 `app.db.JSONB_OR_JSON = JSON().with_variant(JSONB, "postgresql")`。
- ruff line-length 120,`select=["E","F","I","N","W"]`;改动文件须 `ruff check` 无错(预存的 episodes.py/pipeline.py E501 不在范围)。
- **后端全量 pytest 必须保持绿**(改动前 180);测试用 `tests/conftest.py` 的 `db_session`/`client`(内存 SQLite,StaticPool)。
- 删 `_migrate_in_place` 时**同步删除** `backend/tests/test_db_migrations.py`(它测的就是该函数)。

---

## 文件结构

- Modify `backend/pyproject.toml` — 加 `psycopg[binary]`、`alembic` 依赖。
- Modify `backend/app/db.py` — `JSONB_OR_JSON` 变体;engine pool;删 `_migrate_in_place`/`_add_column_if_missing`;`init_app_db` 方言感知。
- Modify `backend/app/models/content.py`、`backend/app/models/study.py` — JSON 列改用变体。
- Delete `backend/tests/test_db_migrations.py`。
- Create `backend/alembic.ini`、`backend/migrations/{env.py,script.py.mako,versions/0001_initial.py,versions/0002_pg_trgm.py}`。
- Create `backend/tests/test_migrations.py`、`backend/tests/test_db_engine.py`。
- Create `backend/Dockerfile`、`docker-compose.yml`、`.dockerignore`。
- Modify `.env.example` — 补 Postgres 形态与 `POSTGRES_*`。

---

## Task 1: 依赖(psycopg3 + Alembic)

**Files:**
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Produces: 可 `import psycopg`、`import alembic`;venv 已装。

- [ ] **Step 1: 改 pyproject 依赖**

把 `backend/pyproject.toml` 的 `dependencies` 列表末尾追加两项(在 `"sudachidict-core>=20240409",` 之后):

```toml
    "psycopg[binary]>=3.2.0",
    "alembic>=1.13.0",
```

- [ ] **Step 2: 安装**

Run: `cd backend && .venv/bin/pip install -e ".[dev]"`
Expected: 成功安装 psycopg、alembic(及依赖)。

- [ ] **Step 3: 验证可导入**

Run: `cd backend && .venv/bin/python -c "import psycopg, alembic; print('ok', alembic.__version__)"`
Expected: 打印 `ok <版本>`。

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml
git commit -m "build(backend): add psycopg3 and alembic deps"
```

---

## Task 2: JSONB 变体 + 引擎池 + 移除迁移 hack

**Files:**
- Modify: `backend/app/db.py`
- Modify: `backend/app/models/content.py`, `backend/app/models/study.py`
- Create: `backend/tests/test_db_engine.py`
- Delete: `backend/tests/test_db_migrations.py`

**Interfaces:**
- Produces:
  - `app.db.JSONB_OR_JSON`(SQLAlchemy 类型,postgres→JSONB / 其它→JSON)。
  - `make_engine(url)` 对 postgres 设 `pool_pre_ping=True, pool_size=5, max_overflow=10`。
  - `init_app_db()` 方言感知:sqlite 走 `create_all`,postgres 交给 Alembic(no-op 建表)。
- Consumes: 无(基础任务)。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_db_engine.py`:

```python
from sqlalchemy.dialects import postgresql, sqlite

from app.db import JSONB_OR_JSON, make_engine


def test_json_variant_compiles_per_dialect():
    assert JSONB_OR_JSON.compile(dialect=postgresql.dialect()) == "JSONB"
    assert JSONB_OR_JSON.compile(dialect=sqlite.dialect()) == "JSON"


def test_make_engine_routes_dialect():
    assert make_engine("sqlite://").dialect.name == "sqlite"
    assert make_engine("postgresql+psycopg://u:p@h:5432/db").dialect.name == "postgresql"


def test_make_engine_postgres_sets_pre_ping():
    eng = make_engine("postgresql+psycopg://u:p@h:5432/db")
    assert eng.pool._pre_ping is True
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_db_engine.py -v`
Expected: FAIL（ImportError: JSONB_OR_JSON）

- [ ] **Step 3: 改 `app/db.py`**

替换 `make_engine`、删除 `_add_column_if_missing`/`_migrate_in_place`、改 `init_app_db`,并新增变体类型。`app/db.py` 改为:

```python
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import JSON, Engine, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# JSON 列:生产(postgres)用 JSONB,其余(测试 sqlite)用 JSON
JSONB_OR_JSON = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url.startswith("sqlite:///"):
            db_path = Path(url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args=connect_args)
    # PostgreSQL 等生产库:连接池 + 预检
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, autoflush=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """建表。导入 models 以注册到 Base.metadata。"""
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)


from app.config import settings  # noqa: E402

_engine = make_engine(settings.database_url)
SessionLocal = make_session_factory(_engine)


def init_app_db() -> None:
    """应用启动时准备 schema。

    sqlite(本地/测试便利):直接 create_all。
    postgres(生产):schema 由 `alembic upgrade head`(容器 entrypoint)管理,此处不建表。
    """
    if _engine.dialect.name == "sqlite":
        init_db(_engine)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖:每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 模型 JSON 列改用变体**

`backend/app/models/content.py`:把 `from sqlalchemy import JSON, ForeignKey, UniqueConstraint, func` 改为 `from sqlalchemy import ForeignKey, UniqueConstraint, func`,并 `from app.db import Base, JSONB_OR_JSON`;把该文件内 4 处 `mapped_column(JSON, default=None)` 改为 `mapped_column(JSONB_OR_JSON, default=None)`(`Series.characters`、`Line.furigana`、`Line.grammar_notes`、`Line.grammar_point_keys`)。

`backend/app/models/study.py`:同样把 `JSON` 从 `sqlalchemy` 导入移除,改 `from app.db import Base, JSONB_OR_JSON`;3 处 `mapped_column(JSON, ...)` 改为 `JSONB_OR_JSON`(`GrammarPoint.quiz_cache`、`DailySession.summary`、`AppSetting.value`)。

- [ ] **Step 5: 删除过时迁移测试**

Run: `git rm backend/tests/test_db_migrations.py`
(它测的 `_migrate_in_place` 已删除。)

- [ ] **Step 6: 运行测试**

Run: `cd backend && .venv/bin/pytest tests/test_db_engine.py tests/test_db.py -v && .venv/bin/pytest -q`
Expected: 新测试 PASS;全量仍绿(JSONB 变体在 sqlite 下等价 JSON)。

- [ ] **Step 7: ruff + Commit**

```bash
cd backend && .venv/bin/ruff check app/db.py app/models/content.py app/models/study.py tests/test_db_engine.py
cd .. && git add backend/app/db.py backend/app/models/content.py backend/app/models/study.py backend/tests/test_db_engine.py
git rm backend/tests/test_db_migrations.py
git commit -m "refactor(db): JSONB variant + pool config, drop ad-hoc migration hack"
```

---

## Task 3: Alembic 脚手架 + 初始迁移

**Files:**
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_initial.py`
- Create: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `app.db.Base`、`app.config.settings`。
- Produces: `alembic upgrade head` 建出全部 10 张表;`downgrade base` 可逆。env 解析 url 优先 `config` 显式设置,回退 `settings.database_url`(供测试覆盖)。

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_migrations.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
_EXPECTED = {
    "series", "episode", "line", "scene", "vocab", "grammar_point",
    "daily_session", "app_setting", "tower_progress", "player_stats",
    "alembic_version",
}


def _cfg(db_path: Path) -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path):
    db = tmp_path / "m.db"
    command.upgrade(_cfg(db), "head")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert _EXPECTED <= set(insp.get_table_names())


def test_downgrade_base_drops_tables(tmp_path):
    db = tmp_path / "m.db"
    cfg = _cfg(db)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert "vocab" not in set(insp.get_table_names())
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_migrations.py -v`
Expected: FAIL（找不到 alembic.ini / 无迁移）

- [ ] **Step 3: 建 `backend/alembic.ini`**

```ini
[alembic]
script_location = migrations
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: 建 `backend/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: 建 `backend/migrations/env.py`**

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db import Base
import app.models  # noqa: F401  注册全部表到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# url 优先取显式设置(测试覆盖),否则用应用配置
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 6: 建初始迁移 `backend/migrations/versions/0001_initial.py`**

用 metadata 直接建表(与模型零偏差,JSONB 随方言渲染):

```python
"""initial schema

Revision ID: 0001_initial
Revises:
"""
from alembic import op

from app.db import Base
import app.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
```

- [ ] **Step 7: 运行测试**

Run: `cd backend && .venv/bin/pytest tests/test_migrations.py -v`
Expected: PASS（建表 + 可逆)

- [ ] **Step 8: ruff + Commit**

```bash
cd backend && .venv/bin/ruff check migrations/env.py migrations/versions/0001_initial.py tests/test_migrations.py
cd .. && git add backend/alembic.ini backend/migrations backend/tests/test_migrations.py
git commit -m "feat(db): alembic scaffold + metadata-based initial migration"
```

---

## Task 4: pg_trgm 词库搜索索引迁移(postgres-only)

**Files:**
- Create: `backend/migrations/versions/0002_pg_trgm.py`
- Modify: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: 0001 迁移。
- Produces: postgres 上 `pg_trgm` 扩展 + `vocab(headword/reading/meaning_zh)` GIN trgm 索引;sqlite 下整条 no-op。

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_migrations.py` 末尾追加(验证 0002 在 sqlite 下 upgrade/downgrade 不报错,即 no-op 守卫生效):

```python
def test_pg_trgm_migration_is_noop_on_sqlite(tmp_path):
    db = tmp_path / "m.db"
    cfg = _cfg(db)
    command.upgrade(cfg, "head")        # 含 0002,sqlite 下应 no-op 不报错
    command.downgrade(cfg, "0001_initial")
    insp = inspect(create_engine(f"sqlite:///{db}"))
    assert "vocab" in set(insp.get_table_names())   # 表仍在(只回退索引迁移)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/pytest tests/test_migrations.py::test_pg_trgm_migration_is_noop_on_sqlite -v`
Expected: FAIL（downgrade 到 `0001_initial` 找不到该 revision,因为 0002 不存在）

- [ ] **Step 3: 建 `backend/migrations/versions/0002_pg_trgm.py`**

```python
"""pg_trgm GIN index for vocab search (postgresql only)

Revision ID: 0002_pg_trgm
Revises: 0001_initial
"""
from alembic import op

revision = "0002_pg_trgm"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_COLS = ("headword", "reading", "meaning_zh")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for col in _COLS:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_vocab_{col}_trgm "
            f"ON vocab USING gin ({col} gin_trgm_ops)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for col in _COLS:
        op.execute(f"DROP INDEX IF EXISTS ix_vocab_{col}_trgm")
    # 扩展保留(可能被他处使用)
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && .venv/bin/pytest tests/test_migrations.py -v`
Expected: PASS（全部 3 个迁移测试）

- [ ] **Step 5: ruff + Commit**

```bash
cd backend && .venv/bin/ruff check migrations/versions/0002_pg_trgm.py tests/test_migrations.py
cd .. && git add backend/migrations/versions/0002_pg_trgm.py backend/tests/test_migrations.py
git commit -m "feat(db): pg_trgm GIN index migration for vocab search"
```

---

## Task 5: 容器化(Dockerfile + Compose + env)

**Files:**
- Create: `backend/Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Modify: `.env.example`

**Interfaces:**
- Consumes: Alembic(`alembic upgrade head`)、`app.main:app`。
- Produces: `docker-compose up` 起 `db`+`app`,app 容器 entrypoint 跑迁移再起服务。

- [ ] **Step 1: 建 `backend/Dockerfile`(多阶段)**

```dockerfile
# --- 前端构建 ---
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 后端运行 ---
FROM python:3.12-slim AS app
WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY backend/pyproject.toml ./
RUN pip install -e .
COPY backend/ ./
# 前端产物放到 main.py 期望的 frontend/dist
COPY --from=frontend /fe/dist /app/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

> 注:`pip install -e .` 仅装 runtime 依赖(不含 `[dev]`),生产镜像更瘦。`main.py` 静态托管路径为 `frontend/dist`(相对仓库根 = `/app/frontend/dist`),与 COPY 目标一致。

- [ ] **Step 2: 建 `.dockerignore`(仓库根)**

```
**/__pycache__/
**/.venv/
**/node_modules/
**/dist/
**/.pytest_cache/
**/.ruff_cache/
**/*.db
**/*.sqlite*
.git/
.superpowers/
*.tmp-*
```

- [ ] **Step 3: 建 `docker-compose.yml`(仓库根)**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-anime}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-anime}
      POSTGRES_DB: ${POSTGRES_DB:-anime}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-anime}"]
      interval: 5s
      timeout: 3s
      retries: 10

  app:
    build:
      context: .
      dockerfile: backend/Dockerfile
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-anime}:${POSTGRES_PASSWORD:-anime}@db:5432/${POSTGRES_DB:-anime}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL:-}
      JIMAKU_API_TOKEN: ${JIMAKU_API_TOKEN:-}
      VOICEVOX_URL: ${VOICEVOX_URL:-http://host.docker.internal:50021}
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  pgdata:
```

- [ ] **Step 4: 更新 `.env.example`**

在 `.env.example` 的数据库段把 SQLite 示例保留为本地注释,并补 Postgres / 容器变量。把原 `DATABASE_URL=sqlite:///./data/anime-nihongo.db` 段替换为:

```bash
# 数据库
# 本地非容器开发(默认):
DATABASE_URL=sqlite:///./data/anime-nihongo.db
# 生产/容器(docker-compose 用):
# DATABASE_URL=postgresql+psycopg://anime:anime@db:5432/anime
POSTGRES_USER=anime
POSTGRES_PASSWORD=anime
POSTGRES_DB=anime
```

- [ ] **Step 5: 校验 compose 配置语法**

Run: `docker compose config >/dev/null && echo "compose ok"`
Expected: 打印 `compose ok`(仅校验 YAML/插值,不拉镜像)。若环境无 docker,跳过并在报告注明。

- [ ] **Step 6: Commit**

```bash
git add backend/Dockerfile docker-compose.yml .dockerignore .env.example
git commit -m "feat(ops): dockerize app + postgres via compose, entrypoint runs migrations"
```

---

## Task 6: 全量回归 + 容器冒烟

**Files:** 无新增,仅验证。

- [ ] **Step 1: 后端全量 + ruff**

Run: `cd backend && .venv/bin/ruff check app migrations tests && .venv/bin/pytest -q`
Expected: ruff 仅剩预存 episodes.py/pipeline.py 的 E501(不在本次改动文件);pytest 全绿(应 ≥ 改动前数量)。

- [ ] **Step 2: 容器端到端冒烟(需 Docker;无则注明跳过)**

Run:
```bash
docker compose up -d --build
sleep 20
curl -s -o /dev/null -w "tower: %{http_code}\n" http://localhost:8000/api/tower
curl -s "http://localhost:8000/api/vocab?q=食&limit=2" | head -c 120
docker compose down
```
Expected: `/api/tower` 200;`/api/vocab` 返回 JSON(说明迁移+种子+Postgres 链路通)。

- [ ] **Step 3: Commit(若有微调)**

```bash
git add -A && git commit -m "test: db productionization regression green"
```

---

## Self-Review(对照 spec)

**1. Spec 覆盖**
- Postgres + psycopg3(spec §2/§3)→ Task 1/2 ✓
- Alembic 取代 hack(spec §3/§4)→ Task 2(删 hack)+ Task 3(scaffold/初始迁移)✓
- JSONB with_variant(spec §5)→ Task 2 ✓
- pg_trgm 索引(spec §6)→ Task 4 ✓
- Docker 多阶段 + compose + env(spec §6)→ Task 5 ✓
- 种子启动幂等(spec §7)→ 现有 main.py 未改,init_app_db 仅管 schema,种子逻辑不变 ✓
- 测试保留内存 SQLite(spec §8)→ conftest 不动;新增 test_db_engine/test_migrations ✓
- 删 hack 牵连 test_db_migrations(spec §9/§10)→ Task 2 Step 5 删除 ✓

**2. 占位扫描**:无 TBD/TODO;每步含完整代码或精确命令。

**3. 类型/命名一致性**:`JSONB_OR_JSON` 在 db.py 定义、models 引用、迁移经 metadata 间接使用,一致;迁移 revision id(`0001_initial`/`0002_pg_trgm`)在文件、down_revision、测试 downgrade 目标处一致;`init_app_db` 方言分支与 conftest(直接 `init_db`)不冲突。

**已知非阻塞**:容器冒烟(Task 5 Step5 / Task 6 Step2)依赖宿主 Docker;无 Docker 环境则按步骤注明跳过,不阻塞代码层交付。VOICEVOX 走 `host.docker.internal`(compose 已配 extra_hosts)。
