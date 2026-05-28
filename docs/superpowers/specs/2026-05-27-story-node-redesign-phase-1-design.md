# 追番日语 · 剧情节点重构（段 1）设计文档

- 日期：2026-05-27
- 状态：待用户审阅
- 上游 spec：`2026-05-22-anime-japanese-phase1-design.md`（不修改，本文档为其段 1 补充设计）
- 范围：仅段 1。段 2（quiz / 精读重写 / 复习嵌入 / celebration）做完段 1 后另立 spec。

---

## 1. 背景与动机

上游 spec 的"今日训练"愿景写得清楚：「**一集大约 3–6 天通关**」+「**每天 15–25 分钟一套流程**」。但当前实现把这套流程退化成了仪表盘：首页是 streak 大数字 + 到期数 + 当前剧集卡片，复习是独立 4 按钮自评的 Anki 风列表，精读是字幕滚动 + "推进 15 行"按钮。这是合格的学习工具，**不是让人不由自主想"再来一集"的产品**。

诊断（从产品视角）：

- 首页讲的是"工具仪表盘"而非"故事"。用户来追番，钩子应是剧情进展不是统计数字。
- "推进 15 行"暴露内部数据模型；"标记本集精读完成"把判定责任丢给用户，失去"系统让你过关"的感觉。
- Review 4 按钮自评反爽，没有连击 / 节奏。
- 五个 tab 是功能菜单；游戏从不让用户一打开就看到所有功能。
- 角色感完全没用上（用户追的是角色，UI 里只在 Conversation 出现头像 fallback）。
- 每天打开看到的内容一样，没有 variable reward。

本次重构以"**追番 = 走剧情节点路径**"为核心叙事，把"集"细化为"场景节点"，首页变成场景路径，导航从 5 tab 降为 2 tab，并通过 AniList 自动注入角色资产建立情感钩子。

为控制风险，重构拆为两段：

- **段 1（本文档）**：数据模型 + 加工流水线切场景 + 节点地图首页 + 2 tab 导航 + AniList 自动取角色。完成后剧情节点这条主轴已成立，但精读 / 复习 / 打卡的交互仍为旧的。
- **段 2（另立 spec）**：场景结束 quiz、精读页重写、复习嵌入主流程、打卡 celebration、角色头像在精读 / 对话页的显示。

---

## 2. 段 1 范围

### 2.1 包含

1. 新增 `Scene` 表，按场景索引现有 `Line`。
2. `Series` 加 AniList 关联字段（`anilist_id` / `anilist_status` / `characters`）。
3. `Episode` 加 `scenes_split` 状态字段。
4. 加工流水线 `process_episode` 前置一步「LLM 切场景」。
5. 新服务 `services/anilist.py`，封装 AniList GraphQL 查询。
6. 新增 / 修改 API：`POST /api/series`（改为后台拉 AniList）、`POST /api/series/{id}/refresh-anilist`、`GET /api/series/{id}`（加 AniList 字段）、`GET /api/episodes/{id}/scenes`、`GET /api/today/journey`。
7. 前端重写 `Today.tsx`（CharacterHeader + SceneTimeline）与 `Layout.tsx`（5 tab → 2 tab + 次级链接）。
8. 前端小改 `Series.tsx`（角色头像）和 `Reading.tsx`（支持 `?scene=N` 滚动 + 回看 banner）。
9. 后端 `init_app_db()` 扩展为幂等 ALTER，补齐新加字段。

### 2.2 不包含（明确留段 2 / 后续）

- Scene quiz 生成 / `SceneQuiz` 表 / 加工流水线第三步。
- `Vocab.quiz_cache` 字段及生词出题。
- 精读页"读完场景判定通关"交互、quiz 弹层、状态机。
- 复习嵌入主流程；4 按钮自评替换为系统出题判对错 + 连击数 + 结算动画。
- 打卡 celebration（全屏 confetti / 角色台词 / streak 跳动）。
- "今日金句" / variable reward 内容生成。
- 角色头像在精读 / Conversation 页的渲染。
- Conversation 页角色默认从 `Series.characters` 取（仍由用户敲）。
- 多语言（中文标题）AniList 模糊匹配。
- 前端测试基建（不引入新依赖）。
- Alembic 迁移（沿用 `create_all` + 幂等 ALTER）。

