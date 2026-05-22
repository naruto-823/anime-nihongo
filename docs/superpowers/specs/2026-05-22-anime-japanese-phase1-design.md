# 追番日语 · Phase 1 设计文档

- 日期：2026-05-22
- 状态：待用户审阅
- 范围：Phase 1（核心闭环）。Phase 2/3 仅作为路线图列出，不在本文档实现范围内。

---

## 1. 背景与目标

**用户画像**：日语 N2 已过（120 分），中上水平。阅读、语法、词汇有底子，但 N2 不考口语，口语是明显短板。热爱看动漫。

**三个诉求**：
1. 每天进步 —— 有稳定的每日节奏和可见的坚持反馈。
2. 基础扎实 —— 把"勉强会"变成"真的牢"，词汇和语法可系统追踪。
3. 口语更强 —— 真正能开口、能连贯输出。

**核心理念**：**你在追的番 = 你的教材。** 软件是"追番时的随身学习搭子"，把用户正在看的每一集动漫，变成一套全方位（听说读写）的日语训练。

**产品形态**：本地运行的网页应用。一条命令启动，浏览器打开一个本地网址即可使用。所有数据和密钥都在用户自己机器上，不外传。

### 1.1 整体愿景（背景，非本期范围）

追番驱动：用户告诉软件"我在看《X》第 N 集" → 这一集变成一个学习单元 → 导入台词 → 自动加工 → 分阶段啃完（精读 / 听写听辨 / 配音跟读 / 角色对话 / 剧情复述）。每天打开 = 一套"今日训练"（约 15–25 分钟，走完打卡 +1）。一集大约 3–6 天通关。

### 1.2 路线图

| 阶段 | 内容 | 关键依赖 |
|------|------|----------|
| **Phase 1（本文档）** | 字幕导入、加工流水线、精读、词汇/语法双 SRS、N2/N1 语法清单、角色对话、今日训练 + 打卡 | fox 网关、Jimaku API、SudachiPy、Web Speech API |
| Phase 2 | 听写听辨、配音跟读、剧情复述、Whisper 转写兜底、ffmpeg 切音频/截图、ImmersionKit 例句弹药 | + Whisper、ffmpeg、ImmersionKit API |
| Phase 3 | 语体雷达深化、看前预习、多番管理、进度可视化增强、每周回顾 | — |

Phase 2、Phase 3 各自单独走"设计 → 计划 → 实现"流程。

**Phase 1 已覆盖全部三个诉求**：每天进步（今日训练 + 连续打卡）、基础扎实（双 SRS + 语法清单）、口语更强（角色对话，且每日训练必含开口环节）。Phase 1 刻意不依赖 Whisper/ffmpeg，以求最快可用。

---

## 2. Phase 1 范围

### 2.1 包含

- **番剧与剧集管理**：登记一部番、管理它的剧集。
- **台词导入**：两条路径 —— (A) 通过 Jimaku API 搜索并下载整集字幕；(B) 用户手动上传字幕文件（.srt / .ass）。
- **加工流水线**：字幕解析 → SudachiPy 分词与注音 → Claude 批量产出翻译、语法拆解、语体标注、语法点匹配 → 落库。可断点续跑。
- **精读**：逐句阅读视图，假名注音、按需翻译、语法拆解、语体标注；一键把生词/语法加入复习。
- **双 SRS**：词汇 SRS + 语法 SRS，SM-2 间隔重复算法。
- **N2/N1 语法清单**：内置一份精选语法点清单，番里出现即点亮，可视化全貌掌握度。
- **角色对话**：Claude 扮演当前番里的角色，用户用麦克风说日语对话，结束后获得纠错与地道化反馈。
- **今日训练**：每日把"复习 + 推进当前集 + 开口 + 小结"编排成一套约 15–25 分钟的流程。
- **打卡与进度**：连续打卡、训练历史、语法清单覆盖度、词汇牌组统计。

### 2.2 不包含（明确排除，留给后续阶段）

- 音频相关：听写听辨、配音跟读（需 Phase 2 的音频）。
- Whisper 自动转写、ffmpeg 切音频/截图。
- ImmersionKit 例句库集成。
- 剧情复述（写作输出）、看前预习。
- 多用户、登录鉴权（Phase 1 为单用户单机）。
- 移动端适配（仅桌面浏览器）。
- 同时主攻多部番（可登记多部，但"今日训练"只推进一部"当前番"）。

