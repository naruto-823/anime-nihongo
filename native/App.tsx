import { useAudioPlayer } from "expo-audio";
import * as Haptics from "expo-haptics";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, Alert, Animated, Easing, Modal, Pressable, SafeAreaView,
  ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";

import { api, authenticate, clearSession, restoreSession } from "./src/api";
import type { Coverage, DueData, Player, Question, Stage, TowerMap, User, VocabItem } from "./src/types";

type Tab = "tower" | "vocab" | "review" | "profile";
type Selection = { stage: Stage; zone: number };
type Score = { passed: boolean; stars: number; accuracy: number; xp_gained?: number };

const MUSIC = require("./assets/audio/dojo-loop.wav");
const TAP = require("./assets/audio/tap.wav");
const CORRECT = require("./assets/audio/correct.wav");
const WRONG = require("./assets/audio/wrong.wav");
const COMPLETE = require("./assets/audio/complete.wav");

function stageName(stage: Stage, zone: number) {
  const first = [["入门试炼", "はじめの一歩"], ["五十音之森", "かなの森"], ["词汇道场", "言葉の道場"], ["助词迷阵", "助詞の迷路"], ["动词山道", "動詞の山道"]];
  const themes = [["基础之里", "基礎の里"], ["日常村落", "日常の村"], ["时光回廊", "時の回廊"], ["数词秘境", "数の秘境"], ["形容之庭", "形容の庭"], ["动词峡谷", "動詞の谷"], ["助词机关", "助詞の砦"], ["会话港口", "会話の港"], ["听解瀑布", "聞き取りの滝"], ["阅读古卷", "読解の巻"], ["综合天守", "総合の天守"]];
  const trials = [["词印初探", "言葉の印"], ["读音追踪", "読みの追跡"], ["语法结界", "文法の結界"], ["句型演武", "文型の稽古"], ["实战试炼", "実戦試練"]];
  if (zone === 0 && !stage.is_boss) return first[stage.stage_idx] ?? [`基础修炼 ${stage.stage_idx + 1}`, "基礎修行"];
  const theme = themes[zone] ?? [`第 ${zone + 1} 区`, `第${zone + 1}区`];
  if (stage.is_boss) return [`${theme[0]}守门人`, `${theme[1]}の門番`];
  const trial = trials[stage.stage_idx] ?? [`修炼 ${stage.stage_idx + 1}`, "修行"];
  return [`${theme[0]} · ${trial[0]}`, trial[1]];
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState(""); const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("tower"); const [tower, setTower] = useState<TowerMap | null>(null);
  const [player, setPlayer] = useState<Player | null>(null); const [levelIndex, setLevelIndex] = useState(0);
  const [vocab, setVocab] = useState<VocabItem[]>([]); const [due, setDue] = useState<DueData>({ vocab: [], grammar: [] });
  const [coverage, setCoverage] = useState<Coverage | null>(null); const [selected, setSelected] = useState<Selection | null>(null);
  const [challenge, setChallenge] = useState<Selection | null>(null); const [questions, setQuestions] = useState<Question[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0); const [picked, setPicked] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Array<{ item: Question["item"]; correct: boolean }>>([]);
  const [result, setResult] = useState<Score | null>(null); const [soundOn, setSoundOn] = useState(true);
  const entrance = useRef(new Animated.Value(0)).current;
  const music = useAudioPlayer(MUSIC); const tap = useAudioPlayer(TAP); const correct = useAudioPlayer(CORRECT);
  const wrong = useAudioPlayer(WRONG); const complete = useAudioPlayer(COMPLETE);

  const level = tower?.levels[levelIndex];
  const xpPercent = useMemo(() => ((player?.total_xp ?? 0) % 500) / 5, [player]);

  function play(playerRef: typeof tap) {
    if (!soundOn) return;
    void playerRef.seekTo(0).then(() => playerRef.play()).catch(() => undefined);
  }

  useEffect(() => {
    music.loop = true; music.volume = .10;
    if (user && soundOn) music.play(); else music.pause();
  }, [music, soundOn, user]);

  useEffect(() => {
    entrance.setValue(0);
    Animated.timing(entrance, { toValue: 1, duration: 430, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  }, [entrance, tab, levelIndex]);

  async function loadGame() {
    const [map, stats] = await Promise.all([api<TowerMap>("/api/tower"), api<Player>("/api/player")]);
    setTower(map); setPlayer(stats);
  }

  useEffect(() => {
    void restoreSession().then(async (session) => { setUser(session); if (session) await loadGame(); })
      .catch(() => setError("登录状态恢复失败")).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user || tab === "tower") return;
    setLoading(true);
    const task = tab === "vocab"
      ? api<{ items: VocabItem[] }>("/api/vocab?level=N5&limit=100").then((x) => setVocab(x.items))
      : tab === "review" ? api<DueData>("/api/srs/due").then(setDue) : api<Coverage>("/api/curriculum/coverage").then(setCoverage);
    void task.catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [tab, user]);

  async function submitAuth() {
    setLoading(true); setError("");
    try { const session = await authenticate(mode, username.trim(), password); setUser(session); await loadGame(); }
    catch (e) { setError(e instanceof Error ? e.message : "登录失败"); } finally { setLoading(false); }
  }

  function openStage(stage: Stage, zone: number) {
    if (!stage.unlocked) return;
    play(tap); void Haptics.selectionAsync(); setSelected({ stage, zone });
  }

  async function startQuiz() {
    if (!selected || !level) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ level: level.level, zone: String(selected.zone), stage: String(selected.stage.stage_idx), boss: selected.stage.is_boss ? "1" : "0" });
      const data = await api<{ questions: Question[] }>(`/api/tower/quiz?${params}`);
      setChallenge(selected); setSelected(null); setQuestions(data.questions); setQuestionIndex(0); setPicked(null); setAnswers([]); setResult(null);
    } catch (e) { setError(e instanceof Error ? e.message : "题目加载失败"); } finally { setLoading(false); }
  }

  function choose(option: string) {
    const current = questions[questionIndex];
    if (!current || !challenge || !level || picked) return;
    const isCorrect = option === current.answer;
    setPicked(option); play(isCorrect ? correct : wrong);
    void (isCorrect ? Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success) : Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));
    const next = [...answers, { item: current.item, correct: isCorrect }]; setAnswers(next);
    setTimeout(async () => {
      if (questionIndex < questions.length - 1) { setQuestionIndex((value) => value + 1); setPicked(null); return; }
      try {
        const score = await api<Score>("/api/tower/submit", { method: "POST", body: JSON.stringify({ level: level.level, zone: challenge.zone, stage: challenge.stage.stage_idx, boss: challenge.stage.is_boss, results: next }) });
        setResult(score); play(complete); await loadGame();
      } catch (e) { Alert.alert("提交失败", e instanceof Error ? e.message : "请稍后重试"); }
    }, 720);
  }

  async function review(kind: "vocab" | "grammar", id: number, grade: "again" | "good") {
    play(tap); await api("/api/srs/review", { method: "POST", body: JSON.stringify({ item_type: kind, item_id: id, grade }) });
    setDue(await api<DueData>("/api/srs/due"));
  }

  function switchTab(next: Tab) { play(tap); void Haptics.selectionAsync(); setTab(next); }

  if (loading && !user) return <SafeAreaView style={styles.center}><ActivityIndicator color="#d5aa2e" /></SafeAreaView>;
  if (!user) return <SafeAreaView style={styles.auth}><StatusBar style="light" /><View style={styles.authCard}><View style={styles.mark}><Text style={styles.markText}>忍</Text></View><Text style={styles.brand}>追番日语</Text><Text style={styles.authTitle}>修炼塔</Text><Text style={styles.muted}>iOS / Android 同步修炼进度</Text><TextInput style={styles.input} value={username} onChangeText={setUsername} autoCapitalize="none" placeholder="用户名" /><TextInput style={styles.input} value={password} onChangeText={setPassword} secureTextEntry placeholder="密码（至少 6 位）" />{!!error && <Text style={styles.error}>{error}</Text>}<Pressable style={styles.primary} onPress={submitAuth}><Text style={styles.primaryText}>{mode === "login" ? "登录并继续" : "创建账号"}</Text></Pressable><Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}><Text style={styles.switch}>{mode === "login" ? "第一次来？创建账号" : "已有账号？返回登录"}</Text></Pressable></View></SafeAreaView>;

  return <SafeAreaView style={styles.shell}><StatusBar style="light" />
    <View style={styles.hero}><Text style={styles.heroGlyph}>忍</Text><View style={styles.heroTop}><Text style={styles.brandLight}>追番日语</Text><View style={styles.heroActions}><Pressable onPress={() => setSoundOn(!soundOn)} style={styles.sound}><Text style={styles.soundText}>{soundOn ? "♪" : "×"}</Text></Pressable><Text style={styles.user}>{user.username}</Text></View></View><View style={styles.heroRow}><View><Text style={styles.gold}>修炼塔 · {level?.level ?? "N5"}</Text><Text style={styles.heroTitle}>忍者之路</Text></View><View style={styles.rank}><Text style={styles.level}>{player?.player_level ?? 1}</Text><Text style={styles.rankLabel}>忍者等级</Text></View></View><View style={styles.xpRow}><Text>Lv. {player?.player_level ?? 1}</Text><Text>{player?.total_xp ?? 0} XP</Text></View><View style={styles.xp}><View style={[styles.xpFill, { width: `${xpPercent}%` }]} /></View></View>
    {!!error && <Pressable style={styles.banner} onPress={() => setError("")}><Text>{error}　×</Text></Pressable>}
    <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
      <Animated.View style={{ opacity: entrance, transform: [{ translateY: entrance.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }}>
      {tab === "tower" && <><ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.levelTabs}>{tower?.levels.map((item, index) => <Pressable key={item.level} disabled={!item.unlocked} onPress={() => { play(tap); setLevelIndex(index); }} style={[styles.levelTab, index === levelIndex && styles.levelTabActive]}><Text style={index === levelIndex ? styles.white : styles.dark}>{item.unlocked ? item.level : `🔒 ${item.level}`}</Text></Pressable>)}</ScrollView><View style={styles.chapter}><View style={styles.chapterMark}><Text style={styles.chapterMarkText}>壹</Text></View><View><Text style={styles.sectionTitle}>{level?.level} · 基础修炼</Text><Text style={styles.muted}>每关题目来自独立词汇与语法题库</Text></View></View><View style={styles.map}><View style={styles.path} />{level?.zones.flatMap((zone) => zone.stages.map((stage, index) => { const row = zone.zone_idx * 6 + index; const [name, jp] = stageName(stage, zone.zone_idx); const current = stage.unlocked && !stage.cleared; return <StageRow key={`${zone.zone_idx}-${stage.stage_idx}-${stage.is_boss}`} side={row % 2 ? "right" : "left"} stage={stage} current={current} name={name} jp={jp} onPress={() => openStage(stage, zone.zone_idx)} />; }))}</View></>}
      {tab === "vocab" && <><PageHeading eyebrow="忍术卷轴" title="N5 词卷" subtitle={`共 ${vocab.length} 个基础词汇`} />{vocab.map((item) => <View style={styles.listCard} key={item.id}><View><Text style={styles.word}>{item.headword}</Text><Text style={styles.muted}>{item.reading}</Text></View><Text style={styles.meaning}>{item.meaning_zh}</Text></View>)}</>}
      {tab === "review" && <><PageHeading eyebrow="今日复习" title="火之修行" subtitle={`${due.vocab.length + due.grammar.length} 项等待复习`} />{due.vocab.length + due.grammar.length === 0 ? <View style={styles.emptyState}><Text style={styles.emptyIcon}>火</Text><Text style={styles.word}>今日修行完成</Text><Text style={styles.muted}>去修炼塔挑战新关卡吧</Text></View> : <>{due.vocab.map((item) => <ReviewCard key={`v${item.id}`} title={item.headword ?? ""} subtitle={`${item.reading} · ${item.meaning_zh}`} onAgain={() => review("vocab", item.id, "again")} onGood={() => review("vocab", item.id, "good")} />)}{due.grammar.map((item) => <ReviewCard key={`g${item.id}`} title={item.name ?? ""} subtitle={item.explanation ?? ""} onAgain={() => review("grammar", item.id, "again")} onGood={() => review("grammar", item.id, "good")} />)}</> }</>}
      {tab === "profile" && <><PageHeading eyebrow="忍者档案" title={user.username} subtitle="你的修炼数据已在所有设备同步" /><View style={styles.soundSetting}><View><Text style={styles.word}>音乐与音效</Text><Text style={styles.muted}>原创和风音乐 · 尊重系统静音设置</Text></View><Pressable onPress={() => setSoundOn(!soundOn)} style={[styles.toggle, soundOn && styles.toggleOn]}><View style={[styles.toggleKnob, soundOn && styles.toggleKnobOn]} /></Pressable></View><View style={styles.stats}><Stat label="忍者等级" value={`Lv. ${player?.player_level ?? 1}`} /><Stat label="总经验" value={`${player?.total_xp ?? 0} XP`} /><Stat label="课程知识点" value={String(coverage?.totals.content_items ?? "—")} /><Stat label="掌握率" value={`${coverage?.totals.mastery_percent ?? 0}%`} /></View>{coverage?.levels.map((item) => <View style={styles.coverage} key={item.level}><Text style={styles.word}>{item.level}</Text><Text style={styles.muted}>{item.vocab.total} 词 · {item.grammar.total} 语法</Text><Text style={styles.gold}>{item.mastery_percent}%</Text></View>)}<Pressable style={styles.logout} onPress={async () => { music.pause(); await clearSession(); setUser(null); }}><Text style={styles.error}>退出账号</Text></Pressable></>}
      </Animated.View>
    </ScrollView>
    {loading && <View style={styles.loading}><ActivityIndicator color="#d5aa2e" /></View>}
    <View style={styles.nav}>{([["tower", "塔", "修炼"], ["vocab", "巻", "词卷"], ["review", "火", "复习"], ["profile", "人", "我的"]] as const).map(([key, icon, label]) => <Pressable key={key} onPress={() => switchTab(key)} style={styles.navItem}><View style={[styles.navIconBox, tab === key && styles.navIconActive]}><Text style={[styles.navIcon, tab === key && styles.navIconTextActive]}>{icon}</Text></View><Text style={tab === key ? styles.red : styles.muted}>{label}</Text></Pressable>)}</View>
    <StageSheet selected={selected} levelName={level?.level ?? "N5"} onClose={() => setSelected(null)} onStart={startQuiz} />
    <Modal visible={!!challenge} animationType="slide" presentationStyle="pageSheet"><SafeAreaView style={styles.quiz}>{!result ? <><View style={styles.quizHead}><Pressable onPress={() => setChallenge(null)}><Text style={styles.close}>×</Text></Pressable><View style={styles.quizProgress}><View style={[styles.quizProgressFill, { width: `${questions.length ? ((questionIndex + 1) / questions.length) * 100 : 0}%` }]} /></View><Text style={styles.muted}>{questionIndex + 1}/{questions.length}</Text></View>{questions[questionIndex] && <View style={styles.quizBody}><Text style={styles.questionType}>选择正确答案</Text><Text style={styles.question}>{questions[questionIndex].prompt}</Text><Text style={styles.hint}>{questions[questionIndex].hint}</Text>{questions[questionIndex].options.map((option, index) => { const state = picked ? option === questions[questionIndex].answer ? "correct" : option === picked ? "wrong" : "muted" : ""; return <Pressable key={`${option}-${index}`} disabled={!!picked} style={[styles.answer, state === "correct" && styles.answerCorrect, state === "wrong" && styles.answerWrong, state === "muted" && styles.answerMuted]} onPress={() => choose(option)}><Text style={[styles.answerLetter, state === "correct" && styles.answerLetterCorrect, state === "wrong" && styles.answerLetterWrong]}>{String.fromCharCode(65 + index)}</Text><Text style={styles.answerText}>{option}</Text>{state === "correct" && <Text style={styles.correct}>✓</Text>}{state === "wrong" && <Text style={styles.errorMark}>×</Text>}</Pressable>; })}</View>}</> : <ResultView result={result} onClose={() => setChallenge(null)} />}</SafeAreaView></Modal>
  </SafeAreaView>;
}

