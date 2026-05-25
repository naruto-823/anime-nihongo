# 追番日语 Phase 1 · Plan 3：前端页面 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1（后端引擎）+ Plan 2（HTTP API）之上，搭一套 React 前端，让用户能在浏览器里用上整个产品：今日训练、番剧库、精读、SRS 复习、语法清单、角色对话、进度面板。

**Architecture:** Vite + React 18 + TypeScript + Tailwind CSS + TanStack Query。React Router 做页面路由。所有数据来自 `/api/*`（dev 通过 Vite 代理转发到 `http://localhost:8000`；生产由后端静态托管 `frontend/dist/`）。麦克风识别与朗读用浏览器原生 Web Speech API（封装为 hooks，需要 Chrome / Edge）。测试用 Vitest + React Testing Library，每页一个冒烟测试。

**Tech Stack:** Node ≥ 20、Vite ≥ 5、React 18、TypeScript 5、Tailwind 3、TanStack Query 5、React Router 6、Vitest + @testing-library/react + jsdom + msw（mock fetch）。

参考规格：`docs/superpowers/specs/2026-05-22-anime-japanese-phase1-design.md`（§5.3–5.7、§6.3）。
前置：Plan 1、Plan 2 已合入 master，后端 API 可用且会自动静态托管 `frontend/dist/`。

---

## 文件结构

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.ts
  postcss.config.js
  index.html
  src/
    main.tsx            # 入口：QueryClient + Router
    App.tsx             # 路由表
    index.css           # Tailwind base
    components/
      Layout.tsx        # 顶栏导航 + <Outlet/>
      Furigana.tsx      # 渲染 {t,r} 段为 ruby
      Loading.tsx
    lib/
      api.ts            # 21 个端点的 typed fetcher
      speech.ts         # useSTT / useTTS hooks（Web Speech API 封装）
    pages/
      Today.tsx         # 今日训练
      Series.tsx        # 番剧库 + 导入
      Reading.tsx       # 精读
      Review.tsx        # SRS 复习
      Grammar.tsx       # 语法清单
      Conversation.tsx  # 角色对话
      Progress.tsx      # 进度
    types.ts            # API 响应类型
  tests/
    setup.ts            # vitest 全局：jsdom、msw 启动
    handlers.ts         # msw 默认处理器（每个测试可覆盖）
    pages.test.tsx      # 7 个页面的渲染冒烟测试
```

每个页面单一职责。`lib/api.ts` 是唯一的网络层。

---

## Task 1: 前端工程骨架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/.gitignore` 不需要（仓库根的 `.gitignore` 已含 `node_modules/`、`dist/`）
- Modify: `Makefile`（增加 `frontend` / `frontend-dev` / `frontend-build` 目标）

- [ ] **Step 1: 写工程文件**

`frontend/package.json`:

```json
{
  "name": "anime-nihongo-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "lint": "tsc -b --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "jsdom": "^25.0.0",
    "msw": "^2.3.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

`frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

`frontend/tailwind.config.ts`:

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

`frontend/postcss.config.js`:

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>追番日语</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

ruby rt { font-size: 0.6em; opacity: 0.7; }
```

`frontend/src/main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
```

`frontend/src/App.tsx` (minimal placeholder; Task 4 fills the routes):

```tsx
export default function App() {
  return <div className="p-8 text-2xl">追番日语 — frontend up</div>;
}
```

Modify `Makefile` —— append (keep existing targets intact):

```makefile
.PHONY: frontend frontend-dev frontend-build

frontend:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
```

- [ ] **Step 2: 安装依赖并冒烟构建**

Run from the repo root: `make frontend && cd frontend && npm run build`
Expected: `npm install` 完成；`vite build` 成功，输出 `frontend/dist/` 目录（包含 `index.html` + assets）。

- [ ] **Step 3: 提交**

```bash
git add frontend Makefile
git commit -m "chore: 前端工程骨架与依赖"
```

---

## Task 2: API 客户端 lib/api.ts

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/tests/handlers.ts`
- Test: `frontend/tests/api.test.ts`

- [ ] **Step 1: 写类型** — `frontend/src/types.ts`:

```ts
export type FuriganaSeg = { t: string; r?: string };

export type Series = {
  id: number; title: string; title_jp: string | null;
  jimaku_entry_id: number | null; is_current: boolean;
};

export type Episode = {
  id: number; series_id: number; number: number; title: string | null;
  status: "importing" | "processing" | "ready" | "failed";
  total_lines: number; processed_lines: number;
  read_position: number; reading_done: boolean;
};

export type Line = {
  id: number; idx: number; start_ms: number | null; end_ms: number | null;
  speaker: string | null; text_jp: string;
  furigana: FuriganaSeg[] | null; translation_zh: string | null;
  grammar_notes: { point: string; explain: string }[] | null;
  register_tag: string | null;
  grammar_point_keys: string[] | null;
  processed: boolean;
};

export type GrammarPoint = {
  id: number; key: string; name: string; jlpt_level: string;
  explanation: string; status: "locked" | "seen" | "learning";
  in_srs: boolean; mastered: boolean;
};

export type DueItems = {
  vocab: { id: number; headword: string; reading: string;
           meaning_zh: string; pos: string | null; context: string | null }[];
  grammar: { id: number; key: string; name: string; jlpt_level: string;
             explanation: string }[];
};

export type Today = {
  due: { vocab: number; grammar: number };
  current_episode: { id: number; number: number; title: string | null;
                     read_position: number; total_lines: number;
                     reading_done: boolean } | null;
  streak: number;
};

export type Progress = {
  streak: number;
  vocab: { total: number; in_srs: number };
  grammar: { total_curated: number; encountered: number; mastered: number };
  history: { date: string; completed: boolean;
             vocab_reviewed: number; grammar_reviewed: number;
             lines_read: number }[];
};

export type Grade = "again" | "hard" | "good" | "easy";

export type ConvTurn = { role: "user" | "assistant"; text: string };
```