---

## 3. 技术架构

沿用用户现有 trading 项目（`~/Desktop/work/ai/trading`）的技术栈，以便配置复用与单一语言维护。

### 3.1 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite + Anthropic SDK + httpx + SudachiPy。Python ≥ 3.11。
- **前端**：React + Vite + TypeScript + Tailwind CSS + shadcn/ui + TanStack Query。
- **语音**：浏览器 Web Speech API —— STT（语音识别，`lang=ja-JP`）+ TTS（语音合成，日语音色）。
- **AI 网关**：fox 网关。用官方 `anthropic` SDK，通过 `base_url` 指向网关，协议为 Anthropic 原生 `/v1/messages`。

### 3.2 进程与运行

- 单个本地后端进程（FastAPI / uvicorn），同时：提供 `/api/*` 接口、托管前端构建产物、持有所有密钥、拥有 SQLite 数据库。
- 开发模式：后端 `uvicorn`（默认 8000）、前端 `vite`（默认 5173）分别启动；前端开发服务器代理 `/api` 到后端。
- 生产/日常使用：前端 `vite build` 产物由后端静态托管，用户只需启动后端、开一个网址。
- 沿用 trading 项目的 `Makefile` 风格：`make setup` / `make dev` / `make test` / `make lint`。

### 3.3 浏览器要求

Web Speech API 的语音识别（STT）仅在 **Chrome / Edge** 可靠工作。Safari / Firefox 不支持或不稳定。README 必须明确写出"请用 Chrome 或 Edge 打开"。STT 不可用时降级为打字输入（见 §8）。

### 3.4 配置（`.env`，照搬 trading 项目写法）

```
# AI 网关（fox）—— Anthropic 原生协议
ANTHROPIC_API_KEY=***
ANTHROPIC_BASE_URL=https://code.newcli.com/claude/aws
ANTHROPIC_MODEL=claude-sonnet-4-6          # 加工与对话默认模型
ANTHROPIC_MODEL_LIGHT=claude-haiku-4-5-20251001   # 备用：低成本批量任务

# Jimaku 字幕 API
JIMAKU_API_TOKEN=***                        # jimaku.cc 免费注册获取

# 数据库
DATABASE_URL=sqlite:///./data/anime-nihongo.db
```

注意：fox 网关对部分模型要求带完整日期后缀（如 `claude-haiku-4-5-20251001`，非简写）。模型 ID 一律走 `.env`，便于按网关实际可用值调整。`.env` 不入库（`.gitignore`），随附 `.env.example`。

### 3.5 项目结构

```
anime-nihongo/
  .env / .env.example / .gitignore / Makefile / README.md
  backend/
    pyproject.toml
    app/
      main.py            # FastAPI 入口、静态托管
      config.py          # pydantic-settings，读 .env
      db.py              # SQLAlchemy engine / session
      models/            # ORM 模型
      api/               # 路由：series / episodes / study / srs / conversation / progress
      services/
        subtitles.py     # .srt/.ass 解析
        jimaku.py         # Jimaku API 客户端
        tokenizer.py     # SudachiPy 封装：分词 + 注音
        pipeline.py      # 加工流水线编排
        llm.py           # Anthropic 客户端封装 + 重试
        srs.py           # SM-2 间隔重复算法
        session.py       # 今日训练编排
      data/
        grammar_seed.json  # 内置 N2/N1 语法清单种子
    tests/
  frontend/
    package.json / vite.config.ts / tsconfig.json / tailwind.config.ts
    src/
      pages/             # 今日训练 / 番剧库 / 精读 / 复习 / 角色对话 / 语法清单 / 进度
      components/
      lib/               # api 客户端、Web Speech API 封装
  docs/superpowers/specs/
```

---

## 4. 数据模型（SQLite / SQLAlchemy）

为简化，SRS 字段内联在 `vocab` 与 `grammar_point` 上，不另建表。

### `series`（番剧）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| title | text | 显示名（中文/通用名） |
| title_jp | text | 日文原名，可空 |
| jimaku_entry_id | int | 对应 Jimaku 条目 id，可空 |
| is_current | bool | 是否为"当前主攻番"（全表至多一条 true） |
| created_at | datetime | |