---

## 3. 数据模型变更

### 3.1 新表 `Scene`

```python
class Scene(Base):
    __tablename__ = "scene"
    __table_args__ = (UniqueConstraint("episode_id", "idx", name="uq_scene_episode_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episode.id"))
    idx: Mapped[int]                # 0-based，按出现顺序
    title_zh: Mapped[str]           # AI 生成的中文短标题，如"便利店发抖"
    start_line_idx: Mapped[int]     # 闭区间，对应 Line.idx
    end_line_idx: Mapped[int]       # 闭区间
    line_count: Mapped[int]         # 冗余存，方便首页直接显示
```

`Episode` ↔ `Scene` 一对多，`cascade="all, delete-orphan"`。

### 3.2 `Series` 加字段

```python
anilist_id: Mapped[int | None]
anilist_status: Mapped[str] = mapped_column(default="pending")
    # pending / matched / not_found / failed
characters: Mapped[list | None] = mapped_column(JSON, default=None)
    # [{"name_en": str, "name_jp": str, "image_url": str, "role": "MAIN" | "SUPPORTING"}]
```

### 3.3 `Episode` 加字段

```python
scenes_split: Mapped[bool] = mapped_column(default=False)
    # 场景切分是否完成；与 line 标注的 processed 解耦，独立断点续跑
```

### 3.4 场景三态 —— 完全派生，无新字段

- **done**：`Episode.read_position > scene.end_line_idx`
- **current**：`scene.start_line_idx <= Episode.read_position <= scene.end_line_idx`（含"刚解锁未读"）
- **locked**：`scene.start_line_idx > Episode.read_position`

### 3.5 Migration

项目用 `Base.metadata.create_all`，无 Alembic。Scene 是新表自动建；Series / Episode 的新列 `create_all` 不补。

方案：扩展 `app/db.py` 的 `init_app_db()`，在 `create_all` 之后执行幂等 `ALTER TABLE ... ADD COLUMN`，捕获 SQLite 的 "duplicate column name" 错误跳过。每次启动自检一次，单用户本地 SQLite 这是最轻方案。

不引 Alembic 的理由：段 1 净新增 3 列，运营成本远低于 Alembic 学习+维护成本。Phase 2/3 字段数膨胀再上 Alembic。

---

## 4. 服务层变更

### 4.1 加工流水线 `pipeline.py`

现状（保持不变的部分）：标 `processing` → 按 15 行批量 `llm.call_json` 注标 → 标 `ready` / `failed`。

新增前置步骤「切场景」：

```python
def process_episode(session, episode_id, batch_size=15):
    episode = session.get(Episode, episode_id)
    episode.status = "processing"; session.commit()

    if not episode.scenes_split:
        scenes = _split_scenes(episode, all_lines)     # 新：LLM 一次性切
        _validate_scenes(scenes, total_lines)          # 校验覆盖性
        _write_scenes(session, episode_id, scenes)
        episode.scenes_split = True
        session.commit()

    # 以下为现有逻辑，未改动
    for batch in batches(pending_lines, batch_size):
        result = llm.call_json(system=_SYSTEM, user=_build_user(batch, grammar_index))
        ...
    episode.status = "ready"; session.commit()
```

**切场景 LLM prompt 设计**：

- system：`你是动漫剧本场景切分助手。给定一集的全部台词，按对话聚集和角色切换切成 5–8 个场景（极少台词时 2–3 个也可）。返回 JSON：{"scenes":[{"title_zh":"5-10 字中文短标题","start_idx":整数,"end_idx":整数}]}。要求覆盖全部 idx 无空隙、无重叠。`
- user：JSON `{"lines":[{"idx":int, "text":str, "speaker":str|null}, ...]}`，全集
- 输入 token 估算：一集 ~250 行，每行 < 50 字 → 5–10k token 输入；输出几百 token。Sonnet 上下文充裕。每集净增 1 次 LLM 调用，成本约 $0.03。

**校验规则**（不通过则 `episode.status = "failed"` 并抛异常）：

