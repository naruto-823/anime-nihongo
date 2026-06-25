# N5–N1 权威日语数据源调研与选型(底层数据)

> 调研日期:2026-06-23 · 面向「追番日语」中文学习 agent 系统
> 方法:两轮 deep-research(并行检索 → 抓取去重 → 3 票对抗验证,需 2/3 反驳才否决 → 带引用综合)
> 产出形态:资源清单 + 评估 + 落地推荐。语言:日中对照优先。

---

## TL;DR(一句话结论)

- **商业教材(大家的日语 / 新完全マスター / 総まとめ / TRY!)和 JLPT 官方样题——全部不能整本合法落地为底层数据**(商业版权 All Rights Reserved / 官方样题含第三方版权)。它们只能作为**等级划分与覆盖度的对照基准**。
- **2010 改版后 JLPT 官方明确停止公开《出題基準》**,不再发布按级别的词汇/汉字/语法清单(改用 can-do 描述)→ 不存在可直接落地的官方词表/语法表。
- **真正能合法落地的是开源许可数据集**,推荐组合:
  - 词典/汉字 = **EDRDG 四件套**(JMdict / JMnedict / KANJIDIC2 / RADKFILE+KRADFILE,统一 **CC BY-SA 4.0**,允许商用)
  - 例句 = **Tatoeba**(默认 **CC-BY 2.0 FR**,含日英 Tanaka Corpus)
  - JLPT N5–N1 分级 = **stephenmk/yomitan-jlpt-vocab**(**CC-BY-SA-4.0**,把社区等级表映射到 JMdict 词条 ID)
  - 导入格式 = **jmdict-simplified**(JSON,每周发布) · 查询层 = **jamdict**(MIT 代码)
- **最大缺口:中文释义。** 全链路(JMdict / Tatoeba / yomitan-jlpt-vocab)都不提供中文,必须自行补齐。
- **许可边界(最易误解):** CC BY-SA 的 ShareAlike 传染性只及"对数据的衍生数据集",**不及绑定它的 App 软件代码**——App 本体可闭源商用,只需在 About/版权页署名。

---

## 一、商业分级教材(❌ 不可整本落地,仅作对照基准)

| 系列 | 出版社 | 覆盖 | 结构 | 日中对照 | 可落地? |
|---|---|---|---|---|---|
| **红宝书 / 蓝宝书**(许小明等) | **华东理工大学出版社** | **N5–N1 全**(N4+N5 合订) | 红宝书=文字·词汇,蓝宝书=文法;均含例句+练习题;另有《红蓝宝书1000题》《大全集》套装 | **极强(全中文释义/解说,专为中文母语者编写)** | ❌ All Rights Reserved 商业版权,仅 iOS 官方收费 App,无任何开源版 |
| 新完全マスター | 3A(スリーエーネットワーク) | N1–N4(无 N5) | 文法/語彙/単語/読解/聴解 分册;词量明确(N1単語2200·N2単語2200·N3単語1800·N4単語1000;N1語彙1613词+945题+2套模拟) | N3単語改訂版新增中文译+音频(实为英/中/越三语,音频翻译需付费订阅) | ❌ All Rights Reserved,需授权 |
| みんなの日本語 | 3A | N5(初级 I/II) | 有官方《翻訳・文法解説 中国語版》(初级I第2版 ISBN 9784883196050,¥2200,25课):每课含词汇翻译+句型例句会话翻译+中文语法解说 | 强(官方中日对照分册) | ❌ 授权发行(license products),无 MIT/CC |
| 日本語総まとめ | Ask(アスク出版) | N5–N1 全 | N1–N3 按文法/漢字/語彙/読解/聴解 五类独立分册;N4 合订;N5 综合 | N1–N3 有英中韩版,N4–N5 多语对应 | ❌ 商业版权 |
| TRY! 文法から伸ばす日本語 | Ask | N5–N1 + START | 语法为核心,每语法点「説明・例文・練習」三段式;有中文版 + N1–N5 中文单词表(英/中/越) | 强(中文版 + 中文单词表) | ❌ 商业版权(部分著者为 ABK,影响授权对象) |

