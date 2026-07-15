# 用户系统 + JWT + 学习状态 user-scoped 化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给追番日语后端加账号体系(User + 注册/登录 + JWT),并把学习状态(SRS/Tower/Player/Daily)按用户隔离,内容资产仍全局共享。

**Architecture:** expand-contract 顺序。先加 auth(独立、不动旧表),再加 per-user 学习态新表(additive,旧 SRS 列保留),逐服务/接口切到 user-scoped(经 `learning_repo` 收敛取或建逻辑),最后 contract 删除 `Vocab`/`GrammarPoint` 上的旧 SRS 列。每个 Task 结束全量测试绿。鉴权唯一入口 `get_current_user`;取或建 SRS 行唯一入口 `learning_repo.get_or_create_*_srs`。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic;鉴权 PyJWT(HS256) + bcrypt;测试 pytest + 内存 SQLite(StaticPool);前端 React + react-router + msw;后端包管理 uv,前端 npm。

## Global Constraints

- JWT:HS256,**单 access token,7 天过期**,`sub` = user_id,过期/非法 decode 返回 `None`;密钥取 `settings.jwt_secret`(有 dev 默认,生产经 env 注入)。
- 密码:bcrypt 哈希(`hash_password`/`verify_password`)。
- 种子 admin:启动时若 `User` 表为空且未禁用则建 `admin`;密码取 `settings.seed_admin_password`(默认 `admin`);`settings.disable_seed_user` 为真时跳过。
- 知识表(`Vocab`/`GrammarPoint`)自本期起**只读知识**,任何用户态写入一律走 `user_vocab_srs`/`user_grammar_srs`;不在知识表存用户态。
- 本期范围:仅隔离**学习状态**(SRS/Tower/Player/Daily);**内容资产**(Series/Episode/Line/Scene)仍全局共享(番剧库按用户隔离留后续)。`series/episodes/tts/conversation` 的内容读取不强制鉴权;但 `conversation/feedback` 写 SRS 需鉴权。
- 测试:用内存 SQLite(`sqlite://` + StaticPool),全量保持绿。
- 代码风格:ruff line-length 120,select `["E","F","I","N","W"]`。
- 不回填历史数据(fresh + 种子);Alembic 0003/0004 的 upgrade/downgrade 在临时 sqlite 必须通过。
- 取或建 user-scoped SRS 行逻辑只能出现在 `learning_repo`,禁止在 service/api 多处手写。

---

## File Structure

新增文件:
- `backend/app/services/auth.py` — JWT + bcrypt 纯逻辑(可单测,无 DB)。
- `backend/app/models/auth.py` — `User` 模型。
- `backend/app/models/learning.py` — `UserVocabSrs`/`UserGrammarSrs` 模型。
- `backend/app/deps.py` — `get_current_user` 鉴权依赖(唯一鉴权入口)。
- `backend/app/api/auth.py` — register/login/me 路由。
- `backend/app/services/learning_repo.py` — `get_or_create_vocab_srs`/`get_or_create_grammar_srs`。
- `backend/migrations/versions/0003_user_scoping.py` — 建新表 + 受改表加列/改唯一(不删旧 SRS 列)。
- `backend/migrations/versions/0004_drop_knowledge_srs.py` — contract:从 vocab/grammar_point 删 SRS 列。
- `frontend/src/pages/Login.tsx` — 注册/登录页。

修改文件:`backend/app/config.py`、`backend/pyproject.toml`、`backend/app/models/{__init__.py,game.py,study.py}`、`backend/app/services/{srs.py,session.py,tower.py,pipeline.py}`、`backend/app/api/{srs.py,study.py,grammar.py,vocab.py,progress.py,today.py,conversation.py,tower.py}`、`backend/app/main.py`、`backend/tests/conftest.py` 与受影响测试、`backend/tests/test_migrations.py`;前端 `frontend/src/lib/api.ts`、`frontend/src/App.tsx`、`frontend/src/components/Layout.tsx`、`frontend/tests/handlers.ts` 与受影响测试。

---

## Task 1: 认证纯逻辑 services/auth.py + config

**Files:**
- Create: `backend/app/services/auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/pyproject.toml`
- Test: `backend/tests/test_auth_service.py`

**Interfaces:**
- Produces:
  - `hash_password(pw: str) -> str`
  - `verify_password(pw: str, hashed: str) -> bool`
  - `create_access_token(user_id: int, now: datetime | None = None) -> str`
  - `decode_token(token: str, now: datetime | None = None) -> int | None`(返回 user_id 或 None)
  - `settings.jwt_secret: str`、`settings.seed_admin_password: str`、`settings.disable_seed_user: bool`

- [ ] **Step 1: 加依赖**

编辑 `backend/pyproject.toml`,在 `dependencies` 列表 `"alembic>=1.13.0",` 之后加两行:

```toml
    "alembic>=1.13.0",
    "bcrypt>=4.1.0",
    "pyjwt>=2.8.0",
```

然后安装:

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv sync --extra dev`
Expected: 成功,锁文件含 bcrypt 与 pyjwt。

- [ ] **Step 2: 加配置项**

编辑 `backend/app/config.py`,在 `voicevox_url` 行之后(`def validate_ai` 之前)加:

```python
    # VOICEVOX 本地 TTS 引擎
    voicevox_url: str = "http://localhost:50021"

    # 鉴权
    jwt_secret: str = "dev-insecure-change-me"
    seed_admin_password: str = "admin"
    disable_seed_user: bool = False
```

(保留原 `voicevox_url` 行,仅在其下追加 3 行。)

- [ ] **Step 3: Write the failing test**

创建 `backend/tests/test_auth_service.py`:

```python
from datetime import datetime, timedelta

from app.services.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_token_roundtrip():
    now = datetime(2026, 6, 26, 12, 0, 0)
    token = create_access_token(42, now=now)
    assert decode_token(token, now=now) == 42


def test_token_expired_returns_none():
    issued = datetime(2026, 6, 26, 12, 0, 0)
    token = create_access_token(42, now=issued)
    later = issued + timedelta(days=8)
    assert decode_token(token, now=later) is None


def test_token_garbage_returns_none():
    assert decode_token("not-a-jwt", now=datetime(2026, 6, 26)) is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_auth_service.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app.services.auth'`。

- [ ] **Step 5: Write minimal implementation**

创建 `backend/app/services/auth.py`:

```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(days=7)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str, now: datetime | None = None) -> int | None:
    now = now or datetime.now(timezone.utc)
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return None
    exp = payload.get("exp")
    sub = payload.get("sub")
    if exp is None or sub is None:
        return None
    if datetime.fromtimestamp(exp, tz=timezone.utc) < _as_utc(now):
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
```

说明:`decode_token` 用 `verify_exp=False` 自行按传入 `now` 判过期,使单测能注入时间;naive `now` 视为 UTC。

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_auth_service.py tests/test_config.py -v`
Expected: PASS。

- [ ] **Step 7: ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run ruff check app/services/auth.py app/config.py tests/test_auth_service.py`
Expected: 无新增告警。

- [ ] **Step 8: 全量回归**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q`
Expected: 全绿(此 Task 未改旧行为)。

- [ ] **Step 9: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add pyproject.toml uv.lock app/config.py app/services/auth.py tests/test_auth_service.py
git commit -m "feat(auth): add jwt+bcrypt auth service and settings"
```

---

## Task 2: User 模型 + get_current_user + auth 路由 + 种子

**Files:**
- Create: `backend/app/models/auth.py`
- Create: `backend/app/deps.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_auth.py`

**Interfaces:**
- Consumes: `app.services.auth.{hash_password,verify_password,create_access_token,decode_token}`(Task 1)。
- Produces:
  - `User` 模型(`id, username, password_hash, created_at`)。
  - `get_current_user(authorization: str | None, db: Session) -> User`(FastAPI 依赖,经 `Depends`;无/非法/过期 token → 401)。
  - `seed_admin_user(db: Session) -> None`(User 空且未禁用时建 admin)。
  - 路由:`POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`。

- [ ] **Step 1: Write the failing test**

创建 `backend/tests/test_api_auth.py`:

```python
def test_register_returns_token_and_user(client):
    resp = client.post("/api/auth/register",
                       json={"username": "alice", "password": "pw123456"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["user"]["username"] == "alice"
    assert "id" in body["user"]


def test_register_duplicate_username_409(client):
    client.post("/api/auth/register",
                json={"username": "bob", "password": "pw123456"})
    resp = client.post("/api/auth/register",
                       json={"username": "bob", "password": "other"})
    assert resp.status_code == 409


def test_login_ok_and_wrong_password_401(client):
    client.post("/api/auth/register",
                json={"username": "carol", "password": "pw123456"})
    ok = client.post("/api/auth/login",
                     json={"username": "carol", "password": "pw123456"})
    assert ok.status_code == 200 and ok.json()["token"]
    bad = client.post("/api/auth/login",
                      json={"username": "carol", "password": "nope"})
    assert bad.status_code == 401


def test_login_unknown_user_401(client):
    resp = client.post("/api/auth/login",
                       json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(client):
    token = client.post("/api/auth/register",
                        json={"username": "dave", "password": "pw123456"}
                        ).json()["token"]
    resp = client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "dave"


def test_me_rejects_garbage_token(client):
    resp = client.get("/api/auth/me",
                      headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_api_auth.py -v`
Expected: FAIL,404(路由不存在)。

- [ ] **Step 3: 建 User 模型**

创建 `backend/app/models/auth.py`:

```python
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 4: 注册到 models 包**

编辑 `backend/app/models/__init__.py` 为:

```python
from app.models.auth import User
from app.models.content import Episode, Line, Scene, Series
from app.models.game import PlayerStats, TowerProgress
from app.models.study import AppSetting, DailySession, GrammarPoint, Vocab

__all__ = [
    "Series", "Episode", "Line", "Scene",
    "Vocab", "GrammarPoint", "DailySession", "AppSetting",
    "TowerProgress", "PlayerStats",
    "User",
]
```

- [ ] **Step 5: 建 get_current_user 依赖**

创建 `backend/app/deps.py`:

```python
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth import decode_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未认证")
    user_id = decode_token(authorization.removeprefix("Bearer ").strip())
    if user_id is None:
        raise HTTPException(401, "无效或过期的令牌")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")
    return user
```

- [ ] **Step 6: 建 auth 路由 + 种子函数**

创建 `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


def _auth_payload(user: User) -> dict:
    return {"token": create_access_token(user.id),
            "user": {"id": user.id, "username": user.username}}


