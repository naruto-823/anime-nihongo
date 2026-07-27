"use client";

import { useEffect, useMemo, useState } from "react";

type Stage = { id: number; label: string; jp: string; type: "normal" | "boss"; xp: number };

const stages: Stage[] = [
  { id: 1, label: "入门试炼", jp: "はじめの一歩", type: "normal", xp: 40 },
  { id: 2, label: "五十音之森", jp: "かなの森", type: "normal", xp: 50 },
  { id: 3, label: "词汇道场", jp: "言葉の道場", type: "normal", xp: 60 },
  { id: 4, label: "助词迷阵", jp: "助詞の迷路", type: "normal", xp: 70 },
  { id: 5, label: "赤鬼守门人", jp: "赤鬼の門番", type: "boss", xp: 120 },
  { id: 6, label: "动词山道", jp: "動詞の山道", type: "normal", xp: 80 },
  { id: 7, label: "听力瀑布", jp: "聞き取りの滝", type: "normal", xp: 90 },
  { id: 8, label: "会话之桥", jp: "会話の橋", type: "normal", xp: 100 },
];

const questions = [
  { prompt: "「食べる」是什么意思？", hint: "たべる · taberu", options: ["吃", "睡觉", "说话", "行走"], answer: "吃" },
  { prompt: "选择「我喜欢动漫」", hint: "好き（すき）= 喜欢", options: ["アニメが好きです", "アニメを食べます", "アニメに行きます", "アニメは寒いです"], answer: "アニメが好きです" },
  { prompt: "「水」的正确读音是？", hint: "日常高频名词", options: ["みず", "みせ", "みち", "みみ"], answer: "みず" },
];