function StageRow({ side, stage, current, name, jp, onPress }: { side: "left" | "right"; stage: Stage; current: boolean; name: string; jp: string; onPress: () => void }) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => { if (!current) return; const loop = Animated.loop(Animated.sequence([Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }), Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true })])); loop.start(); return () => loop.stop(); }, [current, pulse]);
  const node = <Animated.View style={[styles.nodeWrap, current && { transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.07] }) }] }]}><Pressable onPress={onPress} disabled={!stage.unlocked} style={({ pressed }) => [styles.node, stage.cleared && styles.done, current && styles.current, !stage.unlocked && styles.lockedNode, stage.is_boss && styles.boss, pressed && stage.unlocked && styles.nodePressed]}><Text style={styles.nodeText}>{stage.is_boss ? "鬼" : stage.cleared ? "✓" : !stage.unlocked ? "鎖" : stage.stage_idx + 1}</Text></Pressable></Animated.View>;
  const copy = <View style={[styles.stageCopy, side === "right" && styles.stageCopyRight]}><Text style={styles.stageTitle}>{name}</Text><Text style={styles.stageJp}>{jp}</Text>{stage.cleared && <Text style={styles.stageStars}>{"★".repeat(stage.stars)}{"☆".repeat(3 - stage.stars)}</Text>}{current && <Text style={styles.currentTag}>可挑战</Text>}</View>;
  return <View style={[styles.stageRow, side === "right" && styles.stageRowRight]}>{side === "left" ? <>{node}{copy}</> : <>{copy}{node}</>}</View>;
}