- [ ] **Step 2: 写 API 客户端** — `frontend/src/lib/api.ts`:

```ts
import type {
  ConvTurn, DueItems, Episode, Grade, GrammarPoint, Line, Progress, Series, Today,
} from "../types";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!resp.ok) throw new Error(`${resp.status} ${path}: ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

// Series
export const listSeries = () => http<Series[]>("/api/series");
export const createSeries = (title: string, title_jp?: string) =>
  http<Series>("/api/series", { method: "POST", body: JSON.stringify({ title, title_jp }) });
export const setCurrentSeries = (id: number) =>
  http<Series>(`/api/series/${id}/set-current`, { method: "POST" });

// Episodes
export const importEpisodeFile = async (seriesId: number, number: number, file: File) => {
  const form = new FormData();
  form.append("series_id", String(seriesId));
  form.append("number", String(number));
  form.append("file", file);
  const resp = await fetch("/api/episodes/import-file", { method: "POST", body: form });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json() as Promise<Episode>;
};
export const getEpisode = (id: number) => http<Episode>(`/api/episodes/${id}`);
export const getLines = (id: number) => http<Line[]>(`/api/episodes/${id}/lines`);

// Study
export const getToday = () => http<Today>("/api/study/today");
export const addVocabToSrs = (id: number) =>
  http<{ id: number; in_srs: true }>(`/api/study/vocab/${id}/add-srs`, { method: "POST" });
export const addGrammarToSrs = (id: number) =>
  http<{ id: number; in_srs: true; status: string }>(
    `/api/study/grammar/${id}/add-srs`, { method: "POST" });
export const setReadingProgress = (episodeId: number, position: number) =>
  http<Episode>(`/api/study/episodes/${episodeId}/reading-progress`,
    { method: "POST", body: JSON.stringify({ position }) });
export const completeToday = (body: {
  episode_id?: number | null; vocab_reviewed?: number; grammar_reviewed?: number;
  lines_read?: number; conversation_turns?: number; summary?: Record<string, unknown>;
}) => http<{ streak: number }>("/api/study/complete-today",
  { method: "POST", body: JSON.stringify(body) });

// SRS
export const getDue = () => http<DueItems>("/api/srs/due");
export const submitReview = (item_type: "vocab" | "grammar", item_id: number, grade: Grade) =>
  http<{ id: number; interval_days: number; reps: number; due_date: string }>(
    "/api/srs/review",
    { method: "POST", body: JSON.stringify({ item_type, item_id, grade }) });

// Grammar
export const getChecklist = () => http<Record<string, GrammarPoint[]>>("/api/grammar/checklist");
export const getQuiz = (grammarId: number) =>
  http<{ question: string; options: string[]; answer: string; explain: string }>(
    `/api/grammar/${grammarId}/quiz`);

// Conversation
export const conversationTurn = (body: {
  episode_id: number; character?: string; history: ConvTurn[]; user_text: string;
}) => http<{ reply: string }>("/api/conversation/turn",
  { method: "POST", body: JSON.stringify(body) });
export const conversationFeedback = (body: { episode_id: number; history: ConvTurn[] }) =>
  http<{
    corrections: { original: string; fixed: string; explain: string }[];
    suggestions: string[];
    new_vocab: { headword: string; reading: string; meaning_zh: string }[];
    weak_grammar_keys: string[];
  }>("/api/conversation/feedback",
    { method: "POST", body: JSON.stringify(body) });

// Progress
export const getProgress = () => http<Progress>("/api/progress");
```

- [ ] **Step 3: 写测试基础设施** — `frontend/tests/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/series", () => HttpResponse.json([
    { id: 1, title: "测试番", title_jp: null, jimaku_entry_id: null, is_current: true },
  ])),
  http.get("/api/study/today", () => HttpResponse.json({
    due: { vocab: 3, grammar: 1 },
    current_episode: { id: 10, number: 1, title: null,
                       read_position: 0, total_lines: 2, reading_done: false },
    streak: 5,
  })),
  http.get("/api/srs/due", () => HttpResponse.json({
    vocab: [{ id: 1, headword: "猫", reading: "ねこ", meaning_zh: "猫",
              pos: "名詞", context: "猫が走る" }],
    grammar: [],
  })),
  http.get("/api/grammar/checklist", () => HttpResponse.json({
    N2: [{ id: 1, key: "ni-atatte", name: "〜にあたって", jlpt_level: "N2",
           explanation: "在…之际", status: "locked", in_srs: false, mastered: false }],
  })),
  http.get("/api/progress", () => HttpResponse.json({
    streak: 5,
    vocab: { total: 10, in_srs: 7 },
    grammar: { total_curated: 264, encountered: 12, mastered: 2 },
    history: [],
  })),
  http.get("/api/episodes/10", () => HttpResponse.json({
    id: 10, series_id: 1, number: 1, title: null, status: "ready",
    total_lines: 2, processed_lines: 2, read_position: 0, reading_done: false,
  })),
  http.get("/api/episodes/10/lines", () => HttpResponse.json([
    { id: 100, idx: 0, start_ms: 1000, end_ms: 4000, speaker: null,
      text_jp: "おはよう、元気？",
      furigana: [{ t: "おはよう、" }, { t: "元気", r: "げんき" }, { t: "？" }],
      translation_zh: "早上好，精神吗？",
      grammar_notes: [], register_tag: "casual", grammar_point_keys: [], processed: true },
  ])),
];
```

`frontend/tests/setup.ts`:

```ts
import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