export default function Home() {
  const [cleared, setCleared] = useState(2);
  const [xp, setXp] = useState(360);
  const [selected, setSelected] = useState<Stage | null>(null);
  const [activeStage, setActiveStage] = useState<Stage | null>(null);
  const [quiz, setQuiz] = useState(false);
  const [question, setQuestion] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [correct, setCorrect] = useState(0);
  const [result, setResult] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("nihongo-tower-progress");
    if (saved) {
      const value = JSON.parse(saved) as { cleared: number; xp: number };
      setCleared(value.cleared);
      setXp(value.xp);
    }
  }, []);

  const levelProgress = useMemo(() => Math.min(100, ((xp % 500) / 500) * 100), [xp]);

  function start(stage: Stage) {
    if (stage.id > cleared + 1) return;
    setSelected(stage);
  }

  function beginQuiz() {
    setActiveStage(selected);
    setSelected(null);
    setQuiz(true);
    setQuestion(0);
    setPicked(null);
    setCorrect(0);
    setResult(false);
  }

  function choose(option: string) {
    if (picked) return;
    setPicked(option);
    const isCorrect = option === questions[question].answer;
    const nextCorrect = correct + (isCorrect ? 1 : 0);
    setCorrect(nextCorrect);
    window.setTimeout(() => {
      if (question < questions.length - 1) {
        setQuestion((value) => value + 1);
        setPicked(null);
      } else {
        const gained = activeStage?.xp ?? 40;
        const unlocksNext = nextCorrect >= 2 && activeStage?.id === cleared + 1;
        const nextCleared = Math.min(stages.length, cleared + (unlocksNext ? 1 : 0));
        const nextXp = xp + (nextCorrect >= 2 ? gained : 10);
        setCleared(nextCleared);
        setXp(nextXp);
        localStorage.setItem("nihongo-tower-progress", JSON.stringify({ cleared: nextCleared, xp: nextXp }));
        setResult(true);
      }
    }, 650);
  }

  function closeQuiz() {
    setQuiz(false);
    setResult(false);
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="topline"><span className="eyebrow">追番日语</span><button className="sound" aria-label="声音设置">♪</button></div>
        <div className="hero-copy"><div><p>修炼塔 · 第一章</p><h1>忍者之路</h1></div><div className="streak"><b>7</b><span>连胜天数</span></div></div>
        <div className="xp-row"><span>Lv. 3 下忍</span><span>{xp} / 500 XP</span></div>
        <div className="xp-track"><i style={{ width: `${levelProgress}%` }} /></div>
      </header>

      <section className="map" aria-label="修炼塔关卡地图">
        <div className="chapter"><span>壹</span><div><b>N5 · 基础修炼</b><small>完成每关，向塔顶进发</small></div><em>{cleared}/{stages.length}</em></div>
        <div className="path" />
        {stages.map((stage, index) => {
          const done = stage.id <= cleared;
          const current = stage.id === cleared + 1;
          const locked = stage.id > cleared + 1;
          return (
            <article className={`stage-row ${index % 2 ? "right" : "left"}`} key={stage.id}>
              <button className={`stage-node ${done ? "done" : ""} ${current ? "current" : ""} ${locked ? "locked" : ""} ${stage.type === "boss" ? "boss" : ""}`} onClick={() => start(stage)} aria-label={`${stage.label}${locked ? "，未解锁" : ""}`}>
                <span>{stage.type === "boss" ? "鬼" : done ? "✓" : locked ? "鎖" : stage.id}</span>
              </button>
              <div className="stage-copy"><b>{stage.label}</b><small>{stage.jp}</small>{done && <div className="stars">★★★</div>}{current && <i>当前关卡</i>}</div>
            </article>
          );
        })}
      </section>

      <nav className="bottom-nav"><button className="active"><span>塔</span>修炼</button><button><span>巻</span>词卷</button><button><span>火</span>复习</button><button><span>人</span>我的</button></nav>

      {selected && <div className="backdrop" onClick={() => setSelected(null)}><section className="stage-sheet" onClick={(e) => e.stopPropagation()}><div className="sheet-grip" /><div className={`sheet-icon ${selected.type}`}>{selected.type === "boss" ? "鬼" : selected.id}</div><p>第 {selected.id} 关</p><h2>{selected.label}</h2><span className="jp">{selected.jp}</span><div className="reward"><span>本关奖励</span><b>+{selected.xp} XP</b></div><button className="primary" onClick={beginQuiz}>开始修炼 <span>→</span></button></section></div>}

      {quiz && <section className="quiz-screen">
        {!result ? <>
          <header><button onClick={closeQuiz}>×</button><div className="quiz-progress"><i style={{ width: `${((question + 1) / questions.length) * 100}%` }} /></div><span>{question + 1}/{questions.length}</span></header>
          <div className="quiz-body"><p className="question-type">选择正确答案</p><h2>{questions[question].prompt}</h2><span className="hint">{questions[question].hint}</span><div className="answers">{questions[question].options.map((option, index) => { const state = picked ? option === questions[question].answer ? "correct" : option === picked ? "wrong" : "muted" : ""; return <button className={state} key={option} onClick={() => choose(option)} disabled={!!picked}><i>{String.fromCharCode(65 + index)}</i><span>{option}</span>{state === "correct" && <b>✓</b>}{state === "wrong" && <b>×</b>}</button>; })}</div></div>
        </> : <div className="result"><div className="sunburst"><span>忍</span></div><p>修炼完成</p><h2>{correct >= 2 ? "成功通关！" : "再试一次吧"}</h2><div className="result-stars">{correct >= 1 ? "★" : "☆"}{correct >= 2 ? "★" : "☆"}{correct >= 3 ? "★" : "☆"}</div><div className="result-grid"><div><small>正确率</small><b>{Math.round(correct / questions.length * 100)}%</b></div><div><small>获得经验</small><b>+{correct >= 2 ? activeStage?.xp ?? 40 : 10} XP</b></div></div><button className="primary" onClick={closeQuiz}>返回修炼塔</button></div>}
      </section>}
    </main>
  );
}