### `episode`（剧集）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| series_id | int FK | |
| number | int | 集数 |
| title | text | 可空 |
| source | text | `jimaku` / `upload` |
| status | text | `importing` / `processing` / `ready` / `failed` |
| processed_lines | int | 已加工行数（进度展示） |
| total_lines | int | 总行数 |
| read_position | int | 精读已推进到的行 idx |
| reading_done | bool | 精读是否完成 |
| imported_at | datetime | |

### `line`（台词）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| episode_id | int FK | |
| idx | int | 集内顺序 |
| start_ms / end_ms | int | 字幕时间轴，end 可空 |
| speaker | text | 说话人，可空（字幕里有则取） |
| text_jp | text | 原文 |
| furigana | json | SudachiPy 注音的 ruby 分段 |
| translation_zh | text | 中文翻译 |
| grammar_notes | json | 语法拆解条目数组 |
| register_tag | text | 语体标注（见 §5.3） |
| grammar_point_keys | json | 命中的语法清单 key 数组 |
| processed | bool | 是否已加工（断点续跑用） |

### `vocab`（词条，内联 SRS）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| headword | text | 辞书形 |
| reading | text | 读音 |
| meaning_zh | text | 中文释义 |
| pos | text | 词性 |
| jlpt_level | text | 估计等级，可空 |
| source_line_id | int FK | 首次出现的台词（复习时展示原句语境） |
| in_srs | bool | 是否已加入复习队列 |
| ease / interval_days / reps / lapses | — | SM-2 状态 |
| due_date | date | 下次复习日，可空 |
| last_reviewed | datetime | 可空 |

唯一约束：`(headword, reading)` 去重。同词跨集再现只更新 `source_line_id` 不新建。

### `grammar_point`（语法点，内联 SRS）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| key | text unique | 稳定标识，如 `ni-atatte` |
| name | text | 如 「〜にあたって」 |
| jlpt_level | text | `N2` / `N1` 等 |
| explanation | text | 简短讲解 |
| curated | bool | 是否来自内置清单种子 |
| status | text | `locked`（未遇到）/ `seen`（遇到过）/ `learning`（已入 SRS） |
| quiz_cache | json | 预生成的小测题，缓存复用 |
| source_line_id | int FK | 首次出现的台词，可空 |
| in_srs | bool | |
| ease / interval_days / reps / lapses / due_date / last_reviewed | — | SM-2 状态 |

### `daily_session`（今日训练记录 / 打卡）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| date | date unique | 每天一条 |
| completed | bool | 是否走完 |
| episode_id | int FK | 当日推进的剧集 |
| vocab_reviewed / grammar_reviewed | int | 复习数量 |
| lines_read | int | 当日精读行数 |
| conversation_turns | int | 当日对话轮数 |
| summary | json | 小结（新增词、薄弱项、明日预告） |
| created_at | datetime | |

### `app_setting`（单行键值，应用级状态）
存放：每日训练目标值（复习上限、精读行数上限）、连续打卡数缓存等。连续打卡数亦可由 `daily_session` 实时推算，缓存仅为展示加速。

---

## 5. 功能详述

### 5.1 番剧导入

**登记番剧**：用户输入番名 → 调 Jimaku 搜索 → 选定一个条目 → 建 `series`。也支持纯手动建（不依赖 Jimaku）。

**导入一集台词**，两条路径：
- **路径 A · Jimaku**：按 `series.jimaku_entry_id` 列出该番的字幕文件 → 用户选定某一集 → 后端下载字幕文件。
- **路径 B · 手动上传**：用户直接上传 `.srt` 或 `.ass` 文件。

**字幕解析**（`services/subtitles.py`）：
- `.srt`：解析序号、时间轴、文本。
- `.ass`：解析 `[Events]` 段的 `Dialogue:` 行，**剥离样式标签**（`{\...}`）、换行符规整、按开始时间排序。
- 输出统一的行列表（idx、start_ms、end_ms、speaker?、text）。
- 解析失败的行：跳过并记录，不中断整集导入。

导入后建 `episode`（status=`processing`）与全部 `line`（`processed=false`），随即触发加工流水线。

### 5.2 加工流水线（`services/pipeline.py`）

后台任务（FastAPI `BackgroundTasks` 或后台线程），可断点续跑。