- `len(scenes) >= 1`
- 排序后 `scenes[0].start_idx == 0`
- 排序后对相邻两场 `next.start_idx == prev.end_idx + 1`
- `scenes[-1].end_idx == total_lines - 1`
- 每场 `start_idx <= end_idx`
- `title_zh` 非空

**不退化策略**：切分失败 **不自动 fallback 为"整集一场景"**，因为那会让首页节点路径彻底没意义。用户看到 `failed` banner 主动重试。

**断点续跑**：`scenes_split=True` 后再次调用 `process_episode` 不重切场景，仅补 line 标注。

### 4.2 AniList 服务 `services/anilist.py`

```python
def fetch_series_metadata(title: str) -> dict | None:
    """查 AniList GraphQL。匹配返回 {"anilist_id": int, "characters": [...]}；
    无匹配返回 None；HTTP/JSON 错误抛异常由调用方处理。"""
```

GraphQL 查询：

```graphql
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
```

- 端点：`https://graphql.anilist.co`（公开、免 key）
- 用 `httpx`（项目已依赖），POST JSON，10 秒超时
- 单部番一次调用，无 batch / 无 retry，单用户本地无并发压力
- `characters` 字段按 AniList 返回顺序写入（已按 ROLE 排序），第一个为主角

**触发时机**：

- `POST /api/series` 创建 Series 行立即返回（含 `anilist_status="pending"`），用 FastAPI `BackgroundTasks` 异步调用 AniList。
- `POST /api/series/{id}/refresh-anilist` 同步重跑（按钮触发，**不算手动上传**，是无参数触发后端重查）。

**降级矩阵**：

| 情况 | `anilist_status` | 前端表现 |
|---|---|---|
| GraphQL 查不到 Media | `not_found` | 文字头像永久 |
| 找到 Media 但 characters 空 | `matched`（characters=[]） | 文字头像 |
| 主角 image 缺失 | `matched`（取下一个有图的 SUPPORTING） | 真头像或文字头像 |
| HTTP / JSON 错误 | `failed` | 文字头像 + 日志 |

### 4.3 `init_app_db()` 扩展

```python
def init_app_db() -> None:
    init_db(_engine)                       # 现有：create_all
    _migrate_in_place(_engine)             # 新：幂等 ALTER

def _migrate_in_place(engine):
    # 每列一行；用 try/except 吞 "duplicate column name" 错误
    _add_column_if_missing(engine, "series", "anilist_id", "INTEGER")
    _add_column_if_missing(engine, "series", "anilist_status", "VARCHAR DEFAULT 'pending'")
    _add_column_if_missing(engine, "series", "characters", "JSON")
    _add_column_if_missing(engine, "episode", "scenes_split", "BOOLEAN DEFAULT 0")
```

---

## 5. API 变更

### 5.1 修改 `POST /api/series`

行为：创建 Series 行后立即返回，**不阻塞**等 AniList。

请求 body 不变；响应新增字段：

```json
{
  "id": 3, "title": "孤独摇滚", "title_jp": "ぼっち・ざ・ろっく！", ...
  "anilist_status": "pending", "anilist_id": null, "characters": null
}
```

实现：用 FastAPI `BackgroundTasks` 注入；后台任务调 `anilist.fetch_series_metadata` 并更新行。后台异常捕获写日志、置 `anilist_status="failed"`，**绝不让异常逃出后台任务**。

### 5.2 新增 `POST /api/series/{id}/refresh-anilist`

无 body；同步重跑 AniList 查询；返回更新后的 Series。错误同样转为 `anilist_status="failed"`，HTTP 状态仍 200（用 status 字段表达业务结果）。

### 5.3 修改 `GET /api/series/{id}`

响应里多 `anilist_status`、`anilist_id`、`characters` 字段。

### 5.4 新增 `GET /api/episodes/{id}/scenes`

```json
[
  {"id": 1, "idx": 0, "title_zh": "便利店发抖", "line_count": 23,
   "start_line_idx": 0, "end_line_idx": 22, "state": "done"},
  {"id": 5, "idx": 4, "title_zh": "凉的电吉他", "line_count": 28,
   "start_line_idx": 117, "end_line_idx": 144, "state": "current",
   "preview_lines": ["ねぇ、ぼっちちゃん、これ弾ける？", "あ、あの、ちょっと…"]},
  {"id": 6, "idx": 5, "title_zh": null, "line_count": null,
   "start_line_idx": null, "end_line_idx": null, "state": "locked"}
]
```