`frontend/tests/api.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { getChecklist, getProgress, getToday, listSeries } from "../src/lib/api";

describe("api client", () => {
  it("listSeries", async () => {
    const xs = await listSeries();
    expect(xs[0].title).toBe("测试番");
  });
  it("getToday", async () => {
    const t = await getToday();
    expect(t.streak).toBe(5);
    expect(t.due.vocab).toBe(3);
  });
  it("getChecklist groups by level", async () => {
    const c = await getChecklist();
    expect(Object.keys(c)).toContain("N2");
  });
  it("getProgress", async () => {
    const p = await getProgress();
    expect(p.vocab.in_srs).toBe(7);
  });
});
```

- [ ] **Step 4: 跑测试**

Run: `cd frontend && npm test`
Expected: 4 tests PASS.

- [ ] **Step 5: 提交**

```bash
git add frontend/src frontend/tests
git commit -m "feat: 前端 API 客户端与测试基础设施"
```

---

## Task 3: Web Speech API 封装 lib/speech.ts

**Files:**
- Create: `frontend/src/lib/speech.ts`
- Test: `frontend/tests/speech.test.tsx`

- [ ] **Step 1: 写测试** — `frontend/tests/speech.test.tsx`:

```tsx
import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useSTT, useTTS } from "../src/lib/speech";

describe("speech hooks", () => {
  it("useSTT exposes supported/listening flags and control fns", () => {
    const { result } = renderHook(() => useSTT());
    // jsdom 没有 webkitSpeechRecognition，supported 应为 false 且不抛
    expect(typeof result.current.supported).toBe("boolean");
    expect(typeof result.current.listening).toBe("boolean");
    expect(typeof result.current.start).toBe("function");
    expect(typeof result.current.stop).toBe("function");
  });

  it("useTTS exposes supported and speak fn; speak with TTS off is a no-op", () => {
    const { result } = renderHook(() => useTTS());
    expect(typeof result.current.supported).toBe("boolean");
    expect(() => result.current.speak("こんにちは")).not.toThrow();
  });
});
```

- [ ] **Step 2: 写实现** — `frontend/src/lib/speech.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";

type SR = typeof window extends { webkitSpeechRecognition: infer T } ? T : unknown;

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => any;
    SpeechRecognition?: new () => any;
  }
}

function getSR() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function useSTT(lang = "ja-JP") {
  const [supported] = useState(() => getSR() !== null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const ref = useRef<any>(null);

  const start = useCallback(() => {
    const Cls = getSR();
    if (!Cls || listening) return;
    const rec = new Cls();
    rec.lang = lang;
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e: any) => {
      const t = e.results?.[0]?.[0]?.transcript ?? "";
      setTranscript(t);
    };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    ref.current = rec;
    setTranscript("");
    setListening(true);
    rec.start();
  }, [lang, listening]);

  const stop = useCallback(() => {
    ref.current?.stop?.();
    setListening(false);
  }, []);

  useEffect(() => () => stop(), [stop]);

  return { supported, listening, transcript, start, stop };
}

export function useTTS(lang = "ja-JP") {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const speak = useCallback((text: string) => {
    if (!supported || !text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }, [lang, supported]);
  return { supported, speak };
}
```

- [ ] **Step 3: 跑测试**

Run: `cd frontend && npm test -- speech`
Expected: 2 tests PASS.

- [ ] **Step 4: 提交**

```bash
git add frontend/src/lib/speech.ts frontend/tests/speech.test.tsx
git commit -m "feat: Web Speech API hooks 封装"
```

---

## Task 4: 路由与布局 App + Layout + Furigana

**Files:**
- Create: `frontend/src/components/Layout.tsx`
- Create: `frontend/src/components/Furigana.tsx`
- Create: `frontend/src/components/Loading.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 写 Layout** — `frontend/src/components/Layout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "今日训练", end: true },
  { to: "/series", label: "番剧" },
  { to: "/review", label: "复习" },
  { to: "/grammar", label: "语法清单" },
  { to: "/progress", label: "进度" },
];

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <nav className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-6">
          <span className="font-semibold">追番日语</span>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `text-sm hover:text-indigo-600 ${
                  isActive ? "text-indigo-600 font-medium" : "text-slate-600"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
```

`frontend/src/components/Furigana.tsx`:

```tsx
import type { FuriganaSeg } from "../types";

export default function Furigana({ segs, showRuby = true }:
  { segs: FuriganaSeg[] | null; showRuby?: boolean }) {
  if (!segs) return null;
  return (
    <span>
      {segs.map((s, i) =>
        s.r && showRuby ? (
          <ruby key={i}>{s.t}<rt>{s.r}</rt></ruby>
        ) : (
          <span key={i}>{s.t}</span>
        ),
      )}
    </span>
  );
}
```

`frontend/src/components/Loading.tsx`:

```tsx
export default function Loading() {
  return <div className="text-slate-500 py-8 text-center">加载中…</div>;
}
```

- [ ] **Step 2: 改 App** — `frontend/src/App.tsx`:

