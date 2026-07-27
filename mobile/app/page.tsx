"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = "https://api.narutoooo.com";

type Stage = { stage_idx: number; is_boss: boolean; unlocked: boolean; cleared: boolean; stars: number };
type Zone = { zone_idx: number; stages: Stage[] };
type Level = { level: string; unlocked: boolean; zones: Zone[] };
type TowerMap = { levels: Level[] };
type Question = { id: string; prompt: string; hint: string | null; options: string[]; answer: string; item: { kind: string; id: number } };
type Player = { total_xp: number; player_level: number };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem("nihongo-token");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "网络请求失败");
  }
  return response.json() as Promise<T>;
}

function stageName(stage: Stage) {
  if (stage.is_boss) return ["赤鬼守门人", "赤鬼の門番"];
  const names = [["入门试炼", "はじめの一歩"], ["五十音之森", "かなの森"], ["词汇道场", "言葉の道場"], ["助词迷阵", "助詞の迷路"], ["动词山道", "動詞の山道"]];
  return names[stage.stage_idx] ?? [`第 ${stage.stage_idx + 1} 关`, "日本語の修行"];
}

export default function Home() {
  const [tower, setTower] = useState<TowerMap | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [activeLevel, setActiveLevel] = useState(0);
  const [selected, setSelected] = useState<{ stage: Stage; zone: number } | null>(null);
  const [challenge, setChallenge] = useState<{ stage: Stage; zone: number } | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [quiz, setQuiz] = useState(false);
  const [question, setQuestion] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [answers, setAnswers] = useState<{ item: Question["item"]; correct: boolean }[]>([]);
  const [result, setResult] = useState<{ stars: number; accuracy: number; xp_gained: number; passed: boolean } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState("");

  async function loadGame() {
    setLoading(true); setError("");
    try {
      const [map, stats] = await Promise.all([api<TowerMap>("/api/tower"), api<Player>("/api/player")]);
      setTower(map); setPlayer(stats);
    } catch (e) { setError(e instanceof Error ? e.message : "加载失败"); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const saved = localStorage.getItem("nihongo-user") ?? "";
      setUser(saved);
      if (!saved) setLoading(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);
  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void loadGame(), 0);
    return () => window.clearTimeout(timer);
  }, [user]);

  async function authenticate() {
    setError("");
    try {
      const data = await api<{ token: string; user: { username: string } }>(`/api/auth/${authMode}`, {
        method: "POST", body: JSON.stringify({ username, password }),
      });
      localStorage.setItem("nihongo-token", data.token);
      localStorage.setItem("nihongo-user", data.user.username);
      setUser(data.user.username);
    } catch (e) { setError(e instanceof Error ? e.message : "登录失败"); }
  }

  function logout() {
    localStorage.removeItem("nihongo-token"); localStorage.removeItem("nihongo-user");
    setUser(""); setTower(null); setPlayer(null);
  }

  const level = tower?.levels[activeLevel];
  const xpProgress = useMemo(() => player ? Math.min(100, (player.total_xp % 500) / 5) : 0, [player]);

  async function beginQuiz() {
    if (!selected || !level) return;
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ level: level.level, zone: String(selected.zone), stage: String(selected.stage.stage_idx), boss: selected.stage.is_boss ? "1" : "0" });
      const data = await api<{ questions: Question[] }>(`/api/tower/quiz?${params}`);
      setChallenge(selected); setQuestions(data.questions); setQuestion(0); setPicked(null); setAnswers([]); setResult(null); setSelected(null); setQuiz(true);
    } catch (e) { setError(e instanceof Error ? e.message : "题目加载失败"); }
    finally { setLoading(false); }
  }

  function choose(option: string) {
    if (picked || !questions[question]) return;
    setPicked(option);
    const q = questions[question];
    const next = [...answers, { item: q.item, correct: option === q.answer }];
    setAnswers(next);
    window.setTimeout(async () => {
      if (question < questions.length - 1) { setQuestion((value) => value + 1); setPicked(null); return; }
      try {
        const response = await api<{ stars: number; accuracy: number; xp_gained: number; passed: boolean }>("/api/tower/submit", {
          method: "POST", body: JSON.stringify({ level: level?.level, zone: challenge?.zone ?? 0, stage: challenge?.stage.stage_idx ?? 0, boss: challenge?.stage.is_boss ?? false, results: next }),
        });
        setResult(response); await loadGame();
      } catch (e) { setError(e instanceof Error ? e.message : "成绩提交失败"); }
    }, 650);
  }

  if (!user) return <main className="auth-screen"><section className="auth-card"><div className="auth-mark">忍</div><p>追番日语</p><h1>修炼塔</h1><span>登录后在手机和电脑同步修炼进度</span><label>用户名<input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" placeholder="3–32 个字母或数字" /></label><label>密码<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} placeholder="至少 6 位" /></label>{error && <div className="auth-error">{error}</div>}<button className="primary" onClick={authenticate}>{authMode === "login" ? "登录并继续" : "创建账号"}</button><button className="auth-switch" onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setError(""); }}>{authMode === "login" ? "第一次来？创建账号" : "已有账号？返回登录"}</button></section></main>;
  if (loading && !tower) return <main className="auth-screen"><div className="loader">修炼塔开启中…</div></main>;

  return <main className="app-shell">
    <header className="hero"><div className="topline"><span className="eyebrow">追番日语</span><button className="user-pill" onClick={logout}>{user} · 退出</button></div><div className="hero-copy"><div><p>修炼塔 · {level?.level ?? "N5"}</p><h1>忍者之路</h1></div><div className="streak"><b>{player?.player_level ?? 1}</b><span>忍者等级</span></div></div><div className="xp-row"><span>Lv. {player?.player_level ?? 1}</span><span>{player?.total_xp ?? 0} XP</span></div><div className="xp-track"><i style={{ width: `${xpProgress}%` }} /></div></header>
    {error && <div className="global-error">{error}<button onClick={() => setError("")}>×</button></div>}
    <section className="level-tabs">{tower?.levels.map((item, index) => <button key={item.level} disabled={!item.unlocked} className={index === activeLevel ? "active" : ""} onClick={() => setActiveLevel(index)}>{item.unlocked ? item.level : `🔒 ${item.level}`}</button>)}</section>
    <section className="map" aria-label="修炼塔关卡地图">
      <div className="chapter"><span>壹</span><div><b>{level?.level ?? "N5"} · 基础修炼</b><small>每关题目来自独立词汇与语法题库</small></div></div><div className="path" />
      {level?.zones.flatMap((zone) => zone.stages.map((stage, index) => {
        const [name, jp] = stageName(stage); const current = stage.unlocked && !stage.cleared; const row = zone.zone_idx * 6 + index;
        return <article className={`stage-row ${row % 2 ? "right" : "left"}`} key={`${zone.zone_idx}-${stage.stage_idx}-${stage.is_boss}`}><button className={`stage-node ${stage.cleared ? "done" : ""} ${current ? "current" : ""} ${!stage.unlocked ? "locked" : ""} ${stage.is_boss ? "boss" : ""}`} onClick={() => stage.unlocked && setSelected({ stage, zone: zone.zone_idx })}><span>{stage.is_boss ? "鬼" : stage.cleared ? "✓" : !stage.unlocked ? "鎖" : stage.stage_idx + 1}</span></button><div className="stage-copy"><b>{name}</b><small>{jp}</small>{stage.cleared && <div className="stars">{"★".repeat(stage.stars)}{"☆".repeat(3 - stage.stars)}</div>}{current && <i>可挑战</i>}</div></article>;
      }))}
    </section>
    <nav className="bottom-nav"><button className="active"><span>塔</span>修炼</button><button><span>巻</span>词卷</button><button><span>火</span>复习</button><button><span>人</span>我的</button></nav>
    {selected && <div className="backdrop" onClick={() => setSelected(null)}><section className="stage-sheet" onClick={(e) => e.stopPropagation()}><div className="sheet-grip" /><div className={`sheet-icon ${selected.stage.is_boss ? "boss" : "normal"}`}>{selected.stage.is_boss ? "鬼" : selected.stage.stage_idx + 1}</div><p>{level?.level} · 第 {selected.zone + 1} 区</p><h2>{stageName(selected.stage)[0]}</h2><span className="jp">{stageName(selected.stage)[1]}</span><div className="reward"><span>本关题库</span><b>{selected.stage.is_boss ? "区域综合" : "专属词汇 + 语法"}</b></div><button className="primary" onClick={beginQuiz}>开始修炼 <span>→</span></button></section></div>}
    {quiz && <section className="quiz-screen">{!result ? <><header><button onClick={() => setQuiz(false)}>×</button><div className="quiz-progress"><i style={{ width: `${questions.length ? ((question + 1) / questions.length) * 100 : 0}%` }} /></div><span>{question + 1}/{questions.length}</span></header>{questions[question] && <div className="quiz-body"><p className="question-type">选择正确答案</p><h2>{questions[question].prompt}</h2><span className="hint">{questions[question].hint}</span><div className="answers">{questions[question].options.map((option, index) => { const state = picked ? option === questions[question].answer ? "correct" : option === picked ? "wrong" : "muted" : ""; return <button className={state} key={option} onClick={() => choose(option)} disabled={!!picked}><i>{String.fromCharCode(65 + index)}</i><span>{option}</span>{state === "correct" && <b>✓</b>}{state === "wrong" && <b>×</b>}</button>; })}</div></div>}</> : <div className="result"><div className="sunburst"><span>忍</span></div><p>修炼完成</p><h2>{result.passed ? "成功通关！" : "再试一次吧"}</h2><div className="result-stars">{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</div><div className="result-grid"><div><small>正确率</small><b>{Math.round(result.accuracy * 100)}%</b></div><div><small>获得经验</small><b>+{result.xp_gained} XP</b></div></div><button className="primary" onClick={() => setQuiz(false)}>返回修炼塔</button></div>}</section>}
  </main>;
}