1. **分词与注音**（本地，SudachiPy）：对每行分词，取每个词的辞书形与读音 → 生成 `furigana` ruby 分段；汇总词频，标出 N2/N1 及以上、较生僻的候选词。
2. **批量 LLM 加工**（fox / Claude）：按 ~15 行一批调用 Claude，对每行产出：
   - `translation_zh`：中文翻译。
   - `grammar_notes`：句中值得讲的语法点拆解（数组）。
   - `register_tag`：语体标注。
   - `grammar_point_keys`：命中内置语法清单的 key（提示词中带上清单的 key+name 供匹配）。
   - 对该批出现的候选词补充 `meaning_zh`、`pos`、`jlpt_level`。
3. **落库**：写回 `line`，置 `processed=true`，累加 `episode.processed_lines`；命中的 `grammar_point` 由 `locked` → `seen`，写 `source_line_id`；候选词写入 `vocab`（`in_srs=false`）。
4. 全部完成 → `episode.status=ready`。

**断点续跑**：每行 `processed` 标志；流水线启动时只处理 `processed=false` 的行。LLM 调用失败按 §8 重试；整批失败可重跑。

**成本量级**：一集 ~300–500 行，批量加工约几十次 Claude 调用，约 ¥0.x–2 / 集（一次性）。

### 5.3 精读

剧集就绪后进入精读视图：台词像剧本一样逐行排列。

- 每行：日文原文（假名注音可整体开关）；点击展开 → 中文翻译、语法拆解、语体标注。
- **语体标注**（`register_tag`）取值：`polite`（礼貌体）/ `casual`（普通简体）/ `rough`（粗俗/男言葉等）/ `feminine`（女言葉）/ `dialect`（方言）/ `archaic` 等。对 `rough` / `feminine` / `dialect`，加工时附带"现实礼貌场合的等价说法"，存入 `grammar_notes`。这是"语体雷达"的 Phase 1 形态：防止动漫口语把表达带偏。
- **加入复习**：点词 → 该 `vocab` 置 `in_srs=true`，设为次日到期；点语法拆解里的语法点 → 对应 `grammar_point` 置 `in_srs=true`、`status=learning`、次日到期。也可"本行全部生词加入"。
- 精读按"今日训练"配额分天推进，`episode.read_position` 记录进度；推进到末行则 `reading_done=true`。

精读不强制把所有候选词加入 SRS —— 由用户决定，避免牌组膨胀。

### 5.4 双 SRS（`services/srs.py`）

词汇 SRS 与语法 SRS 共用 **SM-2** 算法。

**词汇复习卡**：展示 `headword` → 用户回想读音与释义 → 揭示答案，并显示该词来源台词（`source_line_id`）作为语境 → 评分。
**语法复习卡**：展示语法点 → 一道 Claude 生成的小测题（从 `quiz_cache` 取，用尽则补生成）→ 作答 → 揭示讲解 → 评分。

评分档位与算法见 §7。每日复习量受 `app_setting` 配额限制（默认词汇 ≤30、语法 ≤12，可调）。

### 5.5 N2/N1 语法清单

- 随应用内置一份精选语法点种子（`backend/app/data/grammar_seed.json`，约 150–250 条，以 N2 为主、含部分高频 N1），字段：`key` / `name` / `jlpt_level` / `explanation`。首次启动写入 `grammar_point`，`curated=true`、`status=locked`。
- 番里命中（加工流水线匹配到）→ `locked` → `seen`；用户加入复习 → `learning`。
- **语法清单页**：按 JLPT 等级分组展示全部清单条目及其状态；`learning` 条目按 SRS 区间显示掌握度（区间超过阈值视为"已掌握"）。给用户"整张语法地图覆盖了多少"的全局感 —— 这是"基础扎实"的可视化锚点。
- 加工时若识别到清单之外的语法点，可新建 `grammar_point`（`curated=false`），同样可入 SRS，但不计入"清单覆盖度"。

### 5.6 角色对话

Phase 1 的开口训练。

- **发起**：基于当前番/当前集。Claude 扮演该番中的一个角色，场景为"讨论这一集剧情"或"如果当时…"的假设展开。提示词上下文带入：番名、集数、当日精读涉及的台词片段。
- **进行**：用户用麦克风说日语 → Web Speech API STT 转写（`ja-JP`）→ 文本发给 Claude → Claude 以角色口吻回应（文本 + `speechSynthesis` 朗读）。
- **轮数**：精读进行中的每日训练里穿插 2–4 轮"短对话"（保证每天都开口）；整集精读完成后做一次 5–8 轮的"完整对话"。
- **结束反馈**：Claude 复盘用户的全部发言 → 给出纠错、更地道的说法、语体提醒；其中的生词/薄弱语法回流到对应 SRS（生词 → `vocab` 入 SRS；薄弱语法 → 命中清单则该 `grammar_point` 入 SRS）。
- STT 不可用时降级为打字（见 §8）。