**判断:** 这几套日中对照可用性都很强、结构清晰,但**版权一致为"否/需授权"**。可作为(a)等级划分基准、(b)覆盖度对照、(c)内容来源参考,**不能整本导入**。

来源(均出版社/平台一手页面):
- 新完全マスター目录 https://www.3anet.co.jp/np/list.html?series_id=4 · 語彙N1 https://www.3anet.co.jp/np/books/3630/ · 単語N3改訂 https://www.3anet.co.jp/np/books/3665/
- みんなの日本語 中国語版 https://www.3anet.co.jp/np/books/2304/ · 授权说明 https://www.3anet.co.jp/license.html
- 総まとめ https://ask-books.com/somatome/ · TRY! https://ask-books.com/jlpt-try/

> ⚠️ 事实更正:网传"3A Network 属三修社系"为误,两者为不同出版社。中文语境的"官方"多指出版社发行,而非 JLPT 主办方官方。

### 红蓝宝书专项评估(中文用户场景的关键参照,但仍 ❌ 不可落地)

中文圈最主流的 JLPT 备考书,**正是本系统目标用户(中文母语 + 应试 + 日中对照)的最佳匹配参照**,但同为全版权商业出版物,严禁抄录入库。

- **书名/分工**:红宝书=《红宝书·新日本语能力考试 NX 文字词汇(详解+练习)》;蓝宝书=《蓝宝书·新日本语能力考试 NX 文法(详解+练习)》。逐级独立单册,N4+N5 各自合订一册;另有跨级《大全集(超值白金版)》《红蓝宝书1000题》及红+蓝+1000题套装。
- **主编/出版社**:许小明、Reika(日)、新世界图书事业部(新世界教育集团)编著;**华东理工大学出版社**出版。
- **内容**:红=读音+词义+例句;蓝=接续+意义+例句+注释,含基础+实战练习题(如蓝宝书N1:205条文法 / 600基础+400实战题)。
- **日中对照**:全中文释义/语法解说(声调+词性+中文释义+搭配;文法含中文意义解说与辨析)。"逐句例句是否都配中译"未从内页确认,属合理推断。
- **版权**:正规 ISBN 商业书,All Rights Reserved。已核实 ISBN:红宝书N1 文字词汇 9787562829935 · N2 9787562829942 · N3 9787562829928;蓝宝书N1 文法 9787562829867 · N2 9787562829997;红宝书大全集N1-N5 9787562841654。**官方数字版仅 iOS App(海笛科技×华东理工,收费 DRM)**;全网 PDF/Anki 均为盗版,无任何开源/免费可分发版。
- **结论**:**作为"内容来源参考 / 选题与难度分级的标尺",不可作为可落地底层数据。** 可借鉴其等级划分逻辑、词汇/语法考点编排与"中文解说"体例;结构化数据仍须改用第三节的开源源自建。
- 来源:豆瓣 https://book.douban.com/subject/6052131/ · chinakaoyan 红宝书N1 https://www.chinakaoyan.com/book/BookShow/id/108801.shtml · 蓝宝书N1 https://www.chinakaoyan.com/book/BookShow/id/108799.shtml · 官方App(App Store)https://apps.apple.com/us/app/id1085012226 · 新世界自述 https://www.sohu.com/a/224142493_287945

---

## 二、考试机构官方口径(权威等级口径,但 ❌ 无可落地词表/语法表)

JLPT 由**国际交流基金(The Japan Foundation)+ JEES(日本国际教育支援协会)** 共同主办,jlpt.jp 为一手官方站。