```tsx
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Conversation from "./pages/Conversation";
import Grammar from "./pages/Grammar";
import Progress from "./pages/Progress";
import Reading from "./pages/Reading";
import Review from "./pages/Review";
import Series from "./pages/Series";
import Today from "./pages/Today";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Today />} />
        <Route path="series" element={<Series />} />
        <Route path="episodes/:id/reading" element={<Reading />} />
        <Route path="episodes/:id/conversation" element={<Conversation />} />
        <Route path="review" element={<Review />} />
        <Route path="grammar" element={<Grammar />} />
        <Route path="progress" element={<Progress />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 3: 占位页面** —— 暂时给每个页面写一个最简占位（后续任务逐个替换为真正实现），以便整个路由可以编译/渲染：

`frontend/src/pages/Today.tsx`, `Series.tsx`, `Reading.tsx`, `Review.tsx`, `Grammar.tsx`, `Conversation.tsx`, `Progress.tsx`：每个文件内容相同的占位（按各自文件名替换标题）：

```tsx
export default function PAGENAME() {
  return <div>PAGENAME（待实现）</div>;
}
```

例如 `Today.tsx`:

```tsx
export default function Today() {
  return <div>今日训练（待实现）</div>;
}
```

类似地写另 6 个文件，函数名分别为 `Series` / `Reading` / `Review` / `Grammar` / `Conversation` / `Progress`，标题分别为 中文标签。

- [ ] **Step 4: 跑构建确认无类型/编译错误**

Run: `cd frontend && npm run lint && npm run build`
Expected: 全部通过；`frontend/dist/` 重新生成。

- [ ] **Step 5: 提交**

```bash
git add frontend/src
git commit -m "feat: 前端路由、布局与 Furigana 组件"
```

---

## Task 5: 今日训练页 Today.tsx

**Files:**
- Modify: `frontend/src/pages/Today.tsx`
- Test: `frontend/tests/today.test.tsx`

- [ ] **Step 1: 写测试** — `frontend/tests/today.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrowserRouter } from "react-router-dom";