### 5.7 今日训练与打卡（`services/session.py`）

**今日训练**把当天内容编排成一套约 15–25 分钟的流程：

1. **复习**：词汇 + 语法 SRS 当日到期项（受配额限制）。
2. **推进当前集**：
   - 若当前集精读未完 → 推进今日精读配额（默认 ~15–25 行）。
   - 若精读已完 → 进入该集的完整角色对话。
3. **开口环节**：精读阶段的每日训练，在第 2 步后追加一段 2–4 轮短对话（话题取自当日精读台词）。**保证每天必有开口。**
4. **小结**：当日新增词数、薄弱项、连续打卡数 +1、明日预告。写入 `daily_session`。

**打卡 / 连续天数**：完成今日训练（`daily_session.completed=true`）即当日打卡。连续打卡数 = 连续每日都有 completed 记录的天数；中断则归零。

**当前集推进完毕**：`reading_done` 且完整对话完成 → 该集"通关"；用户导入同番下一集继续。

**进度页**：连续打卡日历热力图、训练历史、语法清单覆盖度、词汇牌组规模与到期分布、各集通关状态。

---

## 6. 外部集成

### 6.1 fox 网关 / Anthropic（`services/llm.py`）

- 用官方 `anthropic` SDK：`Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url or None)`。
- 模型走 `.env`：默认 `ANTHROPIC_MODEL`（加工、对话、反馈、出题）；`ANTHROPIC_MODEL_LIGHT` 留作低成本批量任务的可选项。
- 封装统一的调用入口：注入 system prompt、强制 JSON 输出的任务做 JSON 解析与校验、失败重试（见 §8）。
- 参考 trading 项目 `services/briefing.py`、`services/relevance_scorer.py` 的客户端构造方式。

### 6.2 Jimaku API（`services/jimaku.py`）