- `state=locked` 的场景**服务端脱敏**：`title_zh / line_count / start_line_idx / end_line_idx` 全部置 `null`，仅保留 `id` 和 `idx`。剧透防护由后端保证而非前端"假装隐藏"。
- `state=current` 多 `preview_lines`：取该场首 2 行 `text_jp`。
- 加工尚未完成（`episode.status != "ready"` 或 `scenes_split=False`）→ 返回空数组 `[]`，HTTP 200。前端据此显示骨架。

### 5.5 新增 `GET /api/today/journey`（替代 `GET /api/today`）

```json
{
  "streak": 7,
  "due_total": 12,
  "series": {
    "id": 3, "title": "孤独摇滚",
    "main_character": {
      "name_jp": "後藤ひとり", "image_url": "https://...",
      "fallback_initial": "後"
    }
  },
  "current_episode": {
    "id": 42, "number": 5, "title": "...",
    "read_position": 117, "total_lines": 247,
    "completed_scenes": 4, "total_scenes": 8,
    "status": "ready"
  },
  "scenes": [ /* 同 §5.4 */ ]
}
```

- 无 current series → `series: null`、其它字段缺省
- 有 series 无 episode → `current_episode: null`、`scenes: []`
- `main_character` 取 `Series.characters` 中第一个有 `image_url` 的对象；若都没有 `image_url` 但有 character，仍返回首个 character 且 `image_url: null`；若 series 无 character → `main_character: null`
- `fallback_initial` 永远非 null：优先取 character `name_jp` 首字符；`name_jp` 为 null 时取 `name_en` 首字符；`main_character` 整体为 null 时取 `series.title` 首字符。**前端只读这个字段决定文字头像，不再自己判断 name 字段**
- `main_character.name_jp` 可能为 null（AniList `name.native` 缺失）；前端显示名字时按"name_jp || name_en"降级
- 原 `GET /api/today` 在 commit #5 中删除（单用户本地无需过渡期）

### 5.6 保留不动

`GET /api/episodes/{id}/lines`、`POST /api/episodes/{id}/reading-progress`、`/api/review/*`、`/api/grammar/*`、`/api/progress/*`、`/api/conversation/*` 全部段 1 兼容。

---

## 6. 前端变更

### 6.1 路由 / 导航

```
顶部：[追番日语]  今天 · 我的番剧库          📚 语法 · 📈 进度   [音色选择器]
                  ─────  ──────────         ↑次级浅灰小字↑
                   主 tab
```

- 主导航 2 tab：`/`、`/series`
- 次级链接：`/grammar`、`/progress` 缩在右侧浅灰小字
- `/review` 不在导航；仅通过 Today 页 "🧠 N 到期 →" chip 进入
- 现有路由全部保留可访问

### 6.2 页面 / 组件变更

| 页面 / 组件 | 段 1 状态 | 说明 |
|---|---|---|
| `Layout.tsx` | 重写 | 2 主 tab + 次级链接 |
| `Today.tsx` | 重写 | `CharacterHeader` + `SceneTimeline` + streak/due chip |
| `SceneTimeline.tsx` | 新增 | 章节书风列表，3 态视觉化 |
| `CharacterHeader.tsx` | 新增 | 头像（含 fallback）+ 番剧/集/进度文字 |
| `Series.tsx` | 小改 | 列表行显示角色头像（有 characters 时） |
| `Reading.tsx` | 小改 | 支持 `?scene=N`：进入时滚到该场首行；若该场 end_line_idx < read_position，顶部出现"回看"banner |
| `Review.tsx` / `Grammar.tsx` / `Progress.tsx` / `Conversation.tsx` | 不动 | 段 1 仅在主导航降级 |

### 6.3 `SceneTimeline.tsx` 交互