import Today from "../src/pages/Today";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>{node}</BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("Today page", () => {
  it("renders streak, due counts and current episode", async () => {
    wrap(<Today />);
    await waitFor(() => expect(screen.getByText(/连续/)).toBeInTheDocument());
    expect(screen.getByText(/5/)).toBeInTheDocument(); // streak
    expect(screen.getByText(/词汇/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument(); // due vocab
    expect(screen.getByText(/第 1 集/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 实现** — `frontend/src/pages/Today.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Loading from "../components/Loading";
import { completeToday, getToday } from "../lib/api";

export default function Today() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["today"], queryFn: getToday });
  const complete = useMutation({
    mutationFn: () => completeToday({ episode_id: data?.current_episode?.id ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["today"] }),
  });

  if (isLoading || !data) return <Loading />;
  const ep = data.current_episode;

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">今日训练</h1>
        <div className="text-sm text-slate-600">
          连续打卡 <span className="font-semibold text-indigo-600">{data.streak}</span> 天
        </div>
      </header>

      <section className="grid grid-cols-2 gap-4">
        <Card title="到期复习">
          <div>词汇 <b>{data.due.vocab}</b></div>
          <div>语法 <b>{data.due.grammar}</b></div>
          <Link to="/review" className="text-indigo-600 text-sm">去复习 →</Link>
        </Card>
        <Card title="当前剧集">
          {ep ? (
            <>
              <div>第 {ep.number} 集 · {ep.read_position}/{ep.total_lines} 行
                {ep.reading_done && " · 精读已完成"}</div>
              <div className="flex gap-3 mt-2">
                <Link to={`/episodes/${ep.id}/reading`}
                      className="text-indigo-600 text-sm">精读 →</Link>
                <Link to={`/episodes/${ep.id}/conversation`}
                      className="text-indigo-600 text-sm">角色对话 →</Link>
              </div>
            </>
          ) : (
            <div>
              还没有当前番。<Link to="/series" className="text-indigo-600">先去导入一集 →</Link>
            </div>
          )}
        </Card>
      </section>

      <button
        onClick={() => complete.mutate()}
        className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
        disabled={complete.isPending}
      >
        {complete.isPending ? "保存中…" : "完成今日训练（打卡）"}
      </button>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded border p-4 space-y-1">
      <div className="text-sm text-slate-500">{title}</div>
      {children}
    </div>
  );
}
```

- [ ] **Step 3: 跑测试**

Run: `cd frontend && npm test -- today && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Today.tsx frontend/tests/today.test.tsx
git commit -m "feat: 今日训练页"
```

---

## Task 6: 番剧库与导入 Series.tsx

**Files:**
- Modify: `frontend/src/pages/Series.tsx`
- Test: `frontend/tests/series.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Series.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import { createSeries, importEpisodeFile, listSeries, setCurrentSeries } from "../lib/api";

export default function Series() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["series"], queryFn: listSeries });
  const [title, setTitle] = useState("");
  const create = useMutation({
    mutationFn: () => createSeries(title),
    onSuccess: () => { setTitle(""); qc.invalidateQueries({ queryKey: ["series"] }); },
  });
  const setCurrent = useMutation({
    mutationFn: (id: number) => setCurrentSeries(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["series"] }),
  });

  if (isLoading || !data) return <Loading />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">番剧库</h1>

      <section className="bg-white rounded border p-4 space-y-2">
        <div className="text-sm text-slate-500">新增番剧</div>
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="番剧名"
            className="border rounded px-3 py-1 flex-1"
          />
          <button
            onClick={() => title && create.mutate()}
            className="px-3 py-1 bg-indigo-600 text-white rounded disabled:opacity-50"
            disabled={!title || create.isPending}
          >新增</button>
        </div>
      </section>

      <section className="space-y-3">
        {data.length === 0 && <div className="text-slate-500">还没有番剧。先新增一部吧。</div>}
        {data.map((s) => (
          <div key={s.id} className="bg-white rounded border p-4">
            <div className="flex items-center justify-between">
              <div className="font-medium">
                {s.title}
                {s.is_current && <span className="ml-2 text-xs text-indigo-600">当前</span>}
              </div>
              {!s.is_current && (
                <button
                  onClick={() => setCurrent.mutate(s.id)}
                  className="text-xs text-indigo-600 hover:underline"
                >设为当前</button>
              )}
            </div>
            <ImportEpisode seriesId={s.id} />
          </div>
        ))}
      </section>
    </div>
  );
}

function ImportEpisode({ seriesId }: { seriesId: number }) {
  const qc = useQueryClient();
  const [number, setNumber] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const imp = useMutation({
    mutationFn: () => importEpisodeFile(seriesId, number, file!),
    onSuccess: () => {
      setFile(null); setError(null);
      qc.invalidateQueries({ queryKey: ["today"] });
    },
    onError: (e: Error) => setError(e.message),
  });
  return (
    <div className="mt-3 text-sm space-y-1">
      <div className="text-slate-500">导入字幕（.srt / .ass）</div>
      <div className="flex items-center gap-2">
        <input
          type="number" min={1} value={number}
          onChange={(e) => setNumber(Number(e.target.value))}
          className="border rounded px-2 py-1 w-20"
        />
        <input
          type="file" accept=".srt,.ass"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-xs"
        />
        <button
          onClick={() => file && imp.mutate()}
          className="px-3 py-1 bg-slate-200 rounded disabled:opacity-50"
          disabled={!file || imp.isPending}
        >{imp.isPending ? "处理中…" : "导入并加工"}</button>
      </div>
      {error && <div className="text-red-600">{error}</div>}
      {imp.isSuccess && (
        <div className="text-green-700">第 {number} 集已加工完成。</div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/series.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrowserRouter } from "react-router-dom";

import Series from "../src/pages/Series";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>
    <BrowserRouter>{node}</BrowserRouter>
  </QueryClientProvider>);
}

describe("Series page", () => {
  it("lists series from mocked API", async () => {
    wrap(<Series />);
    await waitFor(() => expect(screen.getByText("测试番")).toBeInTheDocument());
    expect(screen.getByText("当前")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- series && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Series.tsx frontend/tests/series.test.tsx
git commit -m "feat: 番剧库与导入页"
```

---

## Task 7: 精读页 Reading.tsx

**Files:**
- Modify: `frontend/src/pages/Reading.tsx`
- Test: `frontend/tests/reading.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Reading.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import Furigana from "../components/Furigana";
import Loading from "../components/Loading";
import { getEpisode, getLines, setReadingProgress } from "../lib/api";

export default function Reading() {
  const { id } = useParams();
  const epId = Number(id);
  const qc = useQueryClient();
  const { data: ep } = useQuery({ queryKey: ["episode", epId], queryFn: () => getEpisode(epId) });
  const { data: lines } = useQuery({ queryKey: ["lines", epId], queryFn: () => getLines(epId) });
  const [showRuby, setShowRuby] = useState(true);
  const [showZh, setShowZh] = useState<Record<number, boolean>>({});

  const advance = useMutation({
    mutationFn: (position: number) => setReadingProgress(epId, position),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["episode", epId] }),
  });

  if (!ep || !lines) return <Loading />;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          精读 · 第 {ep.number} 集（{ep.read_position}/{ep.total_lines}）
        </h1>
        <label className="text-sm flex items-center gap-2">
          <input type="checkbox" checked={showRuby}
                 onChange={(e) => setShowRuby(e.target.checked)} />
          显示假名注音
        </label>
      </header>

      <ul className="space-y-2">
        {lines.map((ln) => (
          <li key={ln.id} className="bg-white border rounded p-3">
            <div className="text-lg leading-relaxed">
              {ln.speaker && (
                <span className="text-slate-500 text-sm mr-2">{ln.speaker}：</span>
              )}
              <Furigana segs={ln.furigana} showRuby={showRuby} />
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
              <button
                className="hover:text-indigo-600"
                onClick={() => setShowZh((m) => ({ ...m, [ln.id]: !m[ln.id] }))}
              >{showZh[ln.id] ? "收起译文" : "看译文"}</button>
              {ln.register_tag && (
                <span className="px-2 py-0.5 bg-slate-100 rounded">{ln.register_tag}</span>
              )}
              {ln.grammar_point_keys && ln.grammar_point_keys.length > 0 && (
                <span>语法: {ln.grammar_point_keys.join(", ")}</span>
              )}
            </div>
            {showZh[ln.id] && (
              <div className="mt-2 text-sm text-slate-700">{ln.translation_zh}</div>
            )}
            {showZh[ln.id] && ln.grammar_notes && ln.grammar_notes.length > 0 && (
              <ul className="mt-1 text-xs text-slate-600 list-disc list-inside">
                {ln.grammar_notes.map((g, i) => (
                  <li key={i}><b>{g.point}</b>：{g.explain}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <div className="flex gap-3">
        <button
          onClick={() => advance.mutate(Math.min(ep.total_lines, ep.read_position + 15))}
          className="px-3 py-2 bg-indigo-600 text-white rounded disabled:opacity-50"
          disabled={advance.isPending || ep.reading_done}
        >推进 15 行</button>
        <button
          onClick={() => advance.mutate(ep.total_lines)}
          className="px-3 py-2 bg-slate-200 rounded disabled:opacity-50"
          disabled={advance.isPending || ep.reading_done}
        >标记本集精读完成</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/reading.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Reading from "../src/pages/Reading";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/episodes/10/reading"]}>
        <Routes>
          <Route path="/episodes/:id/reading" element={<Reading />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Reading page", () => {
  it("renders lines with speaker/translation toggles", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText(/精读/)).toBeInTheDocument());
    expect(screen.getByText(/おはよう/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- reading && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Reading.tsx frontend/tests/reading.test.tsx
git commit -m "feat: 精读页"
```

---

## Task 8: SRS 复习页 Review.tsx

**Files:**
- Modify: `frontend/src/pages/Review.tsx`
- Test: `frontend/tests/review.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Review.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import Loading from "../components/Loading";
import { getDue, submitReview } from "../lib/api";
import type { Grade } from "../types";

const GRADE_LABELS: { grade: Grade; label: string; cls: string }[] = [
  { grade: "again", label: "又错了", cls: "bg-red-600" },
  { grade: "hard",  label: "有点难", cls: "bg-amber-500" },
  { grade: "good",  label: "会了",   cls: "bg-emerald-600" },
  { grade: "easy",  label: "很简单", cls: "bg-indigo-600" },
];

export default function Review() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["due"], queryFn: getDue });
  const [show, setShow] = useState(false);

  const submit = useMutation({
    mutationFn: ({ kind, id, grade }: { kind: "vocab" | "grammar"; id: number; grade: Grade }) =>
      submitReview(kind, id, grade),
    onSuccess: () => {
      setShow(false);
      qc.invalidateQueries({ queryKey: ["due"] });
      qc.invalidateQueries({ queryKey: ["today"] });
    },
  });

  if (isLoading || !data) return <Loading />;

  const current =
    data.vocab[0]
      ? { kind: "vocab" as const, item: data.vocab[0] }
      : data.grammar[0]
        ? { kind: "grammar" as const, item: data.grammar[0] }
        : null;

  if (!current) {
    return <div className="text-slate-600">今天没有到期复习。继续推进当前集吧。</div>;
  }

  const remaining = data.vocab.length + data.grammar.length;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">复习 · 还有 {remaining} 项</h1>
      <div className="bg-white border rounded p-6">
        {current.kind === "vocab" ? (
          <VocabCard item={current.item} show={show} />
        ) : (
          <GrammarCard item={current.item} show={show} />
        )}
      </div>
      {!show ? (
        <button onClick={() => setShow(true)}
                className="px-4 py-2 bg-slate-800 text-white rounded">
          显示答案
        </button>
      ) : (
        <div className="flex flex-wrap gap-2">
          {GRADE_LABELS.map(({ grade, label, cls }) => (
            <button
              key={grade}
              onClick={() => submit.mutate({ kind: current.kind, id: current.item.id, grade })}
              className={`${cls} text-white px-3 py-2 rounded text-sm disabled:opacity-50`}
              disabled={submit.isPending}
            >{label}</button>
          ))}
        </div>
      )}
    </div>
  );
}

function VocabCard({ item, show }:
  { item: { headword: string; reading: string; meaning_zh: string;
            pos: string | null; context: string | null }; show: boolean }) {
  return (
    <div className="space-y-2">
      <div className="text-3xl">{item.headword}</div>
      {show && (
        <>
          <div className="text-lg">{item.reading}</div>
          <div className="text-slate-700">
            {item.pos && <span className="text-xs mr-2 px-1.5 py-0.5 bg-slate-100 rounded">{item.pos}</span>}
            {item.meaning_zh}
          </div>
          {item.context && <div className="text-slate-500 text-sm">语境：{item.context}</div>}
        </>
      )}
    </div>
  );
}

function GrammarCard({ item, show }:
  { item: { name: string; jlpt_level: string; explanation: string }; show: boolean }) {
  return (
    <div className="space-y-2">
      <div className="text-2xl">{item.name}</div>
      <div className="text-xs text-slate-500">{item.jlpt_level}</div>
      {show && <div className="text-slate-700">{item.explanation}</div>}
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/review.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Review from "../src/pages/Review";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Review page", () => {
  it("shows the current vocab card", async () => {
    wrap(<Review />);
    await waitFor(() => expect(screen.getByText("猫")).toBeInTheDocument());
    expect(screen.getByText(/还有 1 项/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- review && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Review.tsx frontend/tests/review.test.tsx
git commit -m "feat: SRS 复习页"
```

---

## Task 9: 语法清单页 Grammar.tsx

**Files:**
- Modify: `frontend/src/pages/Grammar.tsx`
- Test: `frontend/tests/grammar.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Grammar.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getChecklist } from "../lib/api";

const STATUS_COLOR: Record<string, string> = {
  locked: "bg-slate-100 text-slate-500",
  seen: "bg-amber-100 text-amber-700",
  learning: "bg-indigo-100 text-indigo-700",
};

export default function Grammar() {
  const { data, isLoading } = useQuery({
    queryKey: ["grammar-checklist"], queryFn: getChecklist,
  });
  if (isLoading || !data) return <Loading />;

  const levels = Object.keys(data).sort();
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold">语法清单</h1>
      {levels.map((lv) => {
        const pts = data[lv];
        const mastered = pts.filter((p) => p.mastered).length;
        return (
          <section key={lv} className="space-y-2">
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-medium">{lv}</h2>
              <div className="text-sm text-slate-500">
                掌握 {mastered} / {pts.length}
              </div>
            </div>
            <ul className="grid grid-cols-2 gap-2">
              {pts.map((p) => (
                <li key={p.id}
                    className={`p-2 rounded text-sm flex items-center justify-between
                                ${p.mastered ? "bg-emerald-100 text-emerald-800"
                                              : STATUS_COLOR[p.status] ?? ""}`}>
                  <span>{p.name}</span>
                  <span className="text-xs">
                    {p.mastered ? "已掌握" : p.status === "learning" ? "学习中"
                      : p.status === "seen" ? "已遇到" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/grammar.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Grammar from "../src/pages/Grammar";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Grammar page", () => {
  it("renders the N2 group and points", async () => {
    wrap(<Grammar />);
    await waitFor(() => expect(screen.getByText("N2")).toBeInTheDocument());
    expect(screen.getByText("〜にあたって")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- grammar && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Grammar.tsx frontend/tests/grammar.test.tsx
git commit -m "feat: 语法清单页"
```

---

## Task 10: 角色对话页 Conversation.tsx

**Files:**
- Modify: `frontend/src/pages/Conversation.tsx`
- Test: `frontend/tests/conversation.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Conversation.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import Loading from "../components/Loading";
import { conversationFeedback, conversationTurn, getEpisode } from "../lib/api";
import { useSTT, useTTS } from "../lib/speech";
import type { ConvTurn } from "../types";

export default function Conversation() {
  const { id } = useParams();
  const epId = Number(id);
  const { data: ep } = useQuery({ queryKey: ["episode", epId], queryFn: () => getEpisode(epId) });
  const stt = useSTT();
  const tts = useTTS();
  const [history, setHistory] = useState<ConvTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [character, setCharacter] = useState("登場人物");

  useEffect(() => {
    if (stt.transcript) setDraft(stt.transcript);
  }, [stt.transcript]);

  const turn = useMutation({
    mutationFn: () => conversationTurn({
      episode_id: epId, character, history, user_text: draft,
    }),
    onSuccess: (r) => {
      const next: ConvTurn[] = [
        ...history,
        { role: "user", text: draft },
        { role: "assistant", text: r.reply },
      ];
      setHistory(next);
      setDraft("");
      if (tts.supported) tts.speak(r.reply);
    },
  });

  const feedback = useMutation({
    mutationFn: () => conversationFeedback({ episode_id: epId, history }),
  });

  if (!ep) return <Loading />;

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">角色对话 · 第 {ep.number} 集</h1>
        <input value={character} onChange={(e) => setCharacter(e.target.value)}
               placeholder="角色名" className="border rounded px-2 py-1 text-sm w-40" />
      </header>

      {!stt.supported && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm p-2 rounded">
          当前浏览器不支持语音识别（请用 Chrome / Edge）。可改为打字。
        </div>
      )}

      <div className="space-y-2 bg-white border rounded p-3 max-h-96 overflow-auto">
        {history.length === 0 && (
          <div className="text-slate-500 text-sm">用日语和角色聊聊这一集吧。</div>
        )}
        {history.map((t, i) => (
          <div key={i} className={t.role === "user" ? "text-right" : ""}>
            <span className={`inline-block px-3 py-2 rounded ${
              t.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-100"
            }`}>{t.text}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        {stt.supported && (
          <button
            onClick={() => (stt.listening ? stt.stop() : stt.start())}
            className={`px-3 py-2 rounded text-sm ${
              stt.listening ? "bg-red-600 text-white" : "bg-slate-200"
            }`}
          >{stt.listening ? "■ 停止" : "🎙 说话"}</button>
        )}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="说点什么…（按 Enter 提交）"
          className="border rounded px-3 py-2 flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft && !turn.isPending) turn.mutate();
          }}
        />
        <button
          onClick={() => turn.mutate()}
          disabled={!draft || turn.isPending}
          className="px-3 py-2 bg-indigo-600 text-white rounded disabled:opacity-50"
        >发送</button>
      </div>

      {history.length > 0 && (
        <div className="pt-2">
          <button
            onClick={() => feedback.mutate()}
            className="px-3 py-2 bg-slate-800 text-white rounded text-sm"
            disabled={feedback.isPending}
          >{feedback.isPending ? "AI 复盘中…" : "结束对话 · 让 AI 复盘"}</button>
        </div>
      )}

      {feedback.data && (
        <section className="space-y-2 bg-white border rounded p-4">
          <h3 className="font-medium">复盘</h3>
          {feedback.data.corrections.length > 0 && (
            <ul className="text-sm space-y-1">
              {feedback.data.corrections.map((c, i) => (
                <li key={i}>
                  <span className="line-through text-slate-400">{c.original}</span>
                  {" → "}<span className="text-indigo-700 font-medium">{c.fixed}</span>
                  <span className="text-slate-500 ml-2">{c.explain}</span>
                </li>
              ))}
            </ul>
          )}
          {feedback.data.suggestions.length > 0 && (
            <div className="text-sm text-slate-700">
              💡 {feedback.data.suggestions.join("；")}
            </div>
          )}
          {feedback.data.new_vocab.length > 0 && (
            <div className="text-xs text-slate-500">
              新词已加入复习：{feedback.data.new_vocab.map((v) => v.headword).join("、")}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/conversation.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Conversation from "../src/pages/Conversation";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/episodes/10/conversation"]}>
        <Routes>
          <Route path="/episodes/:id/conversation" element={<Conversation />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Conversation page", () => {
  it("renders header for episode and the typing input", async () => {
    wrap();
    await waitFor(() => expect(screen.getByText(/第 1 集/)).toBeInTheDocument());
    expect(screen.getByPlaceholderText(/说点什么/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- conversation && npm run lint`
Expected: PASS（jsdom 无 webkitSpeechRecognition，会显示"当前浏览器不支持语音识别"提示，符合预期）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Conversation.tsx frontend/tests/conversation.test.tsx
git commit -m "feat: 角色对话页（含 Web Speech API）"
```

---

## Task 11: 进度页 Progress.tsx

**Files:**
- Modify: `frontend/src/pages/Progress.tsx`
- Test: `frontend/tests/progress.test.tsx`

- [ ] **Step 1: 写实现** — `frontend/src/pages/Progress.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";

import Loading from "../components/Loading";
import { getProgress } from "../lib/api";

export default function Progress() {
  const { data, isLoading } = useQuery({ queryKey: ["progress"], queryFn: getProgress });
  if (isLoading || !data) return <Loading />;

  const grammarPct = data.grammar.total_curated
    ? Math.round(100 * data.grammar.mastered / data.grammar.total_curated)
    : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">进度</h1>

      <section className="grid grid-cols-3 gap-4">
        <Stat label="连续打卡">{data.streak} 天</Stat>
        <Stat label="复习中的词汇">{data.vocab.in_srs} / {data.vocab.total}</Stat>
        <Stat label="语法掌握度">
          {data.grammar.mastered} / {data.grammar.total_curated}
          <span className="text-sm text-slate-500 ml-1">（{grammarPct}%）</span>
        </Stat>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">训练历史</h2>
        {data.history.length === 0 ? (
          <div className="text-slate-500">还没有训练记录。</div>
        ) : (
          <table className="w-full text-sm bg-white border rounded">
            <thead className="text-slate-500 text-xs">
              <tr>
                <th className="text-left p-2">日期</th>
                <th className="text-right p-2">复习词汇</th>
                <th className="text-right p-2">复习语法</th>
                <th className="text-right p-2">精读行数</th>
              </tr>
            </thead>
            <tbody>
              {data.history.map((h) => (
                <tr key={h.date} className="border-t">
                  <td className="p-2">{h.date}{h.completed && " ✓"}</td>
                  <td className="p-2 text-right">{h.vocab_reviewed}</td>
                  <td className="p-2 text-right">{h.grammar_reviewed}</td>
                  <td className="p-2 text-right">{h.lines_read}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: 写测试** — `frontend/tests/progress.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Progress from "../src/pages/Progress";

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

describe("Progress page", () => {
  it("renders the three stat cards", async () => {
    wrap(<Progress />);
    await waitFor(() => expect(screen.getByText("5 天")).toBeInTheDocument());
    expect(screen.getByText(/7 \/ 10/)).toBeInTheDocument();
    expect(screen.getByText(/2 \/ 264/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + lint**

Run: `cd frontend && npm test -- progress && npm run lint`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Progress.tsx frontend/tests/progress.test.tsx
git commit -m "feat: 进度页"
```

---

## Task 12: 全量构建 + 后端静态托管联调

**Files:**
- Modify: `Makefile`（增加一个一键启动目标）
- Test: `frontend/tests/build.smoke.test.ts`（可选；最小化即可）

- [ ] **Step 1: 跑全量前端测试 + 构建**

Run: `cd frontend && npm test && npm run build`
Expected: 所有页面冒烟测试通过；`frontend/dist/` 含 `index.html` 与 hashed bundle。

- [ ] **Step 2: 改 Makefile**

在 `Makefile` 追加：

```makefile
.PHONY: serve

# 全量启动：前端先 build，由后端静态托管
serve: frontend-build
	cd backend && .venv/bin/uvicorn app.main:app --port 8000
```

- [ ] **Step 3: 人工联调（不在自动测试范围）**

文档化操作步骤（更新 `README.md`）：

```markdown
## 启动

1. `cp .env.example .env` 并填入 fox / Jimaku 凭证
2. `make setup && make frontend`
3. `make serve`
4. 用 **Chrome 或 Edge** 打开 `http://localhost:8000`

开发模式（前后端分跑、热更）：
- 终端 A：`make dev`（后端 8000）
- 终端 B：`make frontend-dev`（前端 5173，已配置 `/api` 代理到 8000）
```

- [ ] **Step 4: 提交**

```bash
git add Makefile README.md
git commit -m "chore: 全量启动入口与说明"
```

---

## 验收标准

- `cd frontend && npm test` 全绿（每个页面至少一个冒烟测试）；`npm run lint` 与 `npm run build` 干净。
- `make serve` 起后端，浏览器打开 `http://localhost:8000` 看到导航和「今日训练」页面，所有页面可点开。
- 真实手动走通：在「番剧」页新增一部番、上传字幕 → 后端加工完成 → 「今日训练」显示当前剧集 → 「精读」逐行可读、按提示加复习 → 「复习」可走 SM-2 评分 → 「语法清单」点亮命中的语法点 → 「角色对话」按麦克风可说话（Chrome / Edge）→ 「进度」显示连续打卡。

## 交付物

一个可在浏览器里完整使用的「追番日语」Phase 1 应用。后端静态托管 `frontend/dist/`，一条 `make serve` 起整套服务。

## 后续（不在本计划范围）

- shadcn/ui 组件库集成（视觉打磨）。
- 番剧导入的 Jimaku 搜索 UI（API 已有 `GET /api/series/search-jimaku`，前端目前只有上传路径）。
- 加工进度的轮询/流式提示（当前同步等待）。
- Phase 2 / Phase 3 的功能（听写、配音、复述、Whisper 兜底等）。