- httpx 客户端，`Authorization` 头携带 `JIMAKU_API_TOKEN`。
- 用到的能力：按番名搜索条目、列出条目的字幕文件、下载指定字幕文件。
- 具体端点与字段以 [jimaku.cc/api/docs](https://jimaku.cc/api/docs) 为准，在实现期对照确认。
- 失败（无结果 / 下载失败 / 无 token）→ 提示用户改用手动上传（路径 B）。

### 6.3 Web Speech API（前端 `lib/`）

- **STT**：`webkitSpeechRecognition`，`lang='ja-JP'`，用于角色对话输入。
- **TTS**：`speechSynthesis`，选日语音色（macOS 自带 Kyoko/Otoya 质量可用），用于朗读台词与 Claude 的对话回应。
- 封装为统一的 hook/模块，含能力检测与降级。

---

## 7. SRS 算法（SM-2）

每个 SRS 项（`vocab` / `grammar_point`）状态：`ease`（默认 2.5，下限 1.3）、`interval_days`、`reps`、`lapses`、`due_date`、`last_reviewed`。

**评分档位**：`again`（又错了）/ `hard`（有点难）/ `good`（会了）/ `easy`（很简单）。语法小测：答错 → `again`；答对后由用户在 `hard/good/easy` 自评。

**更新规则**：
- `again`：`reps=0`、`interval_days=0`（当日重排）、`lapses+=1`、`ease-=0.20`。
- `hard`：`interval_days = max(1, round(interval_days * 1.2))`、`ease-=0.15`。
- `good`：`reps==0` → `interval=1`；`reps==1` → `interval=6`；否则 `interval = round(interval * ease)`。`reps+=1`。
- `easy`：在 `good` 基础上 `interval = round(interval * ease * 1.3)`、`ease+=0.15`。
- `ease` 钳制于 `[1.3, +∞)`；`due_date = today + interval_days`。

新项加入时 `ease=2.5, interval_days=0, reps=0, lapses=0, due_date=次日`。

"已掌握"判定（用于语法清单可视化）：`interval_days ≥ 21` 且 `lapses` 近期为 0。阈值放入常量，便于调整。

算法为纯函数，单元测试全覆盖（见 §9）。

---

## 8. 错误处理

- **Jimaku 无结果 / 下载失败 / 无 token**：明确提示并引导改用手动上传。
- **字幕解析**：坏行跳过并计数，不中断整集；整体无法解析 → `episode.status=failed` 并给出原因。
- **LLM 调用失败**：指数退避重试（参考 trading 项目 `debate_api_max_retries`，默认重试 ~5 次，扛中转网关突发 429）。加工流水线靠 `line.processed` 断点续跑；可重跑失败批次。
- **LLM 返回非法 JSON**：对要求结构化输出的任务做解析校验，失败则按"该调用失败"重试；连续失败则该批标记失败、不污染数据。
- **Web Speech API STT 不可用 / 识别为空**：角色对话降级为打字输入框，功能不阻断。
- **fox 网关不可达**：前端给出清晰错误与重试入口，不静默失败。
- **加工进行中**：精读视图允许访问已加工的行，未加工行显示"加工中"。

---

## 9. 测试策略

沿用 trading 项目的 pytest 配置（`pytest` + `pytest-asyncio`，`asyncio_mode=auto`）。

**后端单元测试（重点，纯逻辑全覆盖）**：
- `subtitles.py`：.srt / .ass 解析，含样式标签剥离、坏行跳过、时间轴解析。
- `srs.py`：SM-2 各评分档位的状态转移、ease 钳制、新项初始化、"已掌握"判定。
- `session.py`：今日训练编排（精读阶段 vs 对话阶段、配额、开口环节注入）、连续打卡天数推算（含中断归零）。
- `jimaku.py`：HTTP 打桩测试搜索/列文件/下载。
- `pipeline.py`：LLM 打桩，验证编排、断点续跑、落库与 `grammar_point` 状态流转。

**前端**：角色对话流程、复习流程等关键交互做组件测试；Web Speech API 在测试中打桩。

**集成**：用一个小字幕样本走通"导入 → 加工（LLM 打桩）→ 精读 → 加入 SRS → 今日训练 → 打卡"全链路。

实现遵循 TDD：先写测试。

---

## 10. 风险与权衡

- **Web Speech API STT 质量**：浏览器识别对发音不准/语速快的容错有限，且限 Chrome/Edge。权衡：Phase 1 用它换"零额外成本、零额外依赖"，并以打字降级兜底；Phase 2 可评估更强的语音方案。
- **语法点匹配准确度**：靠 LLM 把台词匹配到清单 key，可能漏匹配或误匹配。权衡：清单覆盖度作"参考性进度"而非精确考核；用户在精读中手动加入语法仍是主路径。
- **加工成本与时长**：整集加工是一批 LLM 调用，有耗时与费用。权衡：后台跑 + 进度展示 + 断点续跑；批大小可调。
- **Jimaku 覆盖**：冷门番可能无字幕。Phase 1 以手动上传兜底；自动转写留待 Phase 2 的 Whisper。
- **动漫语体偏差**：动漫日语偏简体/粗俗，直接学会带偏口语。已用 `register_tag` + 礼貌等价说法（语体雷达 Phase 1 形态）缓解。

---

## 11. 已决决策（消除歧义）

- 单用户、单机、无登录。
- "当前主攻番"全局至多一部；可登记多部番，但今日训练只推进当前番。
- 注音由 SudachiPy 本地生成（不耗 LLM）；翻译/语法/语体由 Claude 生成。
- 候选生词默认**不**自动入 SRS，由用户在精读中决定，防牌组膨胀。
- 语法清单种子由实现方依据公开 N2/N1 语法大纲整理为 `grammar_seed.json`，约 150–250 条。
- 每日训练每天必含至少一个开口环节（精读阶段穿插短对话，整集完成后做完整对话）。
- 模型 ID 全部来自 `.env`，以适配 fox 网关实际可用值与日期后缀要求。
- 设计文档与代码注释用中文，与 trading 项目一致。

---

## 附录：术语

- **SRS**：Spaced Repetition System，间隔重复。
- **语体（register）**：日语依场合/对象/性别等的表达层级（礼貌体、简体、粗俗、男言葉/女言葉等）。
- **fox**：用户已有的 AI 网关，走 Anthropic 原生协议，经 `base_url` 接入。
- **通关**：一集完成精读且做完完整角色对话。