@router.post("/register")
def register(body: Credentials, db: Session = Depends(get_db)) -> dict:
    exists = db.query(User).filter_by(username=body.username).first()
    if exists is not None:
        raise HTTPException(409, "用户名已被占用")
    user = User(username=body.username,
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return _auth_payload(user)


@router.post("/login")
def login(body: Credentials, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return _auth_payload(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"id": user.id, "username": user.username}


def seed_admin_user(db: Session) -> None:
    """User 表为空且未禁用时,建默认 admin。"""
    if settings.disable_seed_user:
        return
    if db.query(User).count() > 0:
        return
    db.add(User(username="admin",
                password_hash=hash_password(settings.seed_admin_password)))
    db.commit()
```

- [ ] **Step 7: 注册 router + 启动种子**

编辑 `backend/app/main.py`。在 `_startup` 内 `load_vocab_seed(db)` 之后加 `seed_admin_user(db)`:

```python
    @app.on_event("startup")
    def _startup() -> None:
        init_app_db()
        db = SessionLocal()
        try:
            load_grammar_seed(db)
            load_vocab_seed(db)
            from app.api.auth import seed_admin_user
            seed_admin_user(db)
        finally:
            db.close()
```

并把 `auth` 加入 import 与 include 循环。把 import 块改为含 `auth`:

```python
    from app.api import (
        auth,
        conversation,
        episodes,
        grammar,
        progress,
        series,
        srs,
        study,
        today,
        tower,
        tts,
        vocab,
    )
    for module in (auth, series, episodes, study, srs, grammar, conversation,
                   progress, today, tower, tts, vocab):
        app.include_router(module.router)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_api_auth.py -v`
Expected: PASS(7 项)。

- [ ] **Step 9: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿(旧接口未加鉴权,仍可匿名访问)。

- [ ] **Step 10: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/models/auth.py app/models/__init__.py app/deps.py app/api/auth.py app/main.py tests/test_api_auth.py
git commit -m "feat(auth): User model, get_current_user dep, auth routes, seed admin"
```

---

## Task 3: per-user 学习态表 + Alembic 0003 + learning_repo(additive)

**Files:**
- Create: `backend/app/models/learning.py`
- Create: `backend/app/services/learning_repo.py`
- Create: `backend/migrations/versions/0003_user_scoping.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/game.py`
- Modify: `backend/app/models/study.py`
- Modify: `backend/tests/test_migrations.py`
- Modify: `backend/tests/test_models_game.py`
- Test: `backend/tests/test_learning_repo.py`

**Interfaces:**
- Consumes: `User`(Task 2),`SrsState`/`next_state`(srs.py,Task 4 才用)。
- Produces:
  - `UserVocabSrs`(`id, user_id, vocab_id, in_srs, ease, interval_days, reps, lapses, due_date, last_reviewed`,唯一 `(user_id, vocab_id)`)。
  - `UserGrammarSrs`(同上加 `status` 默认 `"locked"`,字段名 `grammar_id`,唯一 `(user_id, grammar_id)`)。
  - `TowerProgress.user_id`,唯一改 `(user_id, level, zone_idx, stage_idx, is_boss)`。
  - `PlayerStats.user_id`(unique)。
  - `DailySession.user_id`,唯一改 `(user_id, date)`。
  - `learning_repo.get_or_create_vocab_srs(db, user_id, vocab_id) -> UserVocabSrs`
  - `learning_repo.get_or_create_grammar_srs(db, user_id, grammar_id) -> UserGrammarSrs`

> 本 Task **additive**:`Vocab`/`GrammarPoint` 上旧 SRS 列保留,Task 7 才删。

- [ ] **Step 1: 建 learning 模型**

创建 `backend/app/models/learning.py`:

```python
from datetime import date as _date
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class UserVocabSrs(Base):
    __tablename__ = "user_vocab_srs"
    __table_args__ = (
        UniqueConstraint("user_id", "vocab_id", name="uq_user_vocab"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    vocab_id: Mapped[int] = mapped_column(ForeignKey("vocab.id"), index=True)
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[_date | None]
    last_reviewed: Mapped[datetime | None]


class UserGrammarSrs(Base):
    __tablename__ = "user_grammar_srs"
    __table_args__ = (
        UniqueConstraint("user_id", "grammar_id", name="uq_user_grammar"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    grammar_id: Mapped[int] = mapped_column(
        ForeignKey("grammar_point.id"), index=True)
    status: Mapped[str] = mapped_column(default="locked")  # locked/seen/learning
    in_srs: Mapped[bool] = mapped_column(default=False)
    ease: Mapped[float] = mapped_column(default=2.5)
    interval_days: Mapped[int] = mapped_column(default=0)
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    due_date: Mapped[_date | None]
    last_reviewed: Mapped[datetime | None]
```

- [ ] **Step 2: game.py 加 user_id**

编辑 `backend/app/models/game.py` 为:

```python
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TowerProgress(Base):
    __tablename__ = "tower_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "level", "zone_idx", "stage_idx", "is_boss",
                         name="uq_tower_cell"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
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
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), unique=True)
    total_xp: Mapped[int] = mapped_column(default=0)
    player_level: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 3: study.py 的 DailySession 加 user_id**

编辑 `backend/app/models/study.py` 中 `DailySession`:把 `date` 列的 `unique=True` 去掉,加 `user_id` 与新 `__table_args__`。改为:

```python
class DailySession(Base):
    __tablename__ = "daily_session"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    date: Mapped[_date]
    completed: Mapped[bool] = mapped_column(default=False)
    episode_id: Mapped[int | None] = mapped_column(ForeignKey("episode.id"))
    vocab_reviewed: Mapped[int] = mapped_column(default=0)
    grammar_reviewed: Mapped[int] = mapped_column(default=0)
    lines_read: Mapped[int] = mapped_column(default=0)
    conversation_turns: Mapped[int] = mapped_column(default=0)
    summary: Mapped[dict | None] = mapped_column(JSONB_OR_JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

(`Vocab`/`GrammarPoint` 本 Task 不动。)

- [ ] **Step 4: 注册新模型到 models 包**

编辑 `backend/app/models/__init__.py`,加 learning 导入与 `__all__`:

```python
from app.models.auth import User
from app.models.content import Episode, Line, Scene, Series
from app.models.game import PlayerStats, TowerProgress
from app.models.learning import UserGrammarSrs, UserVocabSrs
from app.models.study import AppSetting, DailySession, GrammarPoint, Vocab

__all__ = [
    "Series", "Episode", "Line", "Scene",
    "Vocab", "GrammarPoint", "DailySession", "AppSetting",
    "TowerProgress", "PlayerStats",
    "User", "UserVocabSrs", "UserGrammarSrs",
]
```

- [ ] **Step 5: Write the failing test (learning_repo)**

创建 `backend/tests/test_learning_repo.py`:

```python
from app.models import GrammarPoint, User, Vocab
from app.services import learning_repo


def _user(db, name="u1"):
    u = User(username=name, password_hash="x")
    db.add(u)
    db.commit()
    return u


def test_get_or_create_vocab_srs_creates_once(db_session):
    u = _user(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    db_session.add(v)
    db_session.commit()
    row1 = learning_repo.get_or_create_vocab_srs(db_session, u.id, v.id)
    db_session.commit()
    row2 = learning_repo.get_or_create_vocab_srs(db_session, u.id, v.id)
    assert row1.id == row2.id
    assert row1.user_id == u.id and row1.vocab_id == v.id
    assert row1.in_srs is False and row1.ease == 2.5


def test_get_or_create_grammar_srs_defaults_locked(db_session):
    u = _user(db_session)
    g = GrammarPoint(key="g1", name="〜g", jlpt_level="N5", explanation="x")
    db_session.add(g)
    db_session.commit()
    row = learning_repo.get_or_create_grammar_srs(db_session, u.id, g.id)
    assert row.status == "locked"
    assert row.grammar_id == g.id and row.user_id == u.id


def test_vocab_srs_isolated_per_user(db_session):
    a = _user(db_session, "a")
    b = _user(db_session, "b")
    v = Vocab(headword="犬", reading="いぬ", meaning_zh="狗")
    db_session.add(v)
    db_session.commit()
    ra = learning_repo.get_or_create_vocab_srs(db_session, a.id, v.id)
    rb = learning_repo.get_or_create_vocab_srs(db_session, b.id, v.id)
    db_session.commit()
    assert ra.id != rb.id
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_learning_repo.py -v`
Expected: FAIL,`No module named 'app.services.learning_repo'`。

- [ ] **Step 7: 实现 learning_repo**

创建 `backend/app/services/learning_repo.py`:

```python
from sqlalchemy.orm import Session

from app.models import UserGrammarSrs, UserVocabSrs


def get_or_create_vocab_srs(db: Session, user_id: int,
                            vocab_id: int) -> UserVocabSrs:
    row = db.query(UserVocabSrs).filter_by(
        user_id=user_id, vocab_id=vocab_id).one_or_none()
    if row is None:
        row = UserVocabSrs(user_id=user_id, vocab_id=vocab_id)
        db.add(row)
        db.flush()
    return row


def get_or_create_grammar_srs(db: Session, user_id: int,
                              grammar_id: int) -> UserGrammarSrs:
    row = db.query(UserGrammarSrs).filter_by(
        user_id=user_id, grammar_id=grammar_id).one_or_none()
    if row is None:
        row = UserGrammarSrs(user_id=user_id, grammar_id=grammar_id)
        db.add(row)
        db.flush()
    return row
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_learning_repo.py -v`
Expected: PASS(3 项)。

- [ ] **Step 9: 修旧的 game 模型测试(PlayerStats 需 user_id)**

编辑 `backend/tests/test_models_game.py`(因 `PlayerStats` 现要 `user_id`、`TowerProgress` 也要 `user_id`)。替换全文为:

```python
from app.models import PlayerStats, TowerProgress, User


def _user(db):
    u = User(username="u1", password_hash="x")
    db.add(u)
    db.commit()
    return u


def test_tower_progress_persists(db_session):
    u = _user(db_session)
    p = TowerProgress(user_id=u.id, level="N5", zone_idx=0, stage_idx=1,
                      is_boss=False, cleared=True, stars=2, best_accuracy=0.8,
                      attempts=1)
    db_session.add(p)
    db_session.commit()
    got = db_session.query(TowerProgress).one()
    assert got.level == "N5" and got.stars == 2 and got.is_boss is False


def test_player_stats_defaults(db_session):
    u = _user(db_session)
    s = PlayerStats(user_id=u.id)
    db_session.add(s)
    db_session.commit()
    got = db_session.query(PlayerStats).filter_by(user_id=u.id).one()
    assert got.total_xp == 0
    assert got.player_level == 1
```

- [ ] **Step 10: 写 Alembic 0003**

创建 `backend/migrations/versions/0003_user_scoping.py`:

```python
"""user scoping: User + per-user srs tables + user_id on game/daily

Revision ID: 0003_user_scoping
Revises: 0002_pg_trgm
"""
import sqlalchemy as sa
from alembic import op

revision = "0003_user_scoping"
down_revision = "0002_pg_trgm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String, nullable=False, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_user_username", "user", ["username"])

    op.create_table(
        "user_vocab_srs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"),
                  nullable=False),
        sa.Column("vocab_id", sa.Integer, sa.ForeignKey("vocab.id"),
                  nullable=False),
        sa.Column("in_srs", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ease", sa.Float, nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date),
        sa.Column("last_reviewed", sa.DateTime),
        sa.UniqueConstraint("user_id", "vocab_id", name="uq_user_vocab"),
    )
    op.create_index("ix_user_vocab_srs_user_id", "user_vocab_srs", ["user_id"])
    op.create_index("ix_user_vocab_srs_vocab_id", "user_vocab_srs", ["vocab_id"])

    op.create_table(
        "user_grammar_srs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"),
                  nullable=False),
        sa.Column("grammar_id", sa.Integer, sa.ForeignKey("grammar_point.id"),
                  nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="locked"),
        sa.Column("in_srs", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ease", sa.Float, nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date),
        sa.Column("last_reviewed", sa.DateTime),
        sa.UniqueConstraint("user_id", "grammar_id", name="uq_user_grammar"),
    )
    op.create_index("ix_user_grammar_srs_user_id", "user_grammar_srs", ["user_id"])
    op.create_index("ix_user_grammar_srs_grammar_id", "user_grammar_srs",
                    ["grammar_id"])

    # tower_progress: 加 user_id + 改唯一约束
    with op.batch_alter_table("tower_progress") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer,
                                   sa.ForeignKey("user.id")))
        batch.drop_constraint("uq_tower_cell", type_="unique")
        batch.create_unique_constraint(
            "uq_tower_cell",
            ["user_id", "level", "zone_idx", "stage_idx", "is_boss"])
    op.create_index("ix_tower_progress_user_id", "tower_progress", ["user_id"])

    # player_stats: 加 user_id(unique);fresh,无回填
    with op.batch_alter_table("player_stats") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer,
                                   sa.ForeignKey("user.id")))
        batch.create_unique_constraint("uq_player_user", ["user_id"])

    # daily_session: 去掉 date 单列唯一,加 user_id + (user_id,date) 唯一
    with op.batch_alter_table("daily_session") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer,
                                   sa.ForeignKey("user.id")))
        batch.drop_constraint("daily_session_date_key", type_="unique")
        batch.create_unique_constraint("uq_daily_user_date", ["user_id", "date"])
    op.create_index("ix_daily_session_user_id", "daily_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_session_user_id", "daily_session")
    with op.batch_alter_table("daily_session") as batch:
        batch.drop_constraint("uq_daily_user_date", type_="unique")
        batch.create_unique_constraint("daily_session_date_key", ["date"])
        batch.drop_column("user_id")

    with op.batch_alter_table("player_stats") as batch:
        batch.drop_constraint("uq_player_user", type_="unique")
        batch.drop_column("user_id")

    op.drop_index("ix_tower_progress_user_id", "tower_progress")
    with op.batch_alter_table("tower_progress") as batch:
        batch.drop_constraint("uq_tower_cell", type_="unique")
        batch.create_unique_constraint(
            "uq_tower_cell", ["level", "zone_idx", "stage_idx", "is_boss"])
        batch.drop_column("user_id")

    op.drop_table("user_grammar_srs")
    op.drop_table("user_vocab_srs")
    op.drop_index("ix_user_username", "user")
    op.drop_table("user")
```

> 注意:`daily_session_date_key` 是 0001 经 metadata `create_all` 生成的列级唯一约束名(sqlite 上由 batch_alter 重建,约束名由 alembic 处理)。若 `drop_constraint` 在 sqlite 报「约束不存在」,batch_alter_table 会以重建表方式执行,通常可处理命名约束;运行 Step 12 验证。若失败,改为 `batch.recreate="always"`:把 `with op.batch_alter_table("daily_session") as batch:` 改为 `with op.batch_alter_table("daily_session", recreate="always") as batch:` 并在该块内省略 `drop_constraint`(重建时旧的单列唯一不会被复制,因为新表 schema 由 reflect 来——为稳妥,直接对三处 batch 块都加 `recreate="always"`,并删掉所有 `drop_constraint("...date_key"...)`/`drop_constraint("uq_tower_cell"...)` 行,只保留 add_column + create_unique_constraint;downgrade 同理)。

- [ ] **Step 11: 更新迁移测试期望表集合**

编辑 `backend/tests/test_migrations.py`,把 `_EXPECTED` 加入新表:

```python
_EXPECTED = {
    "series", "episode", "line", "scene", "vocab", "grammar_point",
    "daily_session", "app_setting", "tower_progress", "player_stats",
    "user", "user_vocab_srs", "user_grammar_srs",
    "alembic_version",
}
```

- [ ] **Step 12: 跑迁移测试(upgrade/downgrade)**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_migrations.py -v`
Expected: PASS。若 downgrade 因约束名失败,按 Step 10 注释切到 `recreate="always"` 再重跑直到绿。

- [ ] **Step 13: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿。`conftest` 的 `db_session` 用 `init_db`(metadata create_all)建表,自动含新表。

- [ ] **Step 14: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/models/learning.py app/models/__init__.py app/models/game.py app/models/study.py app/services/learning_repo.py migrations/versions/0003_user_scoping.py tests/test_learning_repo.py tests/test_models_game.py tests/test_migrations.py
git commit -m "feat(learning): per-user srs tables, user_id on game/daily, alembic 0003"
```

---

## Task 4: srs 服务/接口 user-scoped

**Files:**
- Modify: `backend/app/services/srs.py`
- Modify: `backend/app/api/srs.py`
- Modify: `backend/app/api/study.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_srs.py`
- Modify: `backend/tests/test_api_srs.py`
- Modify: `backend/tests/test_api_study.py`

**Interfaces:**
- Consumes: `learning_repo.get_or_create_*_srs`(Task 3),`get_current_user`(Task 2),`UserVocabSrs`/`UserGrammarSrs`。
- Produces:
  - `conftest` 新夹具 `auth_client` —— 注册一个用户、返回 `(TestClient_with_auth_header, user)`。
  - `apply_review(item, grade, today=None)` 不变(继续按鸭子类型作用于带 SRS 字段的行,现传 `UserVocabSrs`/`UserGrammarSrs` 行)。
  - `/api/srs/due`、`/api/srs/review`、`/api/study/*/add-srs` 全部经 `Depends(get_current_user)`,读写 `user_*_srs`。

- [ ] **Step 1: 在 conftest 加 auth_client 夹具**

编辑 `backend/tests/conftest.py`,在文件末尾(`client` 夹具之后)追加:

```python
@pytest.fixture
def auth_user(db_session):
    """注册一个测试用户,返回该 User。"""
    from app.models import User
    from app.services.auth import hash_password
    u = User(username="tester", password_hash=hash_password("pw123456"))
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def auth_client(client, auth_user):
    """带 Authorization 头的 TestClient(已登录 auth_user)。"""
    from app.services.auth import create_access_token
    token = create_access_token(auth_user.id)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
```

(`TestClient.headers` 是可变 `httpx.Headers`,`update` 后所有请求默认带该头。)

- [ ] **Step 2: Write the failing test (srs service, user-scoped)**

替换 `backend/tests/test_srs.py` 中 `test_apply_review_mutates_model` 为对 `UserVocabSrs` 行操作(纯 SM-2 测试 `test_new_card_good_then_good` 等不变,保留)。替换该函数为:

```python
def test_apply_review_mutates_user_srs_row(db_session):
    from app.models import User, UserVocabSrs, Vocab
    u = User(username="u1", password_hash="x")
    v = Vocab(headword="本", reading="ほん", meaning_zh="书")
    db_session.add_all([u, v])
    db_session.commit()
    row = UserVocabSrs(user_id=u.id, vocab_id=v.id, in_srs=True)
    db_session.add(row)
    db_session.commit()
    apply_review(row, "good", today=date(2026, 5, 22))
    assert row.interval_days == 1
    assert row.due_date == date(2026, 5, 23)
    assert row.last_reviewed is not None
```

(同时把文件顶部 `from app.models import Vocab` 删除——已在新测试内局部导入;若其他保留测试不用 Vocab,删之。检查:`test_*` SM-2 纯函数测试不引用 Vocab,可安全删顶部导入。)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_srs.py::test_apply_review_mutates_user_srs_row -v`
Expected: PASS(`apply_review` 鸭子类型本就适用)。若失败先修;此步主要确认新测试可跑。

- [ ] **Step 4: srs.py 的 apply_review 注释更新(逻辑不变)**

编辑 `backend/app/services/srs.py`,把 `apply_review` 的 docstring 改为:

```python
def apply_review(item, grade: str, today: date | None = None) -> None:
    """把一次复习评分应用到带 SRS 字段的行（UserVocabSrs / UserGrammarSrs，鸭子类型）。"""
```

(函数体不变。)

- [ ] **Step 5: Write the failing test (api/srs user-scoped + isolation)**

替换 `backend/tests/test_api_srs.py` 全文为:

```python
from datetime import date

from app.models import GrammarPoint, User, UserVocabSrs, Vocab
from app.services.auth import create_access_token


def _enroll(db, user_id, vocab_id, due):
    db.add(UserVocabSrs(user_id=user_id, vocab_id=vocab_id, in_srs=True,
                        due_date=due))
    db.commit()


def test_due_requires_auth(client):
    assert client.get("/api/srs/due").status_code == 401


def test_due_lists_only_due_in_srs_for_current_user(auth_client, auth_user,
                                                    db_session):
    today = date.today()
    cat = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    dog = Vocab(headword="犬", reading="いぬ", meaning_zh="狗")
    db_session.add_all([cat, dog])
    db_session.commit()
    _enroll(db_session, auth_user.id, cat.id, today)
    body = auth_client.get("/api/srs/due").json()
    heads = [v["headword"] for v in body["vocab"]]
    assert heads == ["猫"]


def test_review_vocab_advances_user_state(auth_client, auth_user, db_session):
    today = date.today()
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    db_session.add(v)
    db_session.commit()
    _enroll(db_session, auth_user.id, v.id, today)
    resp = auth_client.post("/api/srs/review",
                            json={"item_type": "vocab", "item_id": v.id,
                                  "grade": "good"})
    assert resp.status_code == 200
    row = db_session.query(UserVocabSrs).filter_by(
        user_id=auth_user.id, vocab_id=v.id).one()
    assert row.interval_days == 1 and row.reps == 1


def test_review_rejects_bad_grade(auth_client, auth_user, db_session):
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    db_session.add(v)
    db_session.commit()
    _enroll(db_session, auth_user.id, v.id, date.today())
    resp = auth_client.post("/api/srs/review",
                            json={"item_type": "vocab", "item_id": v.id,
                                  "grade": "perfect"})
    assert resp.status_code == 422


def test_due_is_isolated_between_users(auth_client, auth_user, db_session):
    today = date.today()
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    other = User(username="other", password_hash="x")
    db_session.add_all([v, other])
    db_session.commit()
    _enroll(db_session, other.id, v.id, today)   # 仅 other 入池
    body = auth_client.get("/api/srs/due").json()
    assert body["vocab"] == []
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_api_srs.py -v`
Expected: FAIL(当前 `/api/srs/due` 无鉴权、读 `Vocab.in_srs`)。

- [ ] **Step 7: 重写 api/srs.py user-scoped**

替换 `backend/app/api/srs.py` 全文为:

```python
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import (
    GrammarPoint,
    Line,
    User,
    UserGrammarSrs,
    UserVocabSrs,
    Vocab,
)
from app.services.srs import apply_review

router = APIRouter(prefix="/api/srs", tags=["srs"])


@router.get("/due")
def due(user: User = Depends(get_current_user),
        db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vrows = (
        db.query(UserVocabSrs, Vocab)
        .join(Vocab, Vocab.id == UserVocabSrs.vocab_id)
        .filter(UserVocabSrs.user_id == user.id,
                UserVocabSrs.in_srs.is_(True),
                UserVocabSrs.due_date <= today)
        .order_by(UserVocabSrs.due_date)
        .all()
    )
    grows = (
        db.query(GrammarPoint)
        .join(UserGrammarSrs, UserGrammarSrs.grammar_id == GrammarPoint.id)
        .filter(UserGrammarSrs.user_id == user.id,
                UserGrammarSrs.in_srs.is_(True),
                UserGrammarSrs.due_date <= today)
        .order_by(UserGrammarSrs.due_date)
        .all()
    )
    vocab_out = []
    for _row, v in vrows:
        line = db.get(Line, v.source_line_id) if v.source_line_id else None
        vocab_out.append({
            "id": v.id, "headword": v.headword, "reading": v.reading,
            "meaning_zh": v.meaning_zh, "pos": v.pos,
            "context": line.text_jp if line else None,
        })
    grammar_out = [
        {"id": g.id, "key": g.key, "name": g.name, "jlpt_level": g.jlpt_level,
         "explanation": g.explanation}
        for g in grows
    ]
    return {"vocab": vocab_out, "grammar": grammar_out}


class ReviewBody(BaseModel):
    item_type: Literal["vocab", "grammar"]
    item_id: int
    grade: Literal["again", "hard", "good", "easy"]


@router.post("/review")
def review(body: ReviewBody, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> dict:
    if body.item_type == "vocab":
        row = db.query(UserVocabSrs).filter_by(
            user_id=user.id, vocab_id=body.item_id).one_or_none()
    else:
        row = db.query(UserGrammarSrs).filter_by(
            user_id=user.id, grammar_id=body.item_id).one_or_none()
    if row is None:
        raise HTTPException(404, "复习项不存在")
    apply_review(row, body.grade)
    db.commit()
    return {"id": body.item_id, "interval_days": row.interval_days,
            "reps": row.reps, "due_date": row.due_date.isoformat()}
```

- [ ] **Step 8: 重写 api/study.py 的 add-srs(其余路由保留)**

编辑 `backend/app/api/study.py`。改 import 与两个 add-srs 路由;`reading-progress`、`complete-today` 路由本 Task 暂不动(complete-today 在 Task 6 切),其余只加 import。把文件改为:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Episode, GrammarPoint, User, Vocab
from app.services import learning_repo
from app.services import session as sess

router = APIRouter(prefix="/api/study", tags=["study"])


@router.post("/vocab/{vocab_id}/add-srs")
def add_vocab(vocab_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    v = db.get(Vocab, vocab_id)
    if v is None:
        raise HTTPException(404, "词条不存在")
    row = learning_repo.get_or_create_vocab_srs(db, user.id, vocab_id)
    row.in_srs = True
    if row.due_date is None:
        row.due_date = date.today()
    db.commit()
    return {"id": v.id, "in_srs": True}


@router.post("/grammar/{grammar_id}/add-srs")
def add_grammar(grammar_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    gp = db.get(GrammarPoint, grammar_id)
    if gp is None:
        raise HTTPException(404, "语法点不存在")
    row = learning_repo.get_or_create_grammar_srs(db, user.id, grammar_id)
    row.in_srs = True
    row.status = "learning"
    if row.due_date is None:
        row.due_date = date.today()
    db.commit()
    return {"id": gp.id, "in_srs": True, "status": row.status}


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
def complete_today(body: CompleteToday,
                   user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    stats = body.model_dump(exclude={"episode_id"}, exclude_none=True)
    sess.record_completion(db, user.id, today_d, body.episode_id, stats)
    return {"streak": sess.compute_streak(db, user.id, today_d)}
```

> 注意:此处已把 `complete-today` 改为 user-scoped 并调用新签名 `record_completion(db, user_id, today, episode_id, stats)` 与 `compute_streak(db, user_id, today)`。**这两个 session.py 函数将在 Task 6 改签名**。为避免本 Task 测试红,本 Task 在 Step 9 同步改 `session.py` 的这两个函数签名(只加 `user_id` 形参,内部 filter 加 `user_id`),`due_counts` 留到 Task 6。

- [ ] **Step 9: 同步改 session.py 的 record_completion / compute_streak 签名**

编辑 `backend/app/services/session.py`,替换 `compute_streak` 与 `record_completion` 两个函数为:

```python
def compute_streak(session: Session, user_id: int, today: date) -> int:
    """连续打卡天数：从 today 往回数当前用户连续 completed 的 DailySession。"""
    completed = {
        r.date
        for r in session.query(DailySession)
        .filter_by(user_id=user_id, completed=True).all()
    }
    streak = 0
    cursor = today
    while cursor in completed:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def record_completion(session: Session, user_id: int, today: date,
                      episode_id: int | None, stats: dict) -> DailySession:
    """记录/更新当前用户今天的训练完成情况（按 user+date upsert）。"""
    row = session.query(DailySession).filter_by(
        user_id=user_id, date=today).first()
    if row is None:
        row = DailySession(user_id=user_id, date=today)
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

(`due_counts`、`current_episode` 本 Task 不动;`due_counts` 仍引用 `Vocab.in_srs`——Task 6 改。)

- [ ] **Step 10: 更新 test_session.py 的 streak/record 测试签名**

编辑 `backend/tests/test_session.py`。在文件顶部 import 加 `User`,并改 `test_compute_streak` 与 `test_record_completion_upserts` 传 `user_id`。把这两个函数替换为:

```python
def test_compute_streak(db_session):
    from app.models import User
    u = User(username="u1", password_hash="x")
    db_session.add(u)
    db_session.commit()
    today = date(2026, 5, 22)
    for d in (today, today - timedelta(days=1), today - timedelta(days=2)):
        db_session.add(DailySession(user_id=u.id, date=d, completed=True))
    db_session.add(DailySession(user_id=u.id, date=today - timedelta(days=4),
                                completed=True))
    db_session.commit()
    assert sess.compute_streak(db_session, u.id, today) == 3


def test_record_completion_upserts(db_session):
    from app.models import User
    u = User(username="u1", password_hash="x")
    db_session.add(u)
    db_session.commit()
    today = date(2026, 5, 22)
    sess.record_completion(db_session, u.id, today, episode_id=None,
                           stats={"vocab_reviewed": 5})
    row = db_session.query(DailySession).filter_by(
        user_id=u.id, date=today).one()
    assert row.completed is True and row.vocab_reviewed == 5
    sess.record_completion(db_session, u.id, today, episode_id=None,
                           stats={"vocab_reviewed": 9})
    assert db_session.query(DailySession).filter_by(
        user_id=u.id, date=today).count() == 1
    assert db_session.query(DailySession).filter_by(
        user_id=u.id, date=today).one().vocab_reviewed == 9
```

(`test_due_counts`、`test_current_episode_picks_current_series_unfinished` 不动。)

- [ ] **Step 11: 更新 test_api_study.py 用 auth_client**

替换 `backend/tests/test_api_study.py` 全文为:

```python
from app.models import Episode, GrammarPoint, Line, Series, UserGrammarSrs, UserVocabSrs, Vocab


def _ready_episode(db_session):
    s = Series(title="番", is_current=True)
    ep = Episode(series=s, number=1, source="upload", status="ready",
                 total_lines=1, reading_done=False)
    ln = Line(episode=ep, idx=0, text_jp="猫が好き", processed=True,
              grammar_point_keys=["mai"])
    db_session.add(s)
    db_session.commit()
    return ep, ln


def test_add_vocab_requires_auth(client, db_session):
    ep, ln = _ready_episode(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", source_line_id=ln.id)
    db_session.add(v)
    db_session.commit()
    assert client.post(f"/api/study/vocab/{v.id}/add-srs").status_code == 401


def test_add_vocab_to_srs(auth_client, auth_user, db_session):
    ep, ln = _ready_episode(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", source_line_id=ln.id)
    db_session.add(v)
    db_session.commit()
    resp = auth_client.post(f"/api/study/vocab/{v.id}/add-srs")
    assert resp.status_code == 200
    row = db_session.query(UserVocabSrs).filter_by(
        user_id=auth_user.id, vocab_id=v.id).one()
    assert row.in_srs is True and row.due_date is not None


def test_add_grammar_to_srs(auth_client, auth_user, db_session):
    gp = GrammarPoint(key="mai", name="〜まい", jlpt_level="N2",
                      explanation="x")
    db_session.add(gp)
    db_session.commit()
    resp = auth_client.post(f"/api/study/grammar/{gp.id}/add-srs")
    assert resp.status_code == 200
    row = db_session.query(UserGrammarSrs).filter_by(
        user_id=auth_user.id, grammar_id=gp.id).one()
    assert row.in_srs is True and row.status == "learning"


def test_reading_progress_and_complete(auth_client, auth_user, db_session):
    ep, _ = _ready_episode(db_session)
    auth_client.post(f"/api/study/episodes/{ep.id}/reading-progress",
                     json={"position": 1})
    db_session.refresh(ep)
    assert ep.read_position == 1

    resp = auth_client.post("/api/study/complete-today",
                            json={"episode_id": ep.id, "vocab_reviewed": 3})
    assert resp.status_code == 200
    assert resp.json()["streak"] >= 1
```

> 说明:`GrammarPoint` 构造去掉了 `status="seen"`(Task 7 才删列,但此处构造不传也合法;保持向前兼容)。

- [ ] **Step 12: 跑相关测试**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_srs.py tests/test_api_srs.py tests/test_api_study.py tests/test_session.py -v`
Expected: PASS。

- [ ] **Step 13: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿。

- [ ] **Step 14: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/services/srs.py app/services/session.py app/api/srs.py app/api/study.py tests/conftest.py tests/test_srs.py tests/test_api_srs.py tests/test_api_study.py tests/test_session.py
git commit -m "feat(srs): user-scoped due/review/add-srs via learning_repo + auth_client fixture"
```

---

## Task 5: tower 服务/接口 user-scoped

**Files:**
- Modify: `backend/app/services/tower.py`
- Modify: `backend/app/api/tower.py`
- Modify: `backend/tests/test_tower.py`
- Modify: `backend/tests/test_api_tower.py`

**Interfaces:**
- Consumes: `learning_repo.get_or_create_*_srs`、`get_current_user`、`UserVocabSrs`/`UserGrammarSrs`。
- Produces(签名加 `user_id`):
  - `submit_result(db, user_id, level, zone_idx, stage_idx, is_boss, results, today=None) -> dict`
  - `tower_map(db, user_id) -> dict`
  - `is_cell_unlocked(db, user_id, level, zone_idx, stage_idx, is_boss) -> bool`
  - 内部 helper:`_progress_index(db, user_id)`、`_is_cleared` 不变、`_get_or_create_progress(db, user_id, ...)`、`_player(db, user_id)`。
  - tower XP 加成判定改为:vocab 仍按 `source_line_id`;**grammar 加成本期失效**(per-user status 默认 locked,无 seen),即 grammar 永远按 1.0 倍——见 Task 7 说明,本 Task 已生效。

- [ ] **Step 1: Write the failing test (tower service, user-scoped)**

替换 `backend/tests/test_tower.py` 全文为(保留切片/星级/quiz 纯逻辑测试,提交类测试改带 user_id;grammar 加成测试改为「本期 grammar 无加成」):

```python
import random
from datetime import date

import pytest

from app.models import GrammarPoint, PlayerStats, TowerProgress, User, UserVocabSrs, Vocab
from app.services import tower
from app.services.tower import LockedStageError


def _user(db, name="u1"):
    u = User(username=name, password_hash="x")
    db.add(u)
    db.commit()
    return u


def _seed_level(db, n_vocab=20, n_gram=6, level="N5"):
    prefix = level
    for i in range(n_vocab):
        db.add(Vocab(headword=f"{prefix}語{i}", reading=f"{prefix}よ{i}",
                     meaning_zh=f"义{level}{i}", pos="名", jlpt_level=level))
    for i in range(n_gram):
        db.add(GrammarPoint(key=f"{level}-g{i}", name=f"〜文法{level}{i}",
                            jlpt_level=level, explanation=f"含义{level}{i}",
                            curated=True))
    db.commit()


def test_stage_slice_sizes(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    v, g = tower.stage_items(db_session, "N5", 0, 0)
    assert [x.headword for x in v] == [f"N5語{i}" for i in range(8)]
    assert [x.name for x in g] == ["〜文法N50", "〜文法N51"]
    v2, _ = tower.stage_items(db_session, "N5", 0, 1)
    assert [x.headword for x in v2] == [f"N5語{i}" for i in range(8, 16)]


def test_zone_items_unions_five_stages(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    v, g = tower.zone_items(db_session, "N5", 0)
    assert len(v) == 40 and len(g) == 10


def test_stars_for_thresholds():
    assert tower.stars_for(1.0) == 3
    assert tower.stars_for(0.8) == 2
    assert tower.stars_for(0.6) == 1
    assert tower.stars_for(0.59) == 0


def test_build_quiz_stage_has_questions(db_session):
    _seed_level(db_session, n_vocab=20, n_gram=6)
    qs = tower.build_quiz(db_session, "N5", 0, 0, False, random.Random(1))
    assert len(qs) == 10
    assert all(q["answer"] in q["options"] for q in qs)
    assert {q["item"]["kind"] for q in qs} == {"vocab", "grammar"}


def test_build_quiz_boss_is_bigger(db_session):
    _seed_level(db_session, n_vocab=60, n_gram=20)
    qs = tower.build_quiz(db_session, "N5", 0, 0, True, random.Random(1))
    assert len(qs) >= 15


def test_submit_updates_progress_xp_and_srs(db_session):
    u = _user(db_session)
    v = Vocab(headword="飲む", reading="のむ", meaning_zh="喝", pos="他動1",
              jlpt_level="N5", source_line_id=None)
    g = GrammarPoint(key="N5-g0", name="〜て", jlpt_level="N5",
                     explanation="表示", curated=True)
    db_session.add_all([v, g])
    db_session.commit()

    results = [
        {"item": {"kind": "vocab", "id": v.id}, "correct": True},
        {"item": {"kind": "grammar", "id": g.id}, "correct": False},
    ]
    out = tower.submit_result(db_session, u.id, "N5", 0, 0, False, results,
                              today=date(2026, 6, 25))

    assert out["accuracy"] == 0.5
    assert out["stars"] == 0 and out["passed"] is False
    assert out["xp_gained"] == 10
    tp = db_session.query(TowerProgress).filter_by(
        user_id=u.id, level="N5", zone_idx=0, stage_idx=0, is_boss=False).one()
    assert tp.attempts == 1 and tp.best_accuracy == 0.5
    from app.models import UserGrammarSrs
    vr = db_session.query(UserVocabSrs).filter_by(
        user_id=u.id, vocab_id=v.id).one()
    assert vr.in_srs is True
    gr = db_session.query(UserGrammarSrs).filter_by(
        user_id=u.id, grammar_id=g.id).one()
    assert gr.in_srs is True and gr.status == "learning"
    assert gr.due_date == date(2026, 6, 25)


def test_submit_vocab_anime_bonus(db_session):
    u = _user(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", pos="名",
              jlpt_level="N5", source_line_id=999)  # 番剧词
    db_session.add(v)
    db_session.commit()
    out = tower.submit_result(db_session, u.id, "N5", 0, 0, False,
                              [{"item": {"kind": "vocab", "id": v.id},
                                "correct": True}], today=date(2026, 6, 25))
    assert out["xp_gained"] == 15  # 10 × 1.5 番剧加成
    assert out["stars"] == 3 and out["passed"] is True


def test_submit_keeps_best(db_session):
    u = _user(db_session)
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫", pos="名",
              jlpt_level="N5", source_line_id=999)
    db_session.add(v)
    db_session.commit()
    tower.submit_result(db_session, u.id, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": v.id},
                          "correct": True}], today=date(2026, 6, 25))
    tower.submit_result(db_session, u.id, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": v.id},
                          "correct": False}], today=date(2026, 6, 25))
    tp = db_session.query(TowerProgress).filter_by(
        user_id=u.id, level="N5", zone_idx=0, stage_idx=0, is_boss=False).one()
    assert tp.stars == 3 and tp.best_accuracy == 1.0 and tp.attempts == 2


def test_tower_map_initial_locks(db_session):
    u = _user(db_session)
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")
    m = tower.tower_map(db_session, u.id)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["unlocked"] is True
    stage0 = n5["zones"][0]["stages"][0]
    assert stage0["unlocked"] is True and stage0["stage_idx"] == 0
    stage1 = n5["zones"][0]["stages"][1]
    assert stage1["unlocked"] is False
    n4 = next(lv for lv in m["levels"] if lv["level"] == "N4")
    assert n4["unlocked"] is False


def test_tower_map_unlocks_next_after_clear(db_session):
    u = _user(db_session)
    _seed_level(db_session, n_vocab=60, n_gram=20, level="N5")
    tower.submit_result(db_session, u.id, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab",
                          "id": db_session.query(Vocab).first().id},
                          "correct": True}])
    m = tower.tower_map(db_session, u.id)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["zones"][0]["stages"][1]["unlocked"] is True


def test_submit_rejects_locked_stage(db_session):
    u = _user(db_session)
    _seed_level(db_session, n_vocab=20, n_gram=6, level="N5")
    vid = db_session.query(Vocab).first().id
    results = [{"item": {"kind": "vocab", "id": vid}, "correct": True}]
    with pytest.raises(LockedStageError):
        tower.submit_result(db_session, u.id, "N5", 0, 1, False, results)
    assert db_session.query(TowerProgress).count() == 0
    assert db_session.query(PlayerStats).filter_by(user_id=u.id).first() is None


def test_submit_unlocked_stage0_passes(db_session):
    u = _user(db_session)
    _seed_level(db_session, n_vocab=20, n_gram=6, level="N5")
    vid = db_session.query(Vocab).first().id
    out = tower.submit_result(db_session, u.id, "N5", 0, 0, False,
                              [{"item": {"kind": "vocab", "id": vid},
                                "correct": True}])
    assert out["passed"] is True


def _pass_stage(db, user_id, level, zone_idx, stage_idx, is_boss=False):
    vocab = db.query(Vocab).filter_by(jlpt_level=level).first()
    tower.submit_result(db, user_id, level, zone_idx, stage_idx, is_boss,
                        [{"item": {"kind": "vocab", "id": vocab.id},
                          "correct": True}])


def test_tower_map_multizone_level_unlock(db_session):
    u = _user(db_session)
    _seed_level(db_session, n_vocab=80, n_gram=20, level="N5")
    _seed_level(db_session, n_vocab=8, n_gram=2, level="N4")
    for s in range(5):
        _pass_stage(db_session, u.id, "N5", 0, s, False)
    _pass_stage(db_session, u.id, "N5", 0, 0, True)
    m = tower.tower_map(db_session, u.id)
    n5 = next(lv for lv in m["levels"] if lv["level"] == "N5")
    assert n5["zones"][1]["stages"][0]["unlocked"] is True
    n4 = next(lv for lv in m["levels"] if lv["level"] == "N4")
    assert n4["unlocked"] is False
    for s in range(5):
        _pass_stage(db_session, u.id, "N5", 1, s, False)
    _pass_stage(db_session, u.id, "N5", 1, 0, True)
    m2 = tower.tower_map(db_session, u.id)
    n4_2 = next(lv for lv in m2["levels"] if lv["level"] == "N4")
    assert n4_2["unlocked"] is True


def test_tower_is_isolated_between_users(db_session):
    a = _user(db_session, "a")
    b = _user(db_session, "b")
    _seed_level(db_session, n_vocab=20, n_gram=6, level="N5")
    vid = db_session.query(Vocab).first().id
    tower.submit_result(db_session, a.id, "N5", 0, 0, False,
                        [{"item": {"kind": "vocab", "id": vid},
                          "correct": True}])
    # b 的地图 stage1 仍锁
    mb = tower.tower_map(db_session, b.id)
    n5b = next(lv for lv in mb["levels"] if lv["level"] == "N5")
    assert n5b["zones"][0]["stages"][1]["unlocked"] is False
    # b 无 PlayerStats / 无 TowerProgress
    assert db_session.query(PlayerStats).filter_by(user_id=b.id).first() is None
    assert db_session.query(TowerProgress).filter_by(user_id=b.id).count() == 0
```

> 删去了原 `test_best_accuracy_strict_greater_equal_does_not_overwrite` 与 `test_grammar_anime_bonus_uses_original_status`:前者由 `test_submit_keeps_best` 覆盖严格大于语义;后者因 grammar 加成本期失效不再适用。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_tower.py -v`
Expected: FAIL(`submit_result`/`tower_map` 旧签名无 user_id)。

- [ ] **Step 3: 重写 tower.py 的 progress/player/submit/map/unlock 部分**

编辑 `backend/app/services/tower.py`。顶部 import 加 learning_repo;替换 `_is_cleared` 之后到 `tower_map` 之间的相关函数。具体改动:

(a) 顶部 import 块改为:

```python
from datetime import date as _date
from math import ceil

from sqlalchemy import select

from app.models import GrammarPoint, PlayerStats, TowerProgress, Vocab
from app.services import learning_repo
from app.services.quiz_bank import make_grammar_question, make_vocab_question
```

(b) 替换 `is_cell_unlocked` 签名首行与首句:

```python
def is_cell_unlocked(db, user_id, level, zone_idx, stage_idx, is_boss) -> bool:
    """判断给定关卡是否已解锁。规则与 tower_map 完全一致。"""
    idx = _progress_index(db, user_id)
```

(其余函数体不变。)

(c) 替换 `_get_or_create_progress` 与 `_player`:

```python
def _get_or_create_progress(db, user_id, level, zone_idx, stage_idx, is_boss):
    tp = db.query(TowerProgress).filter_by(
        user_id=user_id, level=level, zone_idx=zone_idx,
        stage_idx=stage_idx, is_boss=is_boss).one_or_none()
    if tp is None:
        tp = TowerProgress(user_id=user_id, level=level, zone_idx=zone_idx,
                           stage_idx=stage_idx, is_boss=is_boss, cleared=False,
                           stars=0, best_accuracy=0.0, attempts=0)
        db.add(tp)
    return tp


def _player(db, user_id):
    p = db.query(PlayerStats).filter_by(user_id=user_id).one_or_none()
    if p is None:
        p = PlayerStats(user_id=user_id, total_xp=0, player_level=1)
        db.add(p)
    return p
```

(d) 替换 `submit_result` 全函数:

```python
def submit_result(db, user_id, level, zone_idx, stage_idx, is_boss, results,
                  today=None):
    if not is_cell_unlocked(db, user_id, level, zone_idx, stage_idx, is_boss):
        raise LockedStageError(
            f"关卡未解锁: {level} zone{zone_idx} stage{stage_idx} boss={is_boss}")
    today = today or _date.today()
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total else 0.0
    stars = stars_for(accuracy)
    passed = accuracy >= (BOSS_PASS if is_boss else STAGE_PASS)

    xp_gained = 0
    for r in results:
        kind, iid = r["item"]["kind"], r["item"]["id"]
        if kind == "vocab":
            knowledge = db.get(Vocab, iid)
            if knowledge is None:
                continue
            row = learning_repo.get_or_create_vocab_srs(db, user_id, iid)
        else:
            knowledge = db.get(GrammarPoint, iid)
            if knowledge is None:
                continue
            row = learning_repo.get_or_create_grammar_srs(db, user_id, iid)
            row.status = "learning"
        row.in_srs = True
        if not r["correct"]:
            row.due_date = today
        elif row.due_date is None:
            row.due_date = today
        if r["correct"]:
            if kind == "vocab":
                anime = getattr(knowledge, "source_line_id", None) is not None
            else:
                # 番剧加成依赖 per-user grammar 历史 status,本期默认 locked，暂无加成
                anime = False
            xp_gained += round(XP_PER_CORRECT * (1.5 if anime else 1))

    tp = _get_or_create_progress(db, user_id, level, zone_idx, stage_idx, is_boss)
    tp.attempts += 1
    if accuracy > tp.best_accuracy:
        tp.best_accuracy = accuracy
        tp.stars = stars
    if passed:
        tp.cleared = True

    player = _player(db, user_id)
    player.total_xp += xp_gained
    player.player_level = 1 + player.total_xp // 500

    db.commit()
    return {"stars": stars, "accuracy": accuracy, "passed": passed,
            "xp_gained": xp_gained, "total_xp": player.total_xp}
```

(e) 替换 `_progress_index` 与 `tower_map` 首行:

```python
def _progress_index(db, user_id):
    idx = {}
    for tp in db.query(TowerProgress).filter_by(user_id=user_id).all():
        idx[(tp.level, tp.zone_idx, tp.stage_idx, tp.is_boss)] = tp
    return idx


def tower_map(db, user_id):
    idx = _progress_index(db, user_id)
```

(`tower_map` 其余函数体不变;`build_quiz`、`level_items`、`stage_items`、`zone_items` 不变。)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_tower.py -v`
Expected: PASS。

- [ ] **Step 5: Write the failing test (api/tower)**

替换 `backend/tests/test_api_tower.py` 全文为:

```python
from app.models import GrammarPoint, PlayerStats, Vocab


def _seed(db, n_vocab=12, n_gram=4, level="N5"):
    for i in range(n_vocab):
        db.add(Vocab(headword=f"語{i}", reading=f"よ{i}", meaning_zh=f"義{i}",
                     pos="名", jlpt_level=level))
    for i in range(n_gram):
        db.add(GrammarPoint(key=f"{level}-g{i}", name=f"〜文法{i}",
                            jlpt_level=level, explanation=f"含義{i}",
                            curated=True))
    db.commit()


def test_tower_requires_auth(client):
    assert client.get("/api/tower").status_code == 401


def test_get_tower_map(auth_client, db_session):
    _seed(db_session)
    body = auth_client.get("/api/tower").json()
    assert body["levels"][0]["level"] == "N5"
    assert body["levels"][0]["unlocked"] is True


def test_submit_locked_returns_403(auth_client, db_session):
    _seed(db_session)
    vid = db_session.query(Vocab).first().id
    body = {"level": "N5", "zone": 0, "stage": 1, "boss": False,
            "results": [{"item": {"kind": "vocab", "id": vid}, "correct": True}]}
    assert auth_client.post("/api/tower/submit", json=body).status_code == 403


def test_get_quiz(auth_client, db_session):
    _seed(db_session)
    body = auth_client.get("/api/tower/quiz?level=N5&zone=0&stage=0").json()
    assert len(body["questions"]) >= 1
    q = body["questions"][0]
    assert q["answer"] in q["options"]
    assert q["item"]["kind"] in {"vocab", "grammar"}


def test_get_player_defaults(auth_client, db_session):
    body = auth_client.get("/api/player").json()
    assert body["total_xp"] == 0 and body["player_level"] == 1


def test_submit_quiz_updates_and_returns(auth_client, auth_user, db_session):
    _seed(db_session)
    vid = db_session.query(Vocab).first().id
    body = {"level": "N5", "zone": 0, "stage": 0, "boss": False,
            "results": [{"item": {"kind": "vocab", "id": vid}, "correct": True}]}
    out = auth_client.post("/api/tower/submit", json=body).json()
    assert out["stars"] == 3 and out["passed"] is True
    assert out["xp_gained"] == 10
    m = auth_client.get("/api/tower").json()
    assert m["levels"][0]["zones"][0]["stages"][1]["unlocked"] is True
    assert db_session.query(PlayerStats).filter_by(
        user_id=auth_user.id).one().total_xp == 10
```

- [ ] **Step 6: 重写 api/tower.py**

替换 `backend/app/api/tower.py` 全文为:

```python
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import PlayerStats, User
from app.services import tower
from app.services.tower import LockedStageError

router = APIRouter(tags=["tower"])


@router.get("/api/tower")
def get_tower(user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    return tower.tower_map(db, user.id)


@router.get("/api/tower/quiz")
def get_quiz(
    level: str = Query(...),
    zone: int = Query(0),
    stage: int = Query(0),
    boss: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    questions = tower.build_quiz(db, level, zone, stage, boss, random.Random())
    return {"questions": questions}


@router.get("/api/player")
def get_player(user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    p = db.query(PlayerStats).filter_by(user_id=user.id).one_or_none()
    return {"total_xp": p.total_xp if p else 0,
            "player_level": p.player_level if p else 1}


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
def submit(body: SubmitBody, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> dict:
    results = [{"item": {"kind": r.item.kind, "id": r.item.id},
                "correct": r.correct} for r in body.results]
    try:
        return tower.submit_result(db, user.id, body.level, body.zone,
                                   body.stage, body.boss, results)
    except LockedStageError:
        raise HTTPException(status_code=403, detail="关卡未解锁")
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_tower.py tests/test_api_tower.py -v`
Expected: PASS。

- [ ] **Step 8: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿。

- [ ] **Step 9: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/services/tower.py app/api/tower.py tests/test_tower.py tests/test_api_tower.py
git commit -m "feat(tower): user-scoped tower map/submit/player via learning_repo"
```

---

## Task 6: grammar/vocab/progress/today/session/conversation user-scoped

**Files:**
- Modify: `backend/app/services/session.py`
- Modify: `backend/app/api/grammar.py`
- Modify: `backend/app/api/vocab.py`
- Modify: `backend/app/api/progress.py`
- Modify: `backend/app/api/today.py`
- Modify: `backend/app/api/conversation.py`
- Modify: `backend/tests/test_session.py`
- Modify: `backend/tests/test_api_grammar.py`
- Modify: `backend/tests/test_api_vocab.py`
- Modify: `backend/tests/test_api_progress.py`
- Modify: `backend/tests/test_api_today_journey.py`
- Modify: `backend/tests/test_api_conversation.py`

**Interfaces:**
- Consumes: `learning_repo`、`get_current_user`、`UserVocabSrs`/`UserGrammarSrs`、`session.due_counts(db, user_id, today)`。
- Produces:
  - `session.due_counts(db, user_id, today) -> dict`(user-scoped)。
  - grammar checklist = `GrammarPoint` LEFT JOIN `UserGrammarSrs`(当前用户)→ `status`/`in_srs`/`mastered`。
  - vocab 列表/详情的 `in_srs` 按当前用户左联(列表里每项 `in_srs`)。
  - progress/today/conversation 全部 `Depends(get_current_user)`。

- [ ] **Step 1: 改 session.due_counts 签名**

编辑 `backend/app/services/session.py`,替换 `due_counts` 为(改读 `UserVocabSrs`/`UserGrammarSrs`):

```python
def due_counts(session: Session, user_id: int, today: date) -> dict:
    """当前用户到期待复习的词汇 / 语法数量。"""
    vocab = (
        session.query(UserVocabSrs)
        .filter(UserVocabSrs.user_id == user_id,
                UserVocabSrs.in_srs.is_(True),
                UserVocabSrs.due_date <= today)
        .count()
    )
    grammar = (
        session.query(UserGrammarSrs)
        .filter(UserGrammarSrs.user_id == user_id,
                UserGrammarSrs.in_srs.is_(True),
                UserGrammarSrs.due_date <= today)
        .count()
    )
    return {"vocab": vocab, "grammar": grammar}
```

并把文件顶部 import 改为:

```python
from app.models import (
    DailySession,
    Episode,
    Series,
    UserGrammarSrs,
    UserVocabSrs,
)
```

(`current_episode` 仍用 `Episode`/`Series`;不再需要 `GrammarPoint`/`Vocab`。)

- [ ] **Step 2: 更新 test_session.py 的 due_counts 测试**

编辑 `backend/tests/test_api`... 不,是 `backend/tests/test_session.py`。替换 `test_due_counts` 为:

```python
def test_due_counts(db_session):
    from app.models import GrammarPoint, User, UserGrammarSrs, UserVocabSrs, Vocab
    u = User(username="u1", password_hash="x")
    va = Vocab(headword="A", reading="あ", meaning_zh="a")
    vb = Vocab(headword="B", reading="び", meaning_zh="b")
    g1 = GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x")
    db_session.add_all([u, va, vb, g1])
    db_session.commit()
    today = date(2026, 5, 22)
    db_session.add_all([
        UserVocabSrs(user_id=u.id, vocab_id=va.id, in_srs=True, due_date=today),
        UserVocabSrs(user_id=u.id, vocab_id=vb.id, in_srs=True,
                     due_date=today + timedelta(days=3)),
        UserGrammarSrs(user_id=u.id, grammar_id=g1.id, in_srs=True,
                       due_date=today - timedelta(days=1)),
    ])
    db_session.commit()
    counts = sess.due_counts(db_session, u.id, today)
    assert counts["vocab"] == 1
    assert counts["grammar"] == 1
```

- [ ] **Step 3: 重写 api/grammar.py checklist**

替换 `backend/app/api/grammar.py` 全文为:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import GrammarPoint, User, UserGrammarSrs
from app.services import grammar_quiz
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/grammar", tags=["grammar"])


@router.get("/checklist")
def checklist(user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    """内置语法清单,按 JLPT 等级分组,带当前用户的掌握状态。"""
    rows = (
        db.query(GrammarPoint, UserGrammarSrs)
        .outerjoin(UserGrammarSrs,
                   (UserGrammarSrs.grammar_id == GrammarPoint.id)
                   & (UserGrammarSrs.user_id == user.id))
        .filter(GrammarPoint.curated.is_(True))
        .order_by(GrammarPoint.jlpt_level, GrammarPoint.id)
        .all()
    )
    grouped: dict[str, list[dict]] = {}
    for g, srs in rows:
        status = srs.status if srs else "locked"
        in_srs = bool(srs and srs.in_srs)
        mastered = in_srs and srs.interval_days >= MASTERED_INTERVAL
        grouped.setdefault(g.jlpt_level, []).append({
            "id": g.id, "key": g.key, "name": g.name,
            "explanation": g.explanation, "status": status,
            "in_srs": in_srs, "mastered": mastered,
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

> `quiz` 端点读 GrammarPoint 知识,不强制鉴权(内容资产)。checklist 需鉴权。

- [ ] **Step 4: 重写 api/vocab.py 的 in_srs 字段**

编辑 `backend/app/api/vocab.py`。三处改动:(a)import 加 `get_current_user`/`User`/`UserVocabSrs`;(b)`list_vocab` 与 `get_vocab` 注入 `user`;(c)`_serialize` 不再读 `v.in_srs`,改由调用方传 in_srs 集合。具体:

把顶部 import 改为:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, UserVocabSrs, Vocab
from app.services.conjugation import conjugate
from app.services.jpos import normalize_pos
```

在 `list_vocab` 签名加 `user`,并在返回前算出当前用户已入池的 vocab id 集合,传给 `_serialize`。把 `list_vocab` 的签名首行改为:

```python
@router.get("")
def list_vocab(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    level: str | None = Query(default=None),
    q: str | None = Query(default=None),
    pos: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
```

把 `list_vocab` 末尾(`items = ...` 与 return)改为:

```python
    in_srs_ids = {
        vid for (vid,) in db.query(UserVocabSrs.vocab_id).filter(
            UserVocabSrs.user_id == user.id,
            UserVocabSrs.in_srs.is_(True)).all()
    }
    items = [_serialize(v, v.id in in_srs_ids) for v in rows]
    return {"total": int(total), "counts": counts, "items": items}
```

把 `get_vocab` 改为:

```python
@router.get("/{vocab_id}")
def get_vocab(vocab_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> dict:
    """单词详情:词条 + 词性标签 + 活用表(不变形则 conjugation=null)。"""
    v = db.get(Vocab, vocab_id)
    if v is None:
        raise HTTPException(404, "词汇不存在")
    row = db.query(UserVocabSrs).filter_by(
        user_id=user.id, vocab_id=v.id).one_or_none()
    data = _serialize(v, bool(row and row.in_srs))
    data["conjugation"] = conjugate(v.headword, v.reading, v.pos or "")
    return data
```

把 `_serialize` 改为:

```python
def _serialize(v: Vocab, in_srs: bool) -> dict:
    return {
        "id": v.id, "headword": v.headword, "reading": v.reading,
        "meaning_zh": v.meaning_zh, "pos": v.pos,
        "pos_tags": normalize_pos(v.pos or "")["tags"],
        "jlpt_level": v.jlpt_level, "in_srs": in_srs,
    }
```

- [ ] **Step 5: 重写 api/progress.py**

替换 `backend/app/api/progress.py` 全文为:

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import (
    DailySession,
    GrammarPoint,
    User,
    UserGrammarSrs,
    UserVocabSrs,
    Vocab,
)
from app.services.session import compute_streak
from app.services.srs import MASTERED_INTERVAL

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("")
def progress(user: User = Depends(get_current_user),
             db: Session = Depends(get_db)) -> dict:
    today = date.today()
    vocab_in_srs = (
        db.query(UserVocabSrs)
        .filter(UserVocabSrs.user_id == user.id,
                UserVocabSrs.in_srs.is_(True)).count()
    )
    vocab_total = db.query(Vocab).count()
    curated = db.query(GrammarPoint).filter_by(curated=True).count()
    seen = (
        db.query(UserGrammarSrs)
        .filter(UserGrammarSrs.user_id == user.id,
                UserGrammarSrs.status.in_(("seen", "learning"))).count()
    )
    mastered = (
        db.query(UserGrammarSrs)
        .filter(UserGrammarSrs.user_id == user.id,
                UserGrammarSrs.in_srs.is_(True),
                UserGrammarSrs.interval_days >= MASTERED_INTERVAL).count()
    )
    history = [
        {"date": r.date.isoformat(), "completed": r.completed,
         "vocab_reviewed": r.vocab_reviewed,
         "grammar_reviewed": r.grammar_reviewed,
         "lines_read": r.lines_read}
        for r in db.query(DailySession)
        .filter_by(user_id=user.id)
        .order_by(DailySession.date.desc()).all()
    ]
    return {
        "streak": compute_streak(db, user.id, today),
        "vocab": {"total": vocab_total, "in_srs": vocab_in_srs},
        "grammar": {"total_curated": curated, "encountered": seen,
                    "mastered": mastered},
        "history": history,
    }
```

- [ ] **Step 6: 重写 api/today.py 的 journey 注入 user**

编辑 `backend/app/api/today.py`。import 加 `get_current_user`/`User`;`journey` 加 `user`,所有 `compute_streak`/`due_counts` 传 `user.id`。把 import 与 `journey` 签名/调用改为:

import 块:

```python
from app.api._scene import build_scene_list
from app.db import get_db
from app.deps import get_current_user
from app.models import Series, User
from app.services import session as sess
```

`journey` 首部:

```python
@router.get("/journey")
def journey(user: User = Depends(get_current_user),
            db: Session = Depends(get_db)) -> dict:
    today_d = date.today()
    s = db.query(Series).filter_by(is_current=True).first()
    streak = sess.compute_streak(db, user.id, today_d)
    due = sess.due_counts(db, user.id, today_d)
    due_total = due["vocab"] + due["grammar"]
```

(其余 `journey` 函数体不变。)

- [ ] **Step 7: 重写 api/conversation.py 的 feedback 写 SRS**

编辑 `backend/app/api/conversation.py`。`turn` 端点(纯内容,不强制鉴权)保持只读 episode;`feedback` 需鉴权并经 learning_repo 写 per-user SRS。改 import 与 `feedback`:

import 块改为:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Episode, GrammarPoint, Series, User, Vocab
from app.services import conversation, learning_repo
```

`feedback` 替换为:

```python
@router.post("/feedback")
def feedback(body: Feedback, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)) -> dict:
    title, number = _episode_ctx(db, body.episode_id)
    fb = conversation.conversation_feedback(
        series_title=title, episode_number=number, history=body.history)
    # 新词入库(全局知识)并按当前用户加入 SRS
    for item in fb.get("new_vocab", []):
        hw, rd = item.get("headword"), item.get("reading")
        if not hw or not rd:
            continue
        v = db.query(Vocab).filter_by(headword=hw, reading=rd).first()
        if v is None:
            v = Vocab(headword=hw, reading=rd,
                      meaning_zh=item.get("meaning_zh", ""))
            db.add(v)
            db.flush()
        row = learning_repo.get_or_create_vocab_srs(db, user.id, v.id)
        row.in_srs = True
        if row.due_date is None:
            row.due_date = date.today()
    # 薄弱语法点按当前用户加入 SRS
    for key in fb.get("weak_grammar_keys", []):
        gp = db.query(GrammarPoint).filter_by(key=key).first()
        if gp is None:
            continue
        row = learning_repo.get_or_create_grammar_srs(db, user.id, gp.id)
        row.in_srs = True
        row.status = "learning"
        if row.due_date is None:
            row.due_date = date.today()
    db.commit()
    return fb
```

- [ ] **Step 8: 更新前述 API 测试为 auth_client**

(a) `backend/tests/test_api_grammar.py` 替换全文为:

```python
from app.models import GrammarPoint, User, UserGrammarSrs
from app.services import grammar_quiz


def test_checklist_requires_auth(client):
    assert client.get("/api/grammar/checklist").status_code == 401


def test_checklist_groups_by_level(auth_client, auth_user, db_session):
    g_n2 = GrammarPoint(key="g-n2", name="〜N2点", jlpt_level="N2",
                        explanation="x", curated=True)
    g_n1 = GrammarPoint(key="g-n1", name="〜N1点", jlpt_level="N1",
                        explanation="y", curated=True)
    db_session.add_all([g_n2, g_n1])
    db_session.commit()
    db_session.add(UserGrammarSrs(user_id=auth_user.id, grammar_id=g_n1.id,
                                  status="seen"))
    db_session.commit()
    body = auth_client.get("/api/grammar/checklist").json()
    assert "N2" in body and "N1" in body
    assert body["N2"][0]["key"] == "g-n2"
    assert body["N2"][0]["status"] == "locked"   # 当前用户无该行 → locked
    assert body["N1"][0]["status"] == "seen"


def test_checklist_isolated(auth_client, db_session):
    g = GrammarPoint(key="g-iso", name="〜iso", jlpt_level="N2",
                     explanation="x", curated=True)
    other = User(username="other", password_hash="x")
    db_session.add_all([g, other])
    db_session.commit()
    db_session.add(UserGrammarSrs(user_id=other.id, grammar_id=g.id,
                                  status="learning"))
    db_session.commit()
    body = auth_client.get("/api/grammar/checklist").json()
    assert body["N2"][0]["status"] == "locked"   # other 的状态不可见


def test_grammar_quiz_endpoint(auth_client, db_session, monkeypatch):
    monkeypatch.setattr(
        grammar_quiz.llm, "call_json",
        lambda **kw: {"quiz": [{"question": "Q?",
                                "options": ["a", "b", "c", "d"],
                                "answer": "a", "explain": "e"}]})
    gp = GrammarPoint(key="g1", name="〜g1", jlpt_level="N2", explanation="x",
                      curated=True)
    db_session.add(gp)
    db_session.commit()
    body = auth_client.get(f"/api/grammar/{gp.id}/quiz").json()
    assert body["answer"] == "a" and len(body["options"]) == 4
```

(b) `backend/tests/test_api_vocab.py`:列表/详情现需鉴权。把所有 `client` 改为 `auth_client`,并加一条 401 测试。最简改法:在文件顶部加 401 测试,并把每个测试函数签名的 `client` 换成 `auth_client`(调用处 `client.get` → `auth_client.get`)。在文件末尾追加:

```python
def test_list_requires_auth(client, db_session):
    _seed(db_session)
    assert client.get("/api/vocab").status_code == 401
```

并对 `test_list_returns_total_counts_items`、`test_level_filter`、`test_search_matches_headword_reading_meaning`、`test_items_include_pos_tags`、`test_pos_filter_verb`、`test_pos_filter_noun`、`test_detail_returns_conjugation_for_verb`、`test_detail_noun_has_null_conjugation`、`test_detail_404`、`test_pagination` 这 10 个函数:把参数 `(client, db_session)` 改为 `(auth_client, db_session)`,并把函数体内的 `client.get(` 全部替换为 `auth_client.get(`。

(c) `backend/tests/test_api_progress.py` 替换全文为:

```python
from datetime import date, timedelta

from app.models import (
    DailySession,
    GrammarPoint,
    UserGrammarSrs,
    UserVocabSrs,
    Vocab,
)


def test_progress_requires_auth(client):
    assert client.get("/api/progress").status_code == 401


def test_progress_summary(auth_client, auth_user, db_session):
    today = date.today()
    v = Vocab(headword="猫", reading="ねこ", meaning_zh="猫")
    g1 = GrammarPoint(key="g1", name="g1", jlpt_level="N2", explanation="x",
                      curated=True)
    g2 = GrammarPoint(key="g2", name="g2", jlpt_level="N2", explanation="y",
                      curated=True)
    db_session.add_all([v, g1, g2])
    db_session.commit()
    db_session.add_all([
        DailySession(user_id=auth_user.id, date=today, completed=True),
        DailySession(user_id=auth_user.id, date=today - timedelta(days=1),
                     completed=True),
        UserVocabSrs(user_id=auth_user.id, vocab_id=v.id, in_srs=True,
                     due_date=today),
        UserGrammarSrs(user_id=auth_user.id, grammar_id=g1.id, in_srs=True,
                       interval_days=30, status="learning"),
    ])
    db_session.commit()
    body = auth_client.get("/api/progress").json()
    assert body["streak"] == 2
    assert body["vocab"]["in_srs"] == 1
    assert body["grammar"]["mastered"] == 1
    assert body["grammar"]["total_curated"] == 2
    assert len(body["history"]) == 2
```

(d) `backend/tests/test_api_today_journey.py`:把每个测试函数的 `client` 参数改为 `auth_client`,并把函数体内 `client.get(` 替换为 `auth_client.get(`。在文件顶部加一条 401 测试:

```python
def test_journey_requires_auth(client):
    assert client.get("/api/today/journey").status_code == 401
```

具体:`test_journey_no_series`、`test_journey_series_no_episode`、`test_journey_full_flow_with_main_character`、`test_journey_main_character_fallback_initial_from_series_title`、`test_journey_main_character_picks_first_with_image` 五个函数签名 `(client, db_session)` → `(auth_client, db_session)`(注意 `test_journey_full_flow_with_main_character` 的签名跨两行),函数体 `client.get` → `auth_client.get`。

(e) `backend/tests/test_api_conversation.py`:`turn` 不需鉴权,`feedback` 需鉴权。替换 `test_conversation_feedback_mines_srs` 为:

```python
def test_conversation_feedback_requires_auth(client, db_session, monkeypatch):
    monkeypatch.setattr(conversation.llm, "call_json", lambda **kw: {
        "corrections": [], "suggestions": [], "new_vocab": [],
        "weak_grammar_keys": []})
    ep = _episode(db_session)
    resp = client.post("/api/conversation/feedback",
                       json={"episode_id": ep.id, "history": []})
    assert resp.status_code == 401


def test_conversation_feedback_mines_srs(auth_client, auth_user, db_session,
                                         monkeypatch):
    from app.models import UserGrammarSrs, UserVocabSrs
    monkeypatch.setattr(conversation.llm, "call_json", lambda **kw: {
        "corrections": [{"original": "x", "fixed": "y", "explain": "z"}],
        "suggestions": ["s"],
        "new_vocab": [{"headword": "感想", "reading": "かんそう",
                       "meaning_zh": "感想"}],
        "weak_grammar_keys": ["wk-gram"],
    })
    ep = _episode(db_session)
    db_session.add(GrammarPoint(key="wk-gram", name="〜wk", jlpt_level="N2",
                                explanation="x"))
    db_session.commit()
    resp = auth_client.post("/api/conversation/feedback", json={
        "episode_id": ep.id, "history": [{"role": "user", "text": "x"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["corrections"][0]["fixed"] == "y"
    v = db_session.query(Vocab).filter_by(headword="感想").one()
    vr = db_session.query(UserVocabSrs).filter_by(
        user_id=auth_user.id, vocab_id=v.id).one()
    assert vr.in_srs is True
    gp = db_session.query(GrammarPoint).filter_by(key="wk-gram").one()
    gr = db_session.query(UserGrammarSrs).filter_by(
        user_id=auth_user.id, grammar_id=gp.id).one()
    assert gr.in_srs is True and gr.status == "learning"
```

(`test_conversation_turn` 不动,仍用 `client`,因为 turn 不鉴权。)

- [ ] **Step 9: Run targeted tests**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_session.py tests/test_api_grammar.py tests/test_api_vocab.py tests/test_api_progress.py tests/test_api_today_journey.py tests/test_api_conversation.py -v`
Expected: PASS。

- [ ] **Step 10: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿。

- [ ] **Step 11: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/services/session.py app/api/grammar.py app/api/vocab.py app/api/progress.py app/api/today.py app/api/conversation.py tests/test_session.py tests/test_api_grammar.py tests/test_api_vocab.py tests/test_api_progress.py tests/test_api_today_journey.py tests/test_api_conversation.py
git commit -m "feat(api): user-scope grammar/vocab/progress/today/conversation/due_counts"
```

---

## Task 7: contract — 从 Vocab/GrammarPoint 删 SRS 列 + Alembic 0004

**Files:**
- Modify: `backend/app/models/study.py`
- Modify: `backend/app/services/pipeline.py`
- Create: `backend/migrations/versions/0004_drop_knowledge_srs.py`
- Modify: `backend/tests/test_models.py`
- Modify: `backend/tests/test_pipeline.py`(若引用被删字段)

**Interfaces:**
- Produces:
  - `Vocab`:仅 `id/headword/reading/meaning_zh/pos/jlpt_level/source_line_id`(+ 唯一约束)。
  - `GrammarPoint`:仅 `id/key/name/jlpt_level/explanation/curated/quiz_cache/source_line_id`(无 `status` 及 SRS 列)。
  - pipeline 不再写 `Vocab.in_srs`、不再写 `GrammarPoint.status`(`_mark_grammar_seen` 删除)。

> **说明(写入计划记录):** 删除 `GrammarPoint.status` 后,「番剧语法加成」(原 `submit_result` 中 grammar status∈{seen,learning} → 1.5×)因 per-user status 默认 locked 而**暂失效**(Task 5 已让 grammar 加成恒为 1.0)。**vocab 番剧加成仍靠 `source_line_id`**,不受影响。本期不为 grammar 番剧加成另做替代实现。

- [ ] **Step 1: Write the failing test (knowledge tables are SRS-free)**

编辑 `backend/tests/test_models.py`,替换 `test_grammar_point_defaults` 为(断言无 status/SRS 字段):

```python
def test_grammar_point_defaults(db_session):
    gp = GrammarPoint(key="ni-atatte", name="〜にあたって", jlpt_level="N2",
                      explanation="在…之际", curated=True)
    db_session.add(gp)
    db_session.commit()
    assert gp.curated is True
    assert not hasattr(gp, "status")
    assert not hasattr(gp, "in_srs")
    assert not hasattr(gp, "ease")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_models.py::test_grammar_point_defaults -v`
Expected: FAIL(`gp.status` 仍存在)。

- [ ] **Step 3: 删 study.py 的 SRS 列**

编辑 `backend/app/models/study.py`,把 `Vocab` 与 `GrammarPoint` 替换为(`DailySession`/`AppSetting` 保持 Task 3 版本):

```python
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


class GrammarPoint(Base):
    __tablename__ = "grammar_point"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    jlpt_level: Mapped[str]
    explanation: Mapped[str]
    curated: Mapped[bool] = mapped_column(default=False)
    quiz_cache: Mapped[list | None] = mapped_column(JSONB_OR_JSON, default=None)
    source_line_id: Mapped[int | None] = mapped_column(ForeignKey("line.id"))
```

(顶部 import 仍需 `_date`/`datetime`/`func` 给 `DailySession`,不动。)

- [ ] **Step 4: 改 pipeline.py 去掉用户态写入**

编辑 `backend/app/services/pipeline.py`:

(a) 删除 `_mark_grammar_seen` 整个函数(第 102-107 行那段)。

(b) 把 `_upsert_vocab` 里 `Vocab(...)` 构造中的 `in_srs=False,` 删掉,改为:

```python
        session.add(Vocab(
            headword=hw, reading=rd, meaning_zh=it.get("meaning_zh", ""),
            pos=it.get("pos"), jlpt_level=it.get("jlpt_level"),
            source_line_id=source_line_id,
        ))
```

(c) 在 `process_episode` 内 batch 循环里删除对 `_mark_grammar_seen` 的调用行。把 `for ln in batch:` 循环体改为:

```python
            for ln in batch:
                # LLM 若漏掉某行 idx，该行仍标记 processed（注释留空），保持断点续跑干净
                ann = by_idx.get(ln.idx, {})
                ln.furigana = to_furigana(ln.text_jp)
                ln.translation_zh = ann.get("translation_zh")
                ln.grammar_notes = ann.get("grammar_notes") or []
                ln.register_tag = ann.get("register_tag")
                keys = ann.get("grammar_point_keys") or []
                ln.grammar_point_keys = keys
                ln.processed = True
                session.flush()  # 取得 ln.id
```

(删去 `_mark_grammar_seen(session, keys, ln.id)` 那一行。`keys`/`flush()` 保留——`grammar_point_keys` 仍写入 Line。)

- [ ] **Step 5: 写 Alembic 0004(drop 列)**

创建 `backend/migrations/versions/0004_drop_knowledge_srs.py`:

```python
"""drop per-knowledge SRS columns from vocab/grammar_point

Revision ID: 0004_drop_knowledge_srs
Revises: 0003_user_scoping
"""
import sqlalchemy as sa
from alembic import op

revision = "0004_drop_knowledge_srs"
down_revision = "0003_user_scoping"
branch_labels = None
depends_on = None

_VOCAB_SRS = ("in_srs", "ease", "interval_days", "reps", "lapses",
              "due_date", "last_reviewed")
_GRAMMAR_SRS = ("status", "in_srs", "ease", "interval_days", "reps", "lapses",
                "due_date", "last_reviewed")


def upgrade() -> None:
    with op.batch_alter_table("vocab") as batch:
        for col in _VOCAB_SRS:
            batch.drop_column(col)
    with op.batch_alter_table("grammar_point") as batch:
        for col in _GRAMMAR_SRS:
            batch.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("vocab") as batch:
        batch.add_column(sa.Column("in_srs", sa.Boolean, nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column("ease", sa.Float, nullable=False,
                                   server_default="2.5"))
        batch.add_column(sa.Column("interval_days", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("reps", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("lapses", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("due_date", sa.Date))
        batch.add_column(sa.Column("last_reviewed", sa.DateTime))
    with op.batch_alter_table("grammar_point") as batch:
        batch.add_column(sa.Column("status", sa.String, nullable=False,
                                   server_default="locked"))
        batch.add_column(sa.Column("in_srs", sa.Boolean, nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column("ease", sa.Float, nullable=False,
                                   server_default="2.5"))
        batch.add_column(sa.Column("interval_days", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("reps", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("lapses", sa.Integer, nullable=False,
                                   server_default="0"))
        batch.add_column(sa.Column("due_date", sa.Date))
        batch.add_column(sa.Column("last_reviewed", sa.DateTime))
```

- [ ] **Step 6: 跑迁移测试 + 模型测试**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_migrations.py tests/test_models.py -v`
Expected: PASS(0001→0004 upgrade、再 downgrade base 通过)。

- [ ] **Step 7: 检查 pipeline 测试是否引用被删字段**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_pipeline.py tests/test_pipeline_scenes.py -v`
Expected: 若失败,定位到引用 `in_srs`/`status`/`_mark_grammar_seen` 的断言并删除/改写;典型修法:删掉对 `gp.status == "seen"` 的断言。再重跑直到绿。

- [ ] **Step 8: 全量回归 + ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q && uv run ruff check app tests`
Expected: 全绿。若有残留引用被删字段的测试(grep 帮助:`uv run python -c "import subprocess"` 略),用 `grep -rn "\.in_srs\|\.status" tests/ app/` 复核知识表残留写入。

- [ ] **Step 9: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add app/models/study.py app/services/pipeline.py migrations/versions/0004_drop_knowledge_srs.py tests/test_models.py tests/test_pipeline.py
git commit -m "refactor(models): drop per-knowledge SRS columns + alembic 0004 (contract)"
```

---

## Task 8: 前端 — 登录页 + token 注入 + 路由守卫 + 导航登出

**Files:**
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/tests/handlers.ts`
- Modify: `frontend/tests/api.test.ts`
- Test: `frontend/tests/auth.test.tsx`

**Interfaces:**
- Produces:
  - `lib/api.ts`:`getToken()/setToken()/clearToken()`、`register(username,password)`、`login(username,password)`、`getMe()`;`http` 注入 `Authorization` 头,401 时清 token 并跳 `/login`。
  - `Login.tsx`:注册/登录二合一,成功后存 token 跳 `/`。
  - `App.tsx`:无 token 访问受保护路由 → 重定向 `/login`;`/login` 为公开路由。

- [ ] **Step 1: api.ts 加 token 工具与 auth 调用,改 http**

编辑 `frontend/src/lib/api.ts`。把文件顶部 `http` 之前/之中改为:

```typescript
const TOKEN_KEY = "anime_nihongo_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const resp = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (resp.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw new Error(`401 ${path}`);
  }
  if (!resp.ok) throw new Error(`${resp.status} ${path}: ${await resp.text()}`);
  return resp.json() as Promise<T>;
}
```

并在文件末尾追加 auth API:

```typescript
// Auth
type AuthResponse = { token: string; user: { id: number; username: string } };
export const register = (username: string, password: string) =>
  http<AuthResponse>("/api/auth/register",
    { method: "POST", body: JSON.stringify({ username, password }) });
export const login = (username: string, password: string) =>
  http<AuthResponse>("/api/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) });
export const getMe = () => http<{ id: number; username: string }>("/api/auth/me");
```

- [ ] **Step 2: 建 Login.tsx**

创建 `frontend/src/pages/Login.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { login, register, setToken } from "../lib/api";

export default function Login() {
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const fn = mode === "login" ? login : register;
      const res = await fn(username, password);
      setToken(res.token);
      nav("/");
    } catch {
      setError(mode === "login" ? "用户名或密码错误" : "注册失败（用户名可能已被占用）");
    }
  };

  return (
    <div className="max-w-sm mx-auto py-16">
      <h1 className="text-xl font-bold mb-6 text-brand-700">
        {mode === "login" ? "登录" : "注册"} · 追番日语
      </h1>
      <form onSubmit={submit} className="space-y-3">
        <input
          aria-label="用户名"
          className="w-full border rounded px-3 py-2"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          aria-label="密码"
          type="password"
          className="w-full border rounded px-3 py-2"
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="w-full bg-brand-600 text-white rounded py-2">
          {mode === "login" ? "登录" : "注册"}
        </button>
      </form>
      <button
        className="mt-4 text-sm text-brand-600"
        onClick={() => setMode(mode === "login" ? "register" : "login")}
      >
        {mode === "login" ? "没有账号？去注册" : "已有账号？去登录"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: App.tsx 加守卫与公开 /login 路由**

替换 `frontend/src/App.tsx` 全文为:

```tsx
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import { getToken } from "./lib/api";
import Conversation from "./pages/Conversation";
import Grammar from "./pages/Grammar";
import Login from "./pages/Login";
import Progress from "./pages/Progress";
import Quiz from "./pages/Quiz";
import Reading from "./pages/Reading";
import Review from "./pages/Review";
import Series from "./pages/Series";
import Today from "./pages/Today";
import Tower from "./pages/Tower";

function RequireAuth({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Today />} />
        <Route path="series" element={<Series />} />
        <Route path="episodes/:id/reading" element={<Reading />} />
        <Route path="episodes/:id/conversation" element={<Conversation />} />
        <Route path="review" element={<Review />} />
        <Route path="grammar" element={<Grammar />} />
        <Route path="progress" element={<Progress />} />
        <Route path="tower" element={<Tower />} />
        <Route path="quiz" element={<Quiz />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 4: Layout.tsx 显示用户名 + 登出**

编辑 `frontend/src/components/Layout.tsx`。顶部 import 加,组件内取用户名并加登出按钮。把 import 段与右侧 `<div className="ml-auto ...">` 块改为:

import:

```tsx
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { clearToken, getMe } from "../lib/api";
import SpeakerPicker from "./SpeakerPicker";
```

在 `export default function Layout() {` 后、`return` 前加:

```tsx
  const nav = useNavigate();
  const [username, setUsername] = useState<string>("");

  useEffect(() => {
    getMe().then((u) => setUsername(u.username)).catch(() => {});
  }, []);

  const logout = () => {
    clearToken();
    nav("/login");
  };
```

把右侧 `<div className="ml-auto flex items-center gap-3">` 内、`<SpeakerPicker />` 之后加:

```tsx
            <SpeakerPicker />
            {username && (
              <span className="text-xs text-ink-500">{username}</span>
            )}
            <button onClick={logout} className="text-xs text-brand-600">
              登出
            </button>
```

- [ ] **Step 5: handlers.ts 加 auth mock**

编辑 `frontend/tests/handlers.ts`。在 `export const handlers = [` 数组开头加三条 auth handler:

```typescript
export const handlers = [
  http.post("/api/auth/register", () => HttpResponse.json({
    token: "test-token", user: { id: 1, username: "tester" } })),
  http.post("/api/auth/login", () => HttpResponse.json({
    token: "test-token", user: { id: 1, username: "tester" } })),
  http.get("/api/auth/me", () => HttpResponse.json({
    id: 1, username: "tester" })),
  http.get("/api/series", () => HttpResponse.json([
```

(其余 handler 不变。)

- [ ] **Step 6: Write the failing test (auth flow)**

创建 `frontend/tests/auth.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { getToken, login, register } from "../src/lib/api";
import Login from "../src/pages/Login";

describe("auth", () => {
  beforeEach(() => localStorage.clear());

  it("register returns token", async () => {
    const res = await register("alice", "pw");
    expect(res.token).toBe("test-token");
  });

  it("login returns token", async () => {
    const res = await login("alice", "pw");
    expect(res.user.username).toBe("tester");
  });

  it("login page stores token on submit", async () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<div>home</div>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText("用户名"),
      { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("密码"),
      { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    await waitFor(() => expect(getToken()).toBe("test-token"));
  });
});
```

- [ ] **Step 7: api.test.ts 在调 protected 接口前设 token**

编辑 `frontend/tests/api.test.ts`,在 `describe` 内顶部加 `beforeEach` 设 token(因 `http` 现要 token,否则 msw handler 仍返回数据但更贴近真实;主要确保不会因 401 跳转污染):

```typescript
import { beforeEach, describe, expect, it } from "vitest";

import { getChecklist, getJourney, getProgress, listSeries, setToken } from "../src/lib/api";

describe("api client", () => {
  beforeEach(() => setToken("test-token"));
  it("listSeries", async () => {
```

(其余测试体不变。)

- [ ] **Step 8: Run frontend tests**

Run: `cd /Users/naruo/Workspace/anime-nihongo/frontend && npm test -- --run`
Expected: PASS,含新 `auth.test.tsx`。若 `progress.test.tsx`/`today.test.tsx`/`tower.test.tsx`/`grammar.test.tsx`/`review.test.tsx` 因渲染时调用 protected 接口前无 token 而触发 `window.location.assign`,在其各自测试文件的 `beforeEach`(或渲染前)加 `setToken("test-token")`。逐个修复至绿:在每个失败文件顶部 import `setToken` 并在 `beforeEach(() => setToken("test-token"))`。

- [ ] **Step 9: lint(前端)**

Run: `cd /Users/naruo/Workspace/anime-nihongo/frontend && npm run lint`
Expected: 无新增错误(若项目无 lint script 则跳过)。

- [ ] **Step 10: Commit**

```bash
cd /Users/naruo/Workspace/anime-nihongo
git add frontend/src/pages/Login.tsx frontend/src/lib/api.ts frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/tests/handlers.ts frontend/tests/api.test.ts frontend/tests/auth.test.tsx
# 若 Step 8 改了其它前端测试文件,一并 add
git commit -m "feat(web): login page, token injection, route guard, logout"
```

---

## Task 9: 全量回归 + ruff(收尾)

**Files:** 无新增;仅验证。

- [ ] **Step 1: 后端全量**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest -q`
Expected: 全绿,0 failed。

- [ ] **Step 2: 后端 ruff**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run ruff check app tests`
Expected: 干净(预存 E501 除外)。

- [ ] **Step 3: 前端全量**

Run: `cd /Users/naruo/Workspace/anime-nihongo/frontend && npm test -- --run`
Expected: 全绿。

- [ ] **Step 4: 知识表残留写入扫描(防回归)**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && grep -rn "Vocab(.*in_srs\|gp.status\s*=\|\.status\s*=\s*\"seen\"\|GrammarPoint(.*status=" app/`
Expected: 无命中(知识表不再写用户态)。

- [ ] **Step 5: 迁移端到端**

Run: `cd /Users/naruo/Workspace/anime-nihongo/backend && uv run pytest tests/test_migrations.py -v`
Expected: PASS(0001→0004 upgrade + downgrade base)。

- [ ] **Step 6: Commit(若 Step 2/4 有微调)**

```bash
cd /Users/naruo/Workspace/anime-nihongo/backend
git add -A
git commit -m "chore: full regression green for auth user-scoping" --allow-empty
```

---

## Self-Review

**1. Spec coverage**(对照 `2026-06-25-auth-user-scoping-design.md`):

- §3 新增 User / UserVocabSrs / UserGrammarSrs → Task 2/3。✅
- §3 修改 Vocab/GrammarPoint 删 SRS、TowerProgress/PlayerStats/DailySession 加 user_id → Task 3(加列)+ Task 7(删知识 SRS 列)。✅
- §3 迁移合并:为可分阶段保持绿,**拆为 0003(additive 加表/加列)+ 0004(contract 删列)**——偏离 spec「一条 0003」,但符合本计划要求的 expand-contract 与「每 Task 全绿」,在 Task 7 已注明。⚠️(有意偏离,见下「修正不一致点」)
- §4 services/auth.py + api/auth.py + get_current_user + 种子 → Task 1/2。✅
- §5 srs/tower/session user-scoped、join 读知识+学习态 → Task 4/5/6。✅
- §6 前端 Login/token/守卫/导航 → Task 8。✅
- §7 测试:auth、隔离、迁移、前端守卫 → 各 Task 含隔离测试 + Task 9 回归。✅
- §8 learning_repo 收敛取或建、get_current_user 唯一入口、知识表只读 → Task 3/2/7。✅
- §10 验收:两个用户隔离(test_*_isolated)、无/过期 token 401(test_auth_service + 各 requires_auth)、0003/0004 通过、全绿。✅

**2. Placeholder scan:** 全部步骤含可粘贴代码或精确命令;无 TBD/「适当处理」/「类似 Task N」。Task 7 Step 7、Task 8 Step 8 含「若失败则…」的条件修复,但都给了具体 grep/具体改法,非占位。✅

**3. Type/signature consistency:**
- `learning_repo.get_or_create_vocab_srs(db, user_id, vocab_id)` / `get_or_create_grammar_srs(db, user_id, grammar_id)` — Task 3 定义,Task 4/5/6 一致调用。✅
- `submit_result(db, user_id, ...)` / `tower_map(db, user_id)` / `is_cell_unlocked(db, user_id, ...)` — Task 5 定义并在 api/tower.py、test 一致。✅
- `compute_streak(db, user_id, today)` / `record_completion(db, user_id, today, episode_id, stats)` / `due_counts(db, user_id, today)` — Task 4 改前两者、Task 6 改 due_counts;study/today/progress 调用一致。✅
- `UserGrammarSrs` 用 `grammar_id`(非 grammar_point_id),全计划统一。✅
- `decode_token(token, now=None)`、`create_access_token(user_id, now=None)` — Task 1 定义,deps/auth_client 一致。✅

**修正的不一致点(发现并已在计划中处理):**

1. **迁移拆分 vs spec 的「一条 0003」**:spec 要求合并一次迁移,但本计划的硬约束是 expand-contract 且每个 Task 末尾全量绿;若 0003 直接删知识表 SRS 列,则 Task 4-6 之前(服务尚未切换)测试会红。故拆成 0003(additive)+ 0004(contract),Task 7 显式记录此偏离。

2. **`record_completion`/`compute_streak` 的提前改签名**:study.py 的 `complete-today` 在 Task 4 已切 user-scoped(因其与 add-srs 同属 study 路由,一并改更内聚),因此把这两个 session 函数的签名改动从 Task 6 提到 Task 4,并同步更新 test_session 对应两测试;`due_counts` 仍留 Task 6。已在 Task 4 Step 8/9 与 Task 6 Step 1 之间消除签名冲突。

3. **grammar 番剧加成失效**:原 `submit_result` 依赖 `GrammarPoint.status`;删列后 per-user grammar 默认 locked,无 seen 来源。Task 5 已让 grammar 加成恒为 1.0,并删除原 `test_grammar_anime_bonus_uses_original_status`;Task 7 注明本期不补替代实现(vocab 加成仍靠 source_line_id)。

4. **`auth_client` 夹具做法明确**:spec 仅提示「鉴权 client 需带 token」。计划在 conftest 用 `client.headers.update({"Authorization": ...})` 给出可复用夹具(Task 4 Step 1),并逐个列出受影响测试文件改为 `auth_client` 的具体函数名与替换规则(srs/study/tower/grammar/vocab/progress/today/conversation)。

5. **`GrammarPoint` 测试构造去 `status=`**:多处旧测试以 `GrammarPoint(..., status="seen")` 构造;Task 4/6 起改为不传 status(Task 7 删列后该 kwarg 会报错),已在相关测试改写中统一移除。