function StageSheet({ selected, levelName, onClose, onStart }: { selected: Selection | null; levelName: string; onClose: () => void; onStart: () => void }) {
  if (!selected) return null; const [name, jp] = stageName(selected.stage, selected.zone);
  return <Modal visible transparent animationType="slide" onRequestClose={onClose}><Pressable style={styles.backdrop} onPress={onClose}><Pressable style={styles.sheet} onPress={() => undefined}><View style={styles.grip} /><View style={[styles.sheetIcon, selected.stage.is_boss && styles.sheetBoss]}><Text style={[styles.sheetIconText, selected.stage.is_boss && styles.gold]}>{selected.stage.is_boss ? "鬼" : selected.stage.stage_idx + 1}</Text></View><Text style={styles.sheetEyebrow}>{levelName} · 第 {selected.zone + 1} 区</Text><Text style={styles.sheetTitle}>{name}</Text><Text style={styles.stageJp}>{jp}</Text><View style={styles.reward}><Text>本关题库</Text><Text style={styles.gold}>{selected.stage.is_boss ? "区域综合" : "专属词汇 + 语法"}</Text></View><Pressable style={styles.primary} onPress={onStart}><Text style={styles.primaryText}>开始修炼　→</Text></Pressable></Pressable></Pressable></Modal>;
}