```
✓  场景 1 · 便利店发抖           23 行     ← 灰色，点击 = 进入 Reading（?scene=0），不动 read_position
✓  场景 2 · 乐队相遇             41 行
✓  场景 3 · 第一次排练           35 行
✓  场景 4 · 凉到家               18 行
▶  场景 5 · 凉的电吉他           28 行     ← 高亮卡片，默认展开
   ┌─────────────────────────────────┐
   │ 「ねぇ、ぼっちちゃん、これ弾ける？」  │
   │ 「あ、あの、ちょっと…」              │
   │              [继续读这一场 →]      │   ← 跳 Reading 页，不动 read_position
   └─────────────────────────────────┘
🔒 场景 6 · ???                            ← 单行，灰色，无标题/行数，不可点
🔒 场景 7 · ???
🔒 场景 8 · ???
```

- "继续读这一场"：跳 `/episodes/{id}/reading?scene={current.idx}`，**不 reset `read_position`** —— 用户在场景中段离开就在中段恢复
- 已读场景点击：同上语法，`read_position` 不变（回看）
- 锁定行：无 onClick；视觉上明显置灰

### 6.4 `CharacterHeader.tsx` 状态

| AniList 状态 | 表现 |
|---|---|
| `pending` | 文字 fallback 圆圈头像；TanStack Query 每 3s 轮询 `/series/{id}`，最多 10 次（30s）；超时仍 pending 视作失败显示文字 |
| `matched` 有 image_url | `<img>` 真头像 |
| `matched` 无可用 image | 文字 fallback |
| `not_found` / `failed` | 文字 fallback + Series 详情页有"重新匹配"按钮 |

### 6.5 `Reading.tsx` 回看 banner

当 `?scene=N` 且 `scenes[N].end_line_idx < ep.read_position`：

```
┌─────────────────────────────────────┐
│ 你在回看场景 2 · 当前进度在场景 5    │
│                      [回到当前 →]   │
└─────────────────────────────────────┘
```

点击"回到当前" → 滚到 `current scene.start_line_idx` 行。

---

## 7. 边界场景与错误处理

| 场景 | 处理 |
|---|---|
| 新用户、零番剧 | Today 空态："去导入你在追的第一部番 →"（链 `/series`） |
| 有 Series 无 episode | "《X》还没有任何一集，去导入第一集 →" |
| Episode `importing` / `processing` | Timeline 显示骨架 + "正在加工（约 30–60 秒）…"；每 5s 轮询 `/episodes/{id}/scenes`，`status=ready` 后停 |
| Episode `failed` | 红色 banner："本集加工失败" + [重试] 按钮（触发已有 pipeline 重跑） |
| `scenes_split=True` 但 line 标注未全 | Timeline 已可显示；Reading 页部分行无翻译（沿用现状） |
| 切场景 LLM 返回非法 JSON / 校验失败 | `status=failed`，**不退化为"整集一场景"** |
| Episode 已读完（`read_position >= total_lines`） | Timeline 顶部 banner："本集已读完 · [开始下一集 →]"（下一集按 `series_id + number+1` 查） |
| 点击进行中场景"继续读" | 跳 Reading，**不 reset `read_position`** |
| 点击已读场景"重读" | 跳 Reading `?scene=N`；`read_position` 不变；出现"回看"banner |
| 点击锁定场景 | 无响应（无 onClick） |
| AniList `pending` 超时 | TanStack Query 10 次轮询后停；视作失败显示文字头像 |
| AniList 中文标题匹配不到 | `not_found`；用户可编辑 Series 加 `title_jp` 后点"重新匹配" |
| AniList 主角无图 | 取下一个有图的角色；都没有则文字 fallback |

---

## 8. 测试

沿用项目现有 pytest + per-service / per-router 风格。

### 8.1 新增 / 修订 backend 测试

| 文件 | 覆盖 |
|---|---|
| `test_models_scene.py`（新） | Scene 唯一性约束、cascade delete |
| `test_pipeline_scenes.py`（新） | mock `llm.call_json`：正常 5–8 场景；空响应 → fail；空隙 → 校验失败；重叠 → 校验失败；`scenes_split=True` 时重跑不重切 |
| `test_anilist.py`（新） | `httpx.MockTransport` mock GraphQL：匹配成功提取主角；0 结果返回 None；HTTP 5xx 抛异常；JSON 异常抛异常 |
| `test_api_today_journey.py`（新） | 无 Series；有 Series 无 Episode；三态混合；锁定场景脱敏 |
| `test_api_series.py`（修订） | `POST /api/series` 立即返回 `pending`；BackgroundTasks 注入同步 stub；`refresh-anilist` 触发重查；AniList 错误转 `failed` |
| `test_api_episodes.py`（修订） | `GET /api/episodes/{id}/scenes` 三态返回；锁定脱敏 |