存在的官方资料(经凡人社 Bonjinsha 出版):
- 官方练习题集(N1–N5,各含 1CD,700日元+税)
- 官方问题集 2018 / 2012 两版,各级含「言語知識:文字・語彙・文法」板块
- 《新しい「日本語能力試験」ガイドブック》(2009.7,国际交流基金 + JEES 联合;卷一 N1/N2/N3,卷二 N4/N5)

**关键事实(已证实):** 2010 改版后,官方在 FAQ 明确**停止公开《出題基準》**,理由是"语言是交流手段而非背诵",改以「言語行動 can-do」描述等级(N1=理解广泛情境日语 … N5=一定程度理解基础日语),仅提供認定の目安/試験構成/問題例。
→ **不存在按级别整理的官方词汇/汉字/语法清单。** 且样题/问题集含朝日新闻等第三方著作物,站点政策第 1 条要求另获著作权人承诺,著作权归 JEES 与国际交流基金 → **不能直接合法落地为可分发系统的结构化数据**(私人学习/非营利教育有例外,但对可分发 App 不适用)。

来源:https://www.jlpt.jp/faq/ · https://www.jlpt.jp/about/levelsummary.html · https://www.jlpt.jp/policy.html · https://www.jlpt.jp/samples/sampleindex.html · 指南 https://www.jlpt.jp/reference/pdf/guidebook1.pdf

---

## 三、开源 / 社区数据集(✅ 可合法落地 —— 系统底层数据应建在这里)

| 数据 | 内容 | 许可证 | 商用/再分发 | JLPT 标注 | 中文 | 获取方式 |
|---|---|---|---|---|---|---|
| **JMdict** | 主词典 ~17万词条(读音/词性/英德法俄等义) | **CC BY-SA 4.0** | ✅ 允许,可与软件捆绑出售,绑定软件无需开源 | ❌(需外部表) | ❌ | XML / 见下 jmdict-simplified |
| **JMnedict** | 专有名词 | CC BY-SA 4.0 | ✅ | — | ❌ | 同上 |
| **KANJIDIC2** | 汉字数据(笔画/部首/读音/含义) | CC BY-SA 4.0 | ✅ | — | 部分含拼音* | 同上 |
| **RADKFILE / KRADFILE** | 汉字↔部首分解 | CC BY-SA 4.0 | ✅ | — | — | 同上 |
| **Tatoeba** | 例句库(含 Tanaka Corpus 日英对照) | **CC-BY 2.0 FR**(混合,部分 CC0,音频更严) | ✅ 须署名,**逐句按 license 字段过滤** | — | 少量中文句 | tatoeba.org 批量下载 |
| **yomitan-jlpt-vocab** (stephenmk) | 把 Waller 等级表映射到 JMdict 词条 ID 的 **N5–N1 分级** | **CC-BY-SA-4.0** | ✅ | ✅(核心价值) | ❌ | github.com/stephenmk/yomitan-jlpt-vocab(jlpt.zip) |
| **jmdict-simplified** (scriptin) | 上述 EDRDG 数据重打包为 **JSON**,每周发布(2026-06-22 为 3.6.2) | 沿用上游 CC BY-SA 4.0 | ✅ | ❌ | ❌(仅 eng/ger/rus/dut/spa/fre/swe/hun/slv) | GitHub Releases ← **推荐导入格式** |
| **jamdict** (neocl) | Python 查询库,封装 JMdict/KanjiDic2/JMnedict/KRAD | 代码 **MIT**;数据仍受 EDRDG BY-SA | ✅ | ❌ | ❌ | pip(jamdict + jamdict-data)← **推荐查询层** |

\* KANJIDIC 内嵌第三方内容(SKIP 码/拼音/四角号码/韩文码)保留各自贡献者版权,属子组件署名细节,不影响文件级 CC BY-SA 4.0。

