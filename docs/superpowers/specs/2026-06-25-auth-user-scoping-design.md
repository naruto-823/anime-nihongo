# 用户系统 + JWT + 学习状态 user-scoped 化 设计文档

> 2026-06-25 · 子项目二。建在子项目一(Postgres + Alembic)之上。
> 把「登录」与「数据按用户隔离」**合并为一次迁移**做掉——避免"先加 User 再搬 SRS"的二次迁移痛苦(回应架构评审 #2/#3)。

## 1. 目标与非目标

**目标**
- 账号体系:User 模型 + 注册/登录 + **JWT(单 access token,7 天)**;密码 bcrypt 哈希。
- **学习状态 user-scoped 化**:把当前挂在全局知识表(Vocab/GrammarPoint)上的 SRS 状态拆出来;TowerProgress/PlayerStats/DailySession 加 `user_id`。一次 Alembic 迁移切干净。
- 全部有状态接口注入 `current_user`,数据按用户隔离。
- 种子 dev 账号(本地便利),支持注册。

**非目标(更后续)**
- 异步 Job 系统、外呼 Client 治理层、LLM 生成产物版本化、可观测性 —— 评审路线图的 ③④⑤,各自独立子项目。
- refresh token、第三方 OAuth、邮箱找回、密码强度策略 —— YAGNI。
- 现有本地 SQLite 学习数据迁移 —— 不做(Postgres 全新 + 种子;本地 sqlite 拆列后旧 SRS 进度丢弃,属开发数据)。

## 2. 关键决策

| 决策 | 选择 |
|---|---|
| 登录方式 | 用户名 + 密码,bcrypt |
| 会话 | JWT HS256,单 access token,7 天过期,前端存 localStorage |
| 密钥 | `JWT_SECRET` 环境变量(`.env`/容器注入),有默认 dev 值 |
| 种子账号 | 启动时若无任何用户,建默认 `admin/admin`(可经 env 关闭) |
| 隔离范围 | **一次性**:SRS 拆表 + Tower/Player/Daily 加 user_id |
| 数据迁移 | 不迁旧数据,fresh + 种子 |

## 3. 数据模型变更

### 新增
- **`User`**:`id, username(unique), password_hash, created_at`。
- **`UserVocabSrs`**:`id, user_id(FK→user), vocab_id(FK→vocab), in_srs, ease, interval_days, reps, lapses, due_date, last_reviewed`;唯一 `(user_id, vocab_id)`。
- **`UserGrammarSrs`**:`id, user_id(FK), grammar_id(FK), status(locked/seen/learning, 默认 locked), in_srs, ease, interval_days, reps, lapses, due_date, last_reviewed`;唯一 `(user_id, grammar_id)`。

### 修改
- **`Vocab`**:**移除** SRS 字段(`in_srs/ease/interval_days/reps/lapses/due_date/last_reviewed`)。保留 `headword/reading/meaning_zh/pos/jlpt_level/source_line_id`(纯知识 + 内容溯源)。
- **`GrammarPoint`**:**移除** `status/in_srs/ease/interval_days/reps/lapses/due_date/last_reviewed`。保留 `key/name/jlpt_level/explanation/curated/quiz_cache/source_line_id`(`quiz_cache` 是全局生成缓存,暂留;版本化属后续)。
- **`TowerProgress`**:加 `user_id(FK)`;唯一改为 `(user_id, level, zone_idx, stage_idx, is_boss)`。
- **`PlayerStats`**:由单行 `id=1` 改为**每用户一行**——`user_id(FK, unique)`。
- **`DailySession`**:加 `user_id(FK)`;唯一改为 `(user_id, date)`。

### 迁移(Alembic 0003)
一条迁移:建 user/user_vocab_srs/user_grammar_srs;给 tower_progress/daily_session 加 user_id 与新唯一约束;重建 player_stats;从 vocab/grammar_point 删 SRS 列。**无数据回填**(fresh)。downgrade 反向。

## 4. 认证

- 依赖新增:`bcrypt`、`pyjwt`(写入 pyproject)。
- **`services/auth.py`**(纯逻辑、可单测):
  - `hash_password(pw) -> str`、`verify_password(pw, hash) -> bool`(bcrypt)。
  - `create_access_token(user_id, now) -> str`、`decode_token(token, now) -> int|None`(HS256,exp=7d,sub=user_id;过期/非法返回 None)。
- **`api/auth.py`**:
  - `POST /api/auth/register {username,password}` → 建用户(用户名占用→409),返回 `{token, user:{id,username}}`。
  - `POST /api/auth/login {username,password}` → 校验(失败→401),返回同上。
  - `GET /api/auth/me`(需鉴权)→ `{id, username}`。
- **鉴权依赖 `get_current_user`**(`app/deps.py` 或 `api/auth.py`):从 `Authorization: Bearer <jwt>` 解析 → 查 User → 返回;无/非法/过期 → 401。所有有状态路由用 `Depends(get_current_user)`。
- **种子**:启动时若 `User` 表空,建 `admin`(密码取 `SEED_ADMIN_PASSWORD` env,默认 `admin`);`DISABLE_SEED_USER=1` 可关。

## 5. 服务与接口 user-scoped 化

- `services/srs.py`:`apply_review` 作用于 `UserVocabSrs`/`UserGrammarSrs` 行(按 user_id+item_id 取或建)。
- `services/tower.py`:`submit_result(db, user_id, ...)`、`tower_map(db, user_id)`、`is_cell_unlocked(db, user_id, ...)`;TowerProgress 查询全部带 user_id;PlayerStats 按 user_id 取/建;SRS 写入走 user_*_srs。
- `services/session.py`(streak):DailySession 按 user_id。
- 读取「学习态 + 知识」的地方改为 join:如 grammar checklist = GrammarPoint(知识) LEFT JOIN UserGrammarSrs(当前用户) → 给出 status/mastered;vocab 详情的 `in_srs` 同理。
- 受影响 API(全部注入 current_user):`study`(add-srs)、`srs`(due/review)、`tower`(全部)、`today`(journey)、`progress`、`grammar`(checklist)、`vocab`(列表的 in_srs 字段)。`auth` 新增。`series/episodes/tts/conversation` 暂不强制按用户(内容资产仍全局;番剧库按用户隔离属后续,本期内容仍共享——与"先账号、内容隔离可后续"一致)。

> **范围收敛**:本期**学习状态**(SRS/Tower/Player/Daily)按用户隔离;**内容资产**(Series/Episode/Line/Scene)本期仍全局共享(番剧库按用户隔离留后续),避免一次动太多。

## 6. 前端

- **`pages/Login.tsx`**(注册/登录二合一切换)。
- `lib/api.ts`:`http` 读取 localStorage 的 token 注入 `Authorization` 头;**401 → 清 token 跳 `/login`**。新增 `register/login/getMe`。
- **路由守卫**:无 token 访问受保护路由 → 重定向 `/login`;`App.tsx` 包一层。
- 顶部导航显示当前用户名 + 登出(清 token)。
- 现有页面逻辑基本不动(数据隔离在服务端按 token 完成)。

## 7. 测试策略

- `auth`:注册成功/用户名占用 409、登录成功/密码错 401、token 往返、过期 token→None、`get_current_user` 401。
- **隔离**:建两个用户,各自 SRS/Tower/Player/Daily 互不可见;A 复习不影响 B;tower submit 只写当前用户。
- `srs`/`tower`/`session` 重构后单测更新为带 user_id。
- 迁移:0003 upgrade/downgrade(临时 sqlite)。
- 前端:登录流程、无 token 守卫跳转、401 清 token。
- **全量回归**:现有大量测试构造 `Vocab(in_srs=...)`/`GrammarPoint(status=...)`/`PlayerStats(id=1)`/无 user 的 tower 调用——**都要改**;这是本期工作量大头,须逐个更新至绿。

## 8. 架构边界(落实评审)

- **Repository 雏形**:user-scoped 取/建 SRS 行的逻辑集中到 `learning_repo`(或先放 srs/tower 内的私有 helper,避免散落)——本期至少把"取或建 UserVocabSrs"收敛成单一函数,不在多处手写。
- `get_current_user` 是唯一鉴权入口;路由不自行解析 token。
- 知识表(Vocab/GrammarPoint)自此**只读知识**,任何用户态写入一律走 user_*_srs —— 从模型层杜绝旧错误复发。

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 改动面大(几乎所有有状态服务/接口/测试) | 分阶段:先 auth(独立)→ 再模型+迁移 → 再逐服务 user-scoped → 最后前端;每步全量保持绿 |
| 删 Vocab/GrammarPoint SRS 列波及大量测试 | 计划里逐文件给出测试改法;一次性切,不留兼容层 |
| 种子 admin/admin 弱密码上线风险 | env 可配密码 + `DISABLE_SEED_USER`;文档警示生产改密 |
| JWT 密钥默认值泄漏风险 | 默认仅 dev;生产必须经 env 注入,文档/`.env.example` 警示 |

## 10. 验收标准

- 注册→登录→拿 token→访问受保护接口全通;无 token / 过期 → 401 → 前端跳登录。
- 两个用户学习数据完全隔离(SRS/塔/XP/streak)。
- Alembic 0003 upgrade/downgrade 通过;Vocab/GrammarPoint 不再有 SRS 列。
- 后端全量 + 前端全量测试绿;ruff 干净(预存 E501 除外)。
- 种子 dev 账号本地可直接登录使用。