### 8.2 前端测试

段 1 **不引入**前端测试框架（保持"段 1 不引新依赖"原则）。前端靠：

- `npm run build` 与 TypeScript 通过
- 8.3 手动验证清单

### 8.3 手动验证清单

- [ ] 全新数据库启动，导入一部主流番（如《孤独摇滚》）的一集字幕，Today 出现节点 timeline
- [ ] 加工中显示骨架；加工完出 5–8 场景
- [ ] 点"继续读这一场" → Reading 正确滚到该场首行；`read_position` 不变（中段离开后回来还在中段）
- [ ] 点已读场景重读 → Reading `?scene=N` 滚到该场；显示"回看"banner；点"回到当前"滚回当前场首
- [ ] 锁定场景不可点击，无标题/行数
- [ ] AniList 命中（《孤独摇滚》）→ 角色头像 30s 内替换
- [ ] AniList 不命中（输一个假番名）→ 文字 fallback 永久
- [ ] 加工失败（mock LLM 返回非法 JSON）→ banner + 重试可恢复
- [ ] Episode 已读完 → 顶部 "本集已读完 · 开始下一集"
- [ ] 5 tab 完全消失，仅剩 "今天 / 我的番剧库" 主 tab + "语法 / 进度" 次级链接；旧 `/review` URL 直接访问仍可用

---

## 9. 性能 / 成本 / 安全

- **LLM 调用增量**：每集 +1 次切场景调用（Sonnet ~$0.03）
- **AniList**：每部番 +1 次 GraphQL（免费、~200ms）
- **首页请求**：`/today/journey` 一次返回全部，TanStack Query 缓存到 invalidate；轮询仅在 episode/anilist `pending` 时
- **AniList 图链**：前端 `<img src>` 直接引 CDN，不下载到本地（避免存储 + 许可问题）
- **隐私**：AniList 无 key 无用户数据上传；单用户本地应用，无鉴权变化

---

## 10. 实施顺序

5 个 commit，前后端解耦，每个 commit 自带通过测试：

| # | Commit 标题 | 内容 | 阻塞 |
|---|---|---|---|
| 1 | `feat(db): add Scene table, anilist fields, scenes_split` | Scene 模型 + Series/Episode 字段 + `init_app_db` 幂等 ALTER + 模型测试 | 阻 #3, #4 |
| 2 | `feat(services): add AniList GraphQL client` | `services/anilist.py` + 测试 | 阻 #4 的 AniList 触发 |
| 3 | `feat(pipeline): scene splitting before line annotation` | `pipeline.py` 前置切场景 + `_split_scenes` + `_validate_scenes` + 测试 | 阻 #4 的 scenes 端点 |
| 4 | `feat(api): today/journey, scenes endpoint, anilist hooks` | 新 / 改 API + BackgroundTasks + 测试 | 阻 #5 |
| 5 | `feat(web): scene timeline home, 2-tab nav, AniList header` | Layout / Today / Series / Reading 改动；删除后端 `GET /api/today` 端点及其测试；手动验证清单跑一遍 | — |

#1–#4 完成后即可通过 pytest + 手动 curl 完整跑通后端；#5 完成才上线 UI 改造。

---

## 11. 段 2 待办（防遗漏，写完段 1 后开新 spec）

- `SceneQuiz` 表 + 加工流水线第三步生成 quiz
- `Vocab.quiz_cache` 字段 + 生词出题
- 精读页"读完场景判定通关"交互
- 复习嵌入主流程：场景结束自动混入旧词 quiz；4 按钮自评 → 系统出题判对错 + 连击数 + 结算动画
- 打卡 celebration：全屏 confetti、角色台词、streak 跳动
- "今日金句" / variable reward
- 角色头像在精读 / Conversation 页的渲染
- Conversation 页 character 默认从 `Series.characters` 取
