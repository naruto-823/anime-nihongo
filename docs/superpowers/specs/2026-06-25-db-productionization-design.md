# 数据库生产化设计(PostgreSQL + Alembic + Docker)

> 2026-06-25 · 子项目一(共两个:① 数据库生产化 → ② 登录系统)。
> 把当前「SQLite + create_all + 手写加列 hack」升级为生产级:PostgreSQL 主库、
> Alembic 版本化迁移、Docker Compose 容器编排。代码保持方言无关,本地/CI 测试仍用内存 SQLite。

## 1. 目标与非目标

**目标**
- 生产主库切到 **PostgreSQL**(psycopg3 驱动),`DATABASE_URL` 驱动。
- 引入 **Alembic** 版本化迁移,替换非生产级的 `create_all` + `_migrate_in_place`。
- **Docker Compose** 一键起 `db` + `app`,可作为生产容器编排基线。
- 兑现选型承诺:Postgres **JSONB** + **pg_trgm** 词库搜索加速。
- 全程不破坏现有功能;后端 180 / 前端 21 测试保持绿。

**非目标(后续子项目)**
- 登录系统(User + JWT)= 子项目二,建在此地基上。
- 数据按用户隔离(SRS 状态从共享表拆出)= 再后续。
- 现有本地 SQLite 开发数据迁移到 Postgres = 按需补一次性脚本,本期范围外(Postgres 全新 + 种子起)。

## 2. 关键决策(含理由)

| 决策 | 选择 | 理由 |
|---|---|---|
| 生产主库 | PostgreSQL 16 | JSONB / pg_trgm / 事务性 DDL,贴合字典+搜索+JSON 重的本应用 |
| 驱动 | `psycopg`(psycopg3,binary) | 官方现代驱动,SQLAlchemy 2.0 一等支持 |
| 迁移 | Alembic | 生产必须版本化、可回滚;现 hack 非生产级 |
| 测试库 | 保留内存 SQLite | 快、无外部依赖;靠 `with_variant` 保持兼容 |
| JSON 列 | `JSON().with_variant(JSONB,"postgresql")` | 测试用 JSON、生产用 JSONB,一份模型两边通吃 |
| 搜索 | pg_trgm + GIN(postgres-only 迁移) | `/api/vocab` 的 `LIKE %x%` 免改 SQL 即获索引加速 |
| 容器 | 前端多阶段构建打进后端镜像 | `main.py` 已支持静态托管 dist;单 app 容器最简;nginx 留待规模需要 |

## 3. 引擎与配置(`app/db.py`、`app/config.py`)

- 依赖新增:`psycopg[binary]`、`alembic`(写入 `backend/pyproject.toml`)。
- `make_engine(url)`:
  - SQLite:保留 `check_same_thread=False` 与文件目录创建。
  - PostgreSQL:加 `pool_pre_ping=True`、`pool_size=5`、`max_overflow=10`(可调);不传 SQLite 专用 connect_args。
- `config.settings.database_url` 仍是唯一来源;`.env`/容器环境注入。
- **删除** `_migrate_in_place` 及其 `_add_column_if_missing`(SQLite 报错字符串 hack)。
- `init_app_db()` 拆分职责:
  - 生产:不再 `create_all`;schema 由 `alembic upgrade head`(容器 entrypoint)管理。
  - 启动仍做**幂等灌种子**(grammar/vocab loader)。
  - 测试:conftest 继续用 `Base.metadata.create_all`(不走 Alembic,保持快)。

## 4. Alembic 迁移

- 目录:`backend/alembic.ini` + `backend/migrations/`(`env.py` 绑定 `app.db.Base.metadata` 与 `settings.database_url`;`script.py.mako`)。
- `env.py` 要点:导入 `app.models` 注册全部表;offline/online 两模式;`compare_type=True`。
- **迁移 0001 — 初始全量 schema**:囊括当前 10 张表(Series/Episode/Line/Scene/Vocab/GrammarPoint/DailySession/AppSetting/TowerProgress/PlayerStats),JSON 列在 postgres 上落为 JSONB(由 with_variant 自动决定)。
- **迁移 0002 — pg_trgm 搜索索引(postgres-only)**:
  - `op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")`(仅当 `op.get_bind().dialect.name == "postgresql"`)。
  - 在 `vocab` 的 `headword`/`reading`/`meaning_zh` 上建 GIN trgm 索引(`gin_trgm_ops`)。
  - SQLite 方言下整条迁移 no-op(守卫跳过),保证测试不受影响。
- 迁移可 `upgrade head` / `downgrade base` 往返。

## 5. JSONB 变体(`app/models/*.py`)