function ResultView({ result, onClose }: { result: Score; onClose: () => void }) { return <View style={styles.result}><View style={styles.sunburst}><View style={styles.resultMark}><Text style={styles.markText}>忍</Text></View></View><Text style={styles.sheetEyebrow}>修炼完成</Text><Text style={styles.pageTitle}>{result.passed ? "成功通关！" : "再试一次吧"}</Text><Text style={styles.stars}>{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</Text><View style={styles.resultGrid}><Stat label="正确率" value={`${Math.round(result.accuracy * 100)}%`} /><Stat label="获得经验" value={`+${result.xp_gained ?? 0} XP`} /></View><Pressable style={[styles.primary, styles.resultButton]} onPress={onClose}><Text style={styles.primaryText}>返回修炼塔</Text></Pressable></View>; }
function PageHeading({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle: string }) { return <View style={styles.pageHead}><Text style={styles.sheetEyebrow}>{eyebrow}</Text><Text style={styles.pageTitle}>{title}</Text><Text style={styles.muted}>{subtitle}</Text></View>; }
function Stat({ label, value }: { label: string; value: string }) { return <View style={styles.stat}><Text style={styles.muted}>{label}</Text><Text style={styles.statValue}>{value}</Text></View>; }
function ReviewCard({ title, subtitle, onAgain, onGood }: { title: string; subtitle: string; onAgain: () => void; onGood: () => void }) { return <View style={styles.listCard}><View style={{ flex: 1 }}><Text style={styles.word}>{title}</Text><Text style={styles.muted}>{subtitle}</Text></View><Pressable onPress={onAgain}><Text>再练　</Text></Pressable><Pressable onPress={onGood}><Text style={styles.green}>记住了</Text></Pressable></View>; }

const styles = StyleSheet.create({
  shell:{flex:1,backgroundColor:"#f5f0e6"},center:{flex:1,alignItems:"center",justifyContent:"center"},auth:{flex:1,backgroundColor:"#173b31",alignItems:"center",justifyContent:"center",padding:24},authCard:{width:"100%",maxWidth:420,backgroundColor:"#fbf7ef",padding:28,borderRadius:24},mark:{width:60,height:60,borderRadius:30,backgroundColor:"#284c3f",borderWidth:5,borderColor:"#e8d9ad",alignItems:"center",justifyContent:"center"},markText:{fontSize:32,fontWeight:"900",color:"#fff"},brand:{marginTop:16,color:"#315e4d",fontWeight:"800"},authTitle:{fontSize:38,fontWeight:"900",color:"#17382e",marginVertical:8},muted:{fontSize:12,color:"#918a7f"},input:{height:50,borderWidth:1,borderColor:"#ded5c5",borderRadius:12,paddingHorizontal:15,marginTop:14,backgroundColor:"#fff"},primary:{height:52,borderRadius:14,backgroundColor:"#c94736",alignItems:"center",justifyContent:"center",marginTop:20,shadowColor:"#8d3025",shadowOffset:{width:0,height:5},shadowOpacity:1,shadowRadius:0,elevation:3},primaryText:{color:"#fff",fontWeight:"800"},switch:{textAlign:"center",color:"#315e4d",marginTop:18},error:{color:"#b63c31",marginTop:10},
  hero:{backgroundColor:"#173b31",padding:22,paddingBottom:25,borderBottomLeftRadius:27,borderBottomRightRadius:27,overflow:"hidden"},heroGlyph:{position:"absolute",right:-15,bottom:-57,color:"#fff",opacity:.035,fontSize:150,fontWeight:"900",transform:[{rotate:"-8deg"}]},heroTop:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},heroActions:{flexDirection:"row",alignItems:"center",gap:8},sound:{width:31,height:31,borderRadius:16,borderWidth:1,borderColor:"#ffffff38",alignItems:"center",justifyContent:"center",backgroundColor:"#ffffff10"},soundText:{color:"#fff",fontWeight:"900"},brandLight:{color:"#dbe6df",fontWeight:"800",letterSpacing:3},user:{color:"#fff",fontSize:12},heroRow:{flexDirection:"row",justifyContent:"space-between",alignItems:"flex-end",marginTop:25},gold:{color:"#d5aa2e",fontWeight:"800"},heroTitle:{fontSize:35,color:"#fff",fontWeight:"900",marginTop:5,letterSpacing:3},rank:{alignItems:"center",borderLeftWidth:1,borderColor:"#ffffff25",paddingLeft:18},level:{color:"#f2c83d",fontSize:28,fontWeight:"900"},rankLabel:{color:"#ffffff90",fontSize:10,marginTop:3},xpRow:{flexDirection:"row",justifyContent:"space-between",marginTop:20,color:"#fff"},xp:{height:7,backgroundColor:"#35574e",borderRadius:5,marginTop:7,overflow:"hidden"},xpFill:{height:7,backgroundColor:"#e2bd45"},banner:{padding:10,backgroundColor:"#f6d9d5"},
  content:{flex:1},contentInner:{padding:18,paddingBottom:105},levelTabs:{marginBottom:18},levelTab:{paddingVertical:9,paddingHorizontal:15,borderRadius:10,marginRight:8,backgroundColor:"#e9e1d4",borderWidth:1,borderColor:"#ded5c5"},levelTabActive:{backgroundColor:"#315e4d",borderColor:"#315e4d"},white:{color:"#fff",fontWeight:"800"},dark:{color:"#575047"},chapter:{height:62,backgroundColor:"#fffdf8",borderRadius:15,borderWidth:1,borderColor:"#ded5c4",padding:10,flexDirection:"row",alignItems:"center",gap:11},chapterMark:{width:40,height:40,borderRadius:11,backgroundColor:"#284c3f",alignItems:"center",justifyContent:"center"},chapterMarkText:{color:"#fff",fontSize:22,fontWeight:"900"},sectionTitle:{fontSize:16,fontWeight:"900",color:"#172d26"},map:{position:"relative",paddingVertical:13,minHeight:900},path:{position:"absolute",left:"50%",top:12,bottom:0,width:3,borderLeftWidth:3,borderStyle:"dashed",borderColor:"#c9bda6"},stageRow:{height:108,flexDirection:"row",alignItems:"center",paddingLeft:20},stageRowRight:{justifyContent:"flex-end",paddingLeft:0,paddingRight:20},nodeWrap:{zIndex:2},node:{width:68,height:68,borderRadius:34,backgroundColor:"#cfc8bb",alignItems:"center",justifyContent:"center",borderWidth:5,borderColor:"#ebe3d5",shadowColor:"#40382c",shadowOffset:{width:0,height:6},shadowOpacity:.26,shadowRadius:5,elevation:5},nodePressed:{transform:[{translateY:4}]},done:{backgroundColor:"#47705f",borderColor:"#aac6ba"},current:{backgroundColor:"#c94736",borderColor:"#f0c5bb"},lockedNode:{opacity:.68},boss:{width:76,height:76,borderRadius:38,backgroundColor:"#252724",borderColor:"#d4a940"},nodeText:{color:"#fff",fontWeight:"900",fontSize:24},stageCopy:{width:120,marginHorizontal:12},stageCopyRight:{alignItems:"flex-end"},stageTitle:{fontWeight:"900",color:"#172d26",fontSize:13},stageJp:{color:"#989084",fontSize:11,marginTop:4},stageStars:{color:"#d7a62c",fontSize:12,marginTop:4},currentTag:{fontSize:9,color:"#fff",backgroundColor:"#c94736",borderRadius:9,paddingVertical:2,paddingHorizontal:7,marginTop:5,overflow:"hidden"},
  pageHead:{marginBottom:23},sheetEyebrow:{color:"#a78635",fontSize:11,fontWeight:"800",letterSpacing:2,marginBottom:5},pageTitle:{fontSize:28,fontWeight:"900",color:"#17382e",marginBottom:6},listCard:{flexDirection:"row",alignItems:"center",gap:12,backgroundColor:"#fffdf9",padding:15,borderRadius:14,marginBottom:10,borderWidth:1,borderColor:"#ded5c5"},word:{fontSize:17,fontWeight:"900",color:"#17382e"},meaning:{marginLeft:"auto",color:"#625b52"},emptyState:{alignItems:"center",justifyContent:"center",height:350,gap:8},emptyIcon:{width:74,height:74,borderRadius:37,textAlign:"center",paddingTop:17,backgroundColor:"#f0e6d5",color:"#c94736",fontSize:30,fontWeight:"900",overflow:"hidden"},stats:{flexDirection:"row",flexWrap:"wrap",gap:10},stat:{width:"48%",backgroundColor:"#fff",borderRadius:14,padding:16,borderWidth:1,borderColor:"#e1d8c9"},statValue:{color:"#315e4d",fontWeight:"900",fontSize:18,marginTop:5},coverage:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",backgroundColor:"#fff",padding:14,marginTop:9,borderRadius:12},soundSetting:{backgroundColor:"#fffdf9",borderWidth:1,borderColor:"#ded5c5",borderRadius:15,padding:16,marginBottom:16,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},toggle:{width:48,height:28,borderRadius:14,backgroundColor:"#cfc8bd",padding:3},toggleOn:{backgroundColor:"#315e4d"},toggleKnob:{width:22,height:22,borderRadius:11,backgroundColor:"#fff"},toggleKnobOn:{marginLeft:20},logout:{alignItems:"center",padding:18,marginTop:18},
  nav:{height:82,backgroundColor:"#fffdf8",borderTopWidth:1,borderColor:"#ded5c5",flexDirection:"row"},navItem:{flex:1,alignItems:"center",justifyContent:"center",gap:3},navIconBox:{width:32,height:32,alignItems:"center",justifyContent:"center"},navIconActive:{backgroundColor:"#c94736",borderRadius:9},navIcon:{fontSize:21,color:"#a59d90",fontWeight:"900"},navIconTextActive:{color:"#fff"},red:{fontSize:11,color:"#c94736"},green:{color:"#315e4d",fontWeight:"800"},loading:{position:"absolute",top:0,bottom:82,left:0,right:0,alignItems:"center",justifyContent:"center",backgroundColor:"#ffffff88"},
  backdrop:{flex:1,backgroundColor:"#111a",justifyContent:"flex-end"},sheet:{backgroundColor:"#fffdf8",borderTopLeftRadius:27,borderTopRightRadius:27,padding:24,paddingBottom:35,alignItems:"center"},grip:{width:42,height:4,borderRadius:4,backgroundColor:"#d8d1c5",marginBottom:20},sheetIcon:{width:72,height:72,borderRadius:36,backgroundColor:"#c94736",borderWidth:6,borderColor:"#f0dfd3",alignItems:"center",justifyContent:"center",marginBottom:18},sheetBoss:{backgroundColor:"#252724",borderColor:"#e9dba9"},sheetIconText:{color:"#fff",fontSize:27,fontWeight:"900"},sheetTitle:{fontSize:27,fontWeight:"900",color:"#17382e"},reward:{width:"100%",backgroundColor:"#f3ede2",borderRadius:12,padding:14,marginTop:22,flexDirection:"row",justifyContent:"space-between"},
  quiz:{flex:1,backgroundColor:"#f8f3ea"},quizHead:{height:70,paddingHorizontal:20,flexDirection:"row",gap:14,alignItems:"center"},close:{fontSize:30,color:"#8f887d"},quizProgress:{height:7,flex:1,backgroundColor:"#ded7ca",borderRadius:8,overflow:"hidden"},quizProgressFill:{height:7,backgroundColor:"#c94736"},quizBody:{padding:24,paddingTop:32},questionType:{color:"#ad842a",fontSize:11,fontWeight:"800",letterSpacing:2},question:{fontSize:29,fontWeight:"900",color:"#17382e",marginTop:16,marginBottom:7,lineHeight:40},hint:{color:"#8b867d",fontSize:13,marginBottom:34},answer:{minHeight:62,backgroundColor:"#fffdf9",borderRadius:15,padding:13,marginBottom:12,flexDirection:"row",alignItems:"center",borderWidth:1.5,borderColor:"#d8cfc0",shadowColor:"#8b7f6d",shadowOffset:{width:0,height:3},shadowOpacity:.2,shadowRadius:0},answerCorrect:{borderColor:"#3f795f",backgroundColor:"#edf7f1"},answerWrong:{borderColor:"#c74635",backgroundColor:"#fff0ed"},answerMuted:{opacity:.42},answerLetter:{width:34,height:34,textAlign:"center",paddingTop:7,borderRadius:10,backgroundColor:"#eee8dd",fontWeight:"800",color:"#786f63"},answerLetterCorrect:{backgroundColor:"#3f795f",color:"#fff"},answerLetterWrong:{backgroundColor:"#c74635",color:"#fff"},answerText:{fontSize:16,fontWeight:"700",marginLeft:13,flex:1},correct:{color:"#3f795f",fontSize:22,fontWeight:"900"},errorMark:{color:"#c74635",fontSize:24,fontWeight:"900"},
  result:{flex:1,alignItems:"center",justifyContent:"center",padding:30},sunburst:{width:126,height:126,borderRadius:63,backgroundColor:"#f0cf70",alignItems:"center",justifyContent:"center",marginBottom:28},resultMark:{width:78,height:78,borderRadius:39,backgroundColor:"#24483b",borderWidth:6,borderColor:"#f8f4eb",alignItems:"center",justifyContent:"center"},stars:{fontSize:36,color:"#d5aa2e",marginVertical:16,letterSpacing:5},resultGrid:{width:"100%",flexDirection:"row",gap:10},resultButton:{width:"100%",marginTop:24},
});
