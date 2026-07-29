import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { api, authenticate, clearSession, restoreSession } from "./src/api";
import type {
  Coverage,
  DueData,
  Player,
  Question,
  Stage,
  TowerMap,
  User,
  VocabItem,
} from "./src/types";

type Tab = "tower" | "vocab" | "review" | "profile";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("tower");
  const [tower, setTower] = useState<TowerMap | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [levelIndex, setLevelIndex] = useState(0);
  const [vocab, setVocab] = useState<VocabItem[]>([]);
  const [due, setDue] = useState<DueData>({ vocab: [], grammar: [] });
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [challenge, setChallenge] = useState<{ stage: Stage; zone: number } | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Array<{ item: Question["item"]; correct: boolean }>>([]);
  const [result, setResult] = useState<{ passed: boolean; stars: number; accuracy: number } | null>(null);

  const level = tower?.levels[levelIndex];
  const xpPercent = useMemo(() => ((player?.total_xp ?? 0) % 500) / 5, [player]);

  async function loadGame() {
    const [map, stats] = await Promise.all([
      api<TowerMap>("/api/tower"),
      api<Player>("/api/player"),
    ]);
    setTower(map);
    setPlayer(stats);
  }

  useEffect(() => {
    void restoreSession().then(async (session) => {
      setUser(session);
      if (session) await loadGame();
    }).catch(() => setError("登录状态恢复失败")).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user || tab === "tower") return;
    setLoading(true);
    const task = tab === "vocab"
      ? api<{ items: VocabItem[] }>("/api/vocab?level=N5&limit=100").then((x) => setVocab(x.items))
      : tab === "review"
        ? api<DueData>("/api/srs/due").then(setDue)
        : api<Coverage>("/api/curriculum/coverage").then(setCoverage);
    void task.catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [tab, user]);

  async function submitAuth() {
    setLoading(true); setError("");
    try {
      const session = await authenticate(mode, username.trim(), password);
      setUser(session);
      await loadGame();
    } catch (e) { setError(e instanceof Error ? e.message : "登录失败"); }
    finally { setLoading(false); }
  }

  async function startQuiz(stage: Stage, zone: number) {
    if (!level) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        level: level.level, zone: String(zone), stage: String(stage.stage_idx),
        boss: stage.is_boss ? "1" : "0",
      });
      const data = await api<{ questions: Question[] }>(`/api/tower/quiz?${params}`);
      setChallenge({ stage, zone }); setQuestions(data.questions); setQuestionIndex(0);
      setAnswers([]); setResult(null);
    } catch (e) { setError(e instanceof Error ? e.message : "题目加载失败"); }
    finally { setLoading(false); }
  }

  async function choose(option: string) {
    const current = questions[questionIndex];
    if (!current || !challenge || !level) return;
    const next = [...answers, { item: current.item, correct: option === current.answer }];
    if (questionIndex < questions.length - 1) {
      setAnswers(next); setQuestionIndex((value) => value + 1); return;
    }
    try {
      const score = await api<{ passed: boolean; stars: number; accuracy: number }>("/api/tower/submit", {
        method: "POST",
        body: JSON.stringify({ level: level.level, zone: challenge.zone,
          stage: challenge.stage.stage_idx, boss: challenge.stage.is_boss, results: next }),
      });
      setResult(score); await loadGame();
    } catch (e) { Alert.alert("提交失败", e instanceof Error ? e.message : "请稍后重试"); }
  }

  async function review(kind: "vocab" | "grammar", id: number, grade: "again" | "good") {
    await api("/api/srs/review", { method: "POST",
      body: JSON.stringify({ item_type: kind, item_id: id, grade }) });
    setDue(await api<DueData>("/api/srs/due"));
  }

  if (loading && !user) return <SafeAreaView style={styles.center}><ActivityIndicator color="#d5aa2e" /></SafeAreaView>;
  if (!user) return <SafeAreaView style={styles.auth}><StatusBar style="light" /><View style={styles.authCard}>
    <View style={styles.mark}><Text style={styles.markText}>忍</Text></View><Text style={styles.brand}>追番日语</Text>
    <Text style={styles.authTitle}>修炼塔</Text><Text style={styles.muted}>iOS / Android 同步修炼进度</Text>
    <TextInput style={styles.input} value={username} onChangeText={setUsername} autoCapitalize="none" placeholder="用户名" />
    <TextInput style={styles.input} value={password} onChangeText={setPassword} secureTextEntry placeholder="密码（至少 6 位）" />
    {!!error && <Text style={styles.error}>{error}</Text>}
    <Pressable style={styles.primary} onPress={submitAuth}><Text style={styles.primaryText}>{mode === "login" ? "登录并继续" : "创建账号"}</Text></Pressable>
    <Pressable onPress={() => setMode(mode === "login" ? "register" : "login")}><Text style={styles.switch}>{mode === "login" ? "第一次来？创建账号" : "已有账号？返回登录"}</Text></Pressable>
  </View></SafeAreaView>;

  return <SafeAreaView style={styles.shell}><StatusBar style="light" />
    <View style={styles.hero}><View style={styles.heroTop}><Text style={styles.brandLight}>追番日语</Text><Text style={styles.user}>{user.username}</Text></View>
      <View style={styles.heroRow}><View><Text style={styles.gold}>修炼塔 · {level?.level ?? "N5"}</Text><Text style={styles.heroTitle}>忍者之路</Text></View><Text style={styles.level}>Lv.{player?.player_level ?? 1}</Text></View>
      <View style={styles.xp}><View style={[styles.xpFill, { width: `${xpPercent}%` }]} /></View></View>
    {!!error && <Pressable style={styles.banner} onPress={() => setError("")}><Text>{error}　×</Text></Pressable>}
    <ScrollView style={styles.content} contentContainerStyle={styles.contentInner}>
      {tab === "tower" && <><ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.levelTabs}>{tower?.levels.map((item, index) => <Pressable key={item.level} disabled={!item.unlocked} onPress={() => setLevelIndex(index)} style={[styles.levelTab, index === levelIndex && styles.levelTabActive]}><Text style={index === levelIndex ? styles.white : styles.dark}>{item.unlocked ? item.level : `🔒 ${item.level}`}</Text></Pressable>)}</ScrollView>
        <Text style={styles.sectionTitle}>{level?.level} · 全量修炼</Text><Text style={styles.muted}>每关使用独立词汇与语法，并优先训练薄弱维度</Text>
        {level?.zones.flatMap((zone) => zone.stages.map((stage, index) => <Pressable key={`${zone.zone_idx}-${stage.stage_idx}-${stage.is_boss}`} disabled={!stage.unlocked} onPress={() => startQuiz(stage, zone.zone_idx)} style={[styles.stage, !stage.unlocked && styles.locked]}><View style={[styles.node, stage.cleared && styles.done, stage.is_boss && styles.boss]}><Text style={styles.nodeText}>{stage.is_boss ? "鬼" : stage.cleared ? "✓" : stage.unlocked ? index + 1 : "鎖"}</Text></View><View><Text style={styles.stageTitle}>{stage.is_boss ? `第 ${zone.zone_idx + 1} 区守门人` : `第 ${zone.zone_idx + 1} 区 · 修炼 ${stage.stage_idx + 1}`}</Text><Text style={styles.muted}>{stage.cleared ? `${"★".repeat(stage.stars)}${"☆".repeat(3 - stage.stars)}` : stage.unlocked ? "可挑战" : "尚未解锁"}</Text></View></Pressable>))}</>}
      {tab === "vocab" && <><Text style={styles.pageTitle}>N5 词卷</Text>{vocab.map((item) => <View style={styles.listCard} key={item.id}><View><Text style={styles.word}>{item.headword}</Text><Text style={styles.muted}>{item.reading}</Text></View><Text style={styles.meaning}>{item.meaning_zh}</Text></View>)}</>}
      {tab === "review" && <><Text style={styles.pageTitle}>今日复习</Text>{due.vocab.length + due.grammar.length === 0 ? <Text style={styles.empty}>今日修行完成</Text> : <>{due.vocab.map((item) => <ReviewCard key={`v${item.id}`} title={item.headword ?? ""} subtitle={`${item.reading} · ${item.meaning_zh}`} onAgain={() => review("vocab", item.id, "again")} onGood={() => review("vocab", item.id, "good")} />)}{due.grammar.map((item) => <ReviewCard key={`g${item.id}`} title={item.name ?? ""} subtitle={item.explanation ?? ""} onAgain={() => review("grammar", item.id, "again")} onGood={() => review("grammar", item.id, "good")} />)}</>}</>}
      {tab === "profile" && <><Text style={styles.pageTitle}>忍者档案</Text><View style={styles.stats}><Stat label="忍者等级" value={`Lv. ${player?.player_level ?? 1}`} /><Stat label="总经验" value={`${player?.total_xp ?? 0} XP`} /><Stat label="课程知识点" value={String(coverage?.totals.content_items ?? "—")} /><Stat label="掌握率" value={`${coverage?.totals.mastery_percent ?? 0}%`} /></View>{coverage?.levels.map((item) => <View style={styles.coverage} key={item.level}><Text style={styles.word}>{item.level}</Text><Text style={styles.muted}>{item.vocab.total} 词 · {item.grammar.total} 语法</Text><Text style={styles.gold}>{item.mastery_percent}%</Text></View>)}<Pressable style={styles.logout} onPress={async () => { await clearSession(); setUser(null); }}><Text style={styles.error}>退出账号</Text></Pressable></>}
    </ScrollView>
    {loading && <View style={styles.loading}><ActivityIndicator color="#d5aa2e" /></View>}
    <View style={styles.nav}>{([['tower','塔','修炼'],['vocab','巻','词卷'],['review','火','复习'],['profile','人','我的']] as const).map(([key, icon, label]) => <Pressable key={key} onPress={() => setTab(key)} style={styles.navItem}><Text style={[styles.navIcon, tab === key && styles.navActive]}>{icon}</Text><Text style={tab === key ? styles.red : styles.muted}>{label}</Text></Pressable>)}</View>
    <Modal visible={!!challenge} animationType="slide" presentationStyle="pageSheet"><SafeAreaView style={styles.quiz}>{!result ? <><View style={styles.quizHead}><Pressable onPress={() => setChallenge(null)}><Text style={styles.close}>×</Text></Pressable><Text>{questionIndex + 1}/{questions.length}</Text></View>{questions[questionIndex] && <View style={styles.quizBody}><Text style={styles.gold}>{questions[questionIndex].hint}</Text><Text style={styles.question}>{questions[questionIndex].prompt}</Text>{questions[questionIndex].options.map((option, index) => <Pressable key={`${option}-${index}`} style={styles.answer} onPress={() => choose(option)}><Text style={styles.answerLetter}>{String.fromCharCode(65 + index)}</Text><Text style={styles.answerText}>{option}</Text></Pressable>)}</View>}</> : <View style={styles.result}><Text style={styles.markText}>忍</Text><Text style={styles.pageTitle}>{result.passed ? "成功通关！" : "再试一次吧"}</Text><Text style={styles.stars}>{"★".repeat(result.stars)}{"☆".repeat(3 - result.stars)}</Text><Text>正确率 {Math.round(result.accuracy * 100)}%</Text><Pressable style={styles.primary} onPress={() => setChallenge(null)}><Text style={styles.primaryText}>返回修炼塔</Text></Pressable></View>}</SafeAreaView></Modal>
  </SafeAreaView>;
}