- 定义一处共享列类型:`JSONB_OR_JSON = JSON().with_variant(JSONB, "postgresql")`(放 `app/db.py` 导出)。
- 把现有 `mapped_column(JSON, ...)` 改为该变体:`Line.furigana/grammar_notes/grammar_point_keys`、`Series.characters`、`GrammarPoint.quiz_cache`、`DailySession.summary`、`AppSetting.value`、`TowerProgress`/`PlayerStats` 无 JSON 列(跳过)。
- 行为不变;仅生产存储为 JSONB。

## 6. 容器编排

- **`backend/Dockerfile`(多阶段)**
  1. `node:20` 阶段:`cd frontend && npm ci && npm run build` → 产出 `frontend/dist`。
  2. `python:3.12-slim` 阶段:装后端依赖(pip install -e backend),拷贝 `backend/` 与上一阶段 `frontend/dist`。
  3. entrypoint:`alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- **`docker-compose.yml`**(仓库根)
  - `db`:`postgres:16-alpine`,环境 `POSTGRES_USER/PASSWORD/DB`,持久卷 `pgdata:/var/lib/postgresql/data`,healthcheck `pg_isready`。
  - `app`:`build: .`(指 backend/Dockerfile),`depends_on: db: condition: service_healthy`,环境 `DATABASE_URL=postgresql+psycopg://...@db:5432/anime` + `ANTHROPIC_*`/`JIMAKU_API_TOKEN`/`VOICEVOX_URL`,端口 `8000:8000`。
  - VOICEVOX 仍为宿主本地服务(容器内通过 `host.docker.internal:50021` 访问,文档注明)。
- **`.env.example`** 补:`DATABASE_URL` 的 postgres 形态 + `POSTGRES_USER/PASSWORD/DB`;保留 SQLite 形态作本地非容器开发示例。

## 7. 种子与现有数据

- 启动后 `load_grammar_seed` / `load_vocab_seed` 幂等灌入(沿用现有 loader);Postgres 首启自动建立词库。
- 现有本地 `data/anime-nihongo.db` 的塔进度/XP 属开发数据,**不自动迁移**;如需保留,后补一次性 dump→load 脚本(范围外)。

## 8. 测试策略

- conftest 内存 SQLite 不变;**全量 pytest(后端 180)与前端 21 必须仍绿**(JSONB 变体保证)。
- 新增:
  - `test_db_engine.py`:`make_engine` 对 postgres URL 设置 pool 参数、对 sqlite 设置 connect_args 的单测(不真连库)。
  - `test_migrations.py`:用临时 SQLite 跑 `alembic upgrade head` 后表齐全、`downgrade base` 可逆;断言 pg_trgm 迁移在 sqlite 下 no-op 不报错。
- 真连 Postgres 的端到端验证靠 `docker-compose up` 手动冒烟(不进 CI 单测,避免依赖 Docker)。

## 9. 文件改动一览

- 改:`backend/pyproject.toml`(deps)、`backend/app/db.py`(引擎/变体/去 hack)、`backend/app/models/*.py`(JSONB 变体)、`backend/.env.example`、根 `.env.example`。
- 新:`backend/alembic.ini`、`backend/migrations/`(env + 2 迁移)、`backend/Dockerfile`、`docker-compose.yml`、`.dockerignore`、测试 `test_db_engine.py`/`test_migrations.py`。
- 注:`db.py` 现有 `test_db_migrations.py` 测的是 `_migrate_in_place`——删 hack 后需同步删/改该测试。

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 删 `_migrate_in_place` 影响现有 `test_db_migrations.py` | 该测试随 hack 一并移除/重写为 Alembic 测试 |
| SQLite 与 Postgres 行为差异(如布尔、JSON) | 用 SQLAlchemy 类型 + with_variant;不写裸方言 SQL |
| 首启灌 10k 词到 Postgres 慢 | 批量 `add_all`;一次性、幂等可接受 |
| VOICEVOX 在容器内不可达 | 文档注明用 `host.docker.internal`;非容器开发不受影响 |
| server_default `func.now()` 跨方言 | SQLAlchemy 统一翻译,两库均可 |

## 11. 验收标准

- `docker-compose up` 后:Postgres 起、`alembic upgrade head` 成功、应用 8000 可访问、词库/塔接口返回正常。
- 后端 180 + 前端 21 测试仍绿;新增迁移/引擎测试通过。
- `/api/vocab?q=…` 在 Postgres 上走 trgm GIN 索引(EXPLAIN 验证)。
- ruff 干净(仅预存 episodes.py/pipeline.py 的 E501 不在本次范围)。