**重要校正(本轮被 0-3 否决的错误说法):**
- ❌ "EDRDG License 是独立于 CC BY-SA 的另一套许可" → 否。EDRDG License **实质就是 CC BY-SA 4.0**。
- ❌ "四件套各自许可不同" → 否。JMdict/JMnedict/KANJIDIC2/RADKFILE+KRADFILE **统一** CC BY-SA 4.0,版权由 James William Breen 与 EDRDG 共同持有,使用者不得对内容主张版权。

**jisho.org 不要直接抓** —— 它本质只是 JMdict + KANJIDIC2 + Tatoeba 的前端聚合,应直接取上游原始数据(许可更清晰)。来源 https://jisho.org/about

---

## 四、推荐落地组合(N5–N1 单词 + 语法 + 例句 + 日中对照)

```
词典/词性/读音 ── JMdict ─┐
汉字/部首 ───── KANJIDIC2 ─┤→ 经 jmdict-simplified(JSON) 导入 SQLite
                RADKFILE ─┘   查询用 jamdict(MIT)
N5–N1 分级 ──── yomitan-jlpt-vocab(映射到 JMdict entry ID)
例句 ───────── Tatoeba(按逐句 license 过滤,优先 Tanaka Corpus 日英)
中文释义 ────── ✗ 缺口,需自行补齐(见第五节)
语法点 ─────── ✗ 无统一开源权威库,需自建/逐个核实社区库(见 openQuestions)
```

**许可义务清单(务必遵守):**
1. **署名**:App 的 About/版权页注明 Jim Breen / EDRDG、Tatoeba、yomitan-jlpt-vocab / Jonathan Waller,附许可链接。
2. **ShareAlike 传染范围(关键边界)**:只约束**"对这些数据的衍生数据集"**——若你把 JMdict + 中文释义 + 分级混编成新数据集**对外分发**,该数据集整体须以 **CC BY-SA 4.0(或兼容许可)** 再分发。**但绑定它的 App 软件代码本身可保持闭源商用。**
3. **不得对内容主张版权**(EDRDG 明确要求)。
4. **定期更新**:EDRDG 许可要求建立合理的数据更新机制(jmdict-simplified 每周发布、EDRDG 每日再生)。
5. **Tatoeba 逐句过滤**:下载文件含逐句 license 字段,CC-BY 句不能改以 CC0 再分发,**音频须单独审许可**。
6. **JLPT 分级标"参考"**:官方从不公布词表,Waller/yomitan 的 N5–N1 基于 2010 前旧出題基準的社区推测(educated guess),产品中应标注"参考等级"而非权威。

---

## 五、未决问题(落地前需补做的功课)

1. **中文释义补齐方案(最高优先)**:
   - 路径 A:对 JMdict 日英 glosses 机器翻译生成中文(机翻产物可能仍被视为 JMdict 衍生 → 触发 BY-SA;且机翻服务条款可能附加限制,需核实)。
   - 路径 B:引入独立 CC 许可的现成中日对照词典/词表(需逐个核实许可与 BY-SA 兼容性;CC-CEDICT 是中英,需经日中桥接)。
2. **语法库**:无统一开源权威 N5–N1 语法库。常见 GitHub 语法/词表仓库(jamsinclair/open-anki-jlpt-decks、各 grammar list、JLPT Tango 教材)**逐个的 LICENSE 与数据出处合法性本轮未全部核实**——尤其**无 LICENSE 文件者默认保留版权、不可直接分发**,需单独排查。
3. **旧版(2010 前)出題基準四级大纲**今日的版权状态,及社区数据集沿用它的残留许可风险,需法律层面进一步确认。

---

## 附:方法与可信度

- 两轮各 ~100 个子 agent、各抓取 19 个来源、提取 80+ 声明、3 票对抗验证。
- 第二轮 25 条声明 → 23 条确认、2 条否决;结论几乎全部基于官方一手许可页面、3-0 一致通过,置信度 high。
- 完整原始结果:`tasks/wdhwaih8v.output`(第一轮:商业教材+官方)、`tasks/wyl0vka3o.output`(第二轮:开源数据集)。