function Stat({ label, value }: { label: string; value: string }) { return <View style={styles.stat}><Text style={styles.muted}>{label}</Text><Text style={styles.statValue}>{value}</Text></View>; }
function ReviewCard({ title, subtitle, onAgain, onGood }: { title: string; subtitle: string; onAgain: () => void; onGood: () => void }) { return <View style={styles.listCard}><View style={{ flex: 1 }}><Text style={styles.word}>{title}</Text><Text style={styles.muted}>{subtitle}</Text></View><Pressable onPress={onAgain}><Text>再练　</Text></Pressable><Pressable onPress={onGood}><Text style={styles.green}>记住了</Text></Pressable></View>; }

const styles = StyleSheet.create({
  shell:{flex:1,backgroundColor:"#f5f0e6"},center:{flex:1,alignItems:"center",justifyContent:"center"},auth:{flex:1,backgroundColor:"#173b31",alignItems:"center",justifyContent:"center",padding:24},authCard:{width:"100%",maxWidth:420,backgroundColor:"#fbf7ef",padding:28,borderRadius:24},mark:{width:60,height:60,borderRadius:30,backgroundColor:"#c94736",alignItems:"center",justifyContent:"center"},markText:{fontSize:32,fontWeight:"900",color:"#fff"},brand:{marginTop:16,color:"#315e4d",fontWeight:"800"},authTitle:{fontSize:38,fontWeight:"900",color:"#17382e",marginVertical:8},muted:{fontSize:12,color:"#918a7f"},input:{height:50,borderWidth:1,borderColor:"#ded5c5",borderRadius:12,paddingHorizontal:15,marginTop:14,backgroundColor:"#fff"},primary:{height:52,borderRadius:14,backgroundColor:"#c94736",alignItems:"center",justifyContent:"center",marginTop:20},primaryText:{color:"#fff",fontWeight:"800"},switch:{textAlign:"center",color:"#315e4d",marginTop:18},error:{color:"#b63c31",marginTop:10},hero:{backgroundColor:"#173b31",padding:22,paddingBottom:25},heroTop:{flexDirection:"row",justifyContent:"space-between"},brandLight:{color:"#dbe6df",fontWeight:"800"},user:{color:"#fff"},heroRow:{flexDirection:"row",justifyContent:"space-between",alignItems:"flex-end",marginTop:25},gold:{color:"#d5aa2e",fontWeight:"800"},heroTitle:{fontSize:35,color:"#fff",fontWeight:"900",marginTop:5},level:{color:"#f2c83d",fontSize:25,fontWeight:"900"},xp:{height:7,backgroundColor:"#35574e",borderRadius:5,marginTop:20,overflow:"hidden"},xpFill:{height:7,backgroundColor:"#e2bd45"},banner:{padding:10,backgroundColor:"#f6d9d5"},content:{flex:1},contentInner:{padding:18,paddingBottom:105},levelTabs:{marginBottom:20},levelTab:{paddingVertical:11,paddingHorizontal:18,borderRadius:12,marginRight:8,backgroundColor:"#e9e1d4"},levelTabActive:{backgroundColor:"#315e4d"},white:{color:"#fff",fontWeight:"800"},dark:{color:"#575047"},sectionTitle:{fontSize:20,fontWeight:"900",color:"#172d26"},stage:{flexDirection:"row",alignItems:"center",gap:18,padding:15,marginTop:14,backgroundColor:"#fffdf8",borderRadius:18},locked:{opacity:.45},node:{width:58,height:58,borderRadius:29,backgroundColor:"#c94736",alignItems:"center",justifyContent:"center",borderWidth:4,borderColor:"#f3b6aa"},done:{backgroundColor:"#497d68",borderColor:"#a8c2b6"},boss:{backgroundColor:"#202721",borderColor:"#d5aa2e"},nodeText:{color:"#fff",fontWeight:"900",fontSize:22},stageTitle:{fontWeight:"900",color:"#172d26",marginBottom:5},pageTitle:{fontSize:26,fontWeight:"900",color:"#17382e",marginBottom:15},listCard:{flexDirection:"row",alignItems:"center",gap:12,backgroundColor:"#fff",padding:15,borderRadius:14,marginBottom:10},word:{fontSize:17,fontWeight:"900",color:"#17382e"},meaning:{marginLeft:"auto",color:"#625b52"},empty:{textAlign:"center",marginTop:100,color:"#918a7f"},stats:{flexDirection:"row",flexWrap:"wrap",gap:10},stat:{width:"48%",backgroundColor:"#fff",borderRadius:14,padding:16},statValue:{color:"#315e4d",fontWeight:"900",fontSize:18,marginTop:5},coverage:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",backgroundColor:"#fff",padding:14,marginTop:9,borderRadius:12},logout:{alignItems:"center",padding:18,marginTop:18},nav:{height:82,backgroundColor:"#fffdf8",borderTopWidth:1,borderColor:"#ded5c5",flexDirection:"row"},navItem:{flex:1,alignItems:"center",justifyContent:"center"},navIcon:{fontSize:22,color:"#a59d90",fontWeight:"900"},navActive:{color:"#c94736"},red:{fontSize:11,color:"#c94736"},green:{color:"#315e4d",fontWeight:"800"},loading:{position:"absolute",top:0,bottom:82,left:0,right:0,alignItems:"center",justifyContent:"center",backgroundColor:"#ffffff88"},quiz:{flex:1,backgroundColor:"#f8f3ea"},quizHead:{height:65,paddingHorizontal:20,flexDirection:"row",justifyContent:"space-between",alignItems:"center"},close:{fontSize:30},quizBody:{padding:22},question:{fontSize:31,fontWeight:"900",color:"#17382e",marginVertical:25},answer:{minHeight:58,backgroundColor:"#fff",borderRadius:15,padding:14,marginBottom:12,flexDirection:"row",alignItems:"center"},answerLetter:{width:32,height:32,textAlign:"center",paddingTop:6,borderRadius:16,backgroundColor:"#e9e1d4",fontWeight:"800"},answerText:{fontSize:16,fontWeight:"700",marginLeft:13,flex:1},result:{flex:1,alignItems:"center",justifyContent:"center",padding:30},stars:{fontSize:30,color:"#d5aa2e",margin:18},
});
