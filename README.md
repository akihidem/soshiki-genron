# 組織原論 / soshiki-genron

**人間の組織モデルを起点にせず、「AIにとって組織とは何か」をゼロから問い直す研究。**

私たちは AI のマルチエージェント協調を、無意識に *人間の組織*（チーム・役割・階層・管理者）から借りて設計してきた。だが人間組織の形は、人間という実行主体の限界（狭い通信帯域・忘れる記憶・高い専門家コスト・分散した動機）への**対処**である。AI でその限界の多くは緩む・逆転する。なら借りてきた構造の多くは最適でなく、**擬人的な負債**かもしれない。

このリポジトリは、その問いを主張で終わらせず、**機能から再導出 →（部分的に）実証**するための研究の土台である。

> 📄 **研究全体の論証は [`PAPER.md`](PAPER.md)** ── 問い・方法・機能からの再導出・7モデルの計測・実証（監督/レース/構造/市場3レジーム/Goodhart）・市場支配定理 p\*=w/s・実測較正・AI-2027・限界を一本に束ねた consolidation（まずこれを読めば全体が掴める）。🗺️ 1枚の全体像は [`docs/overview.html`](docs/overview.html):

![全体像：問い→方法→再導出→6モデル計測→実証較正→統合・テーゼ](docs/overview.png)

> **第一原理: モデルと実験による科学的計測。** 測れない主張は採らない —— 概念(③)も理論接続(①)も、最終的に実験基盤(②)で*測れる仮説*へ還元する。関連文献も継続調査し、再利用できる形式モデルと先行計測を取り込む（[`docs/literature.md`](docs/literature.md)）。

> ⚠️ これは `tehai`（別の private な姉妹リポ・管理された委譲層 / 人間組織体系を参考に実装）の続きではない。tehai は、この問いを生んだ**一つの実装例・一つのデータ点**にすぎない。本研究は tehai を起点にせず、組織そのものから問い直す。tehai の A/B 実測は参考証拠として引く（数値は本リポ内に転記）。

## ロードマップ ③ → ① → ②

| 段 | 何を | 状態 |
|---|---|---|
| **③ 概念の問い直し** | 「組織」を機能に分解し、各機能の人間版が*なぜその形か（拘束）*を辿り、AIで拘束が成立するかを問う。AIネイティブな形を導く。 | **着手中** → [`docs/foundations.md`](docs/foundations.md) |
| **① 転移マッピング** | ③ を既存の組織論（Coase / Mintzberg / Galbraith / March&Simon / Williamson…）に接続し、体系化。組織論＝人間の限界の科学を AI 用に再導出。 | 並行予定 → [`docs/references.md`](docs/references.md) |
| **② 実験基盤** | 何も前提しない「組織構造 × 課題類型 × 指標」の実験プラットフォーム。③①の主張を反証可能にする。 | 最終目標 |

方法論は [`docs/method.md`](docs/method.md)。**機能から始め、構造から始めない**（構造から始めると人間組織を密輸する）。

## 暫定テーゼ（③ の現時点の到達点・反証歓迎）

> AIネイティブの「組織」はたぶん**組織ではない**。型付き・証拠付き・記憶共有のデータフロー＋オンデマンドのエージェント生成、その上に**薄い人間統治膜**。「チーム/役割/階層」はその人間可読な投影にすぎない。

中心的緊張は **最適性（AIネイティブ・流動・検証中心）vs 可読性（人間が統治・主権を保てる）**。

## 最初の計測（②の胚）— 通信コストと最適構造

![最初の二つの計測：相図（通信コスト→構造）と統治膜曲線（stakes→膜の厚み）](docs/measurements.png)

第一原理を最初に具体化: 「**通信コスト c_comm が下がると、コスト最小の調整構造は階層→平ら→市場へ動くか**」(F3＋Malone)を決定的モデルで計測。
- **flat↔hierarchy 交差点 c_comm\* ≈ 1.12** — これより通信が高コストなら階層、安いと平らが勝つ。c_comm を下げると勝者は **hierarchy → market → flat**（密度依存）。
- **管理者OHが大きいほど階層の領域は狭い**（感度分析）。検証軸を中立化しても交差点は残る（純調整コスト由来と盲点流出由来を分離）。
- tehai の A/B（実コードの2点観測）と**独立の経路**で同じ向き（通信が安いと平ら有利）を再現 —— 弱い相互裏取り。
- 詳細: [`docs/first-measurement.md`](docs/first-measurement.md)（解釈）／[`model/RESULTS.md`](model/RESULTS.md)（生数値・再生成）。

### 第二の計測 — 統治膜の最適な厚み（最適性 vs 可読性）
研究の**中心的緊張**(F8/§5)を計測: 人間可読な統治膜の厚み m∈[0,1] に最適値はあるか。
- **内点最適が存在**（既定 m\*≈0.73）— 膜ゼロでも全面でもなく**部分的な膜**が最小損失。
- **stakes がしきい値を決める**: stakes<1.11 で m\*=0（純効率最適）／>22.3 で m\*=1（全面膜）／間は対数的に厚くなる。監督が効くほど薄い膜で足りる。
- = §5「膜が厚すぎれば擬人的負債・薄すぎれば主権喪失」を**しきい値**として測った。falsifier（任意 stakes で m\*=0）は**偽にならず** §5 を条件付き支持。
- 詳細: [`docs/second-measurement.md`](docs/second-measurement.md)／[`model/GOVERNANCE.md`](model/GOVERNANCE.md)。

### 第三の計測 — 容量制約と分解粒度（F1）
**エージェント容量 κ が上がると最適な分解粒度 g\* はどう動くか**（限定合理性）。
- **容量が高いほど分解は粗い**: g\* = 50→20→10→5→2→1（κ=2→100）。**AI＝高容量 → 粗い分解**（「人の職サイズ」は AI の自然単位でない）。通信が高いと過負荷を許容してでもさらに粗く。
- AI 域（高 κ・低 c_comm）は正味**粗い分解 → 片が少なく調整辺も少ない → flat を後押し**（第一の計測 F3 と接続）。
- 詳細: [`model/CAPACITY.md`](model/CAPACITY.md)。

### 合成 — 処方マップ
3つの計測を合成し、タスク profile（通信域・stakes）→ 推奨（構造・統治膜）を返す → [`model/DESIGN_MAP.md`](model/DESIGN_MAP.md)。

### レース外部性（AI-2027 が動機）— 競争は統治膜を安全最適より薄くするか
統治膜の単独最適に**多者レース**を足す。各 actor の Nash 均衡膜 m_eq と社会最適 m\* の差を測る。
- **m_eq ＜ m\***（既定 0.21＜0.84・**gap=0.63**）＝安全の race-to-the-bottom を反証可能に確認。
- **レース強度（prize）↑で m_eq→0・gap 拡大** ＝ AI-2027 の **Race ending**。破局を内部化すれば m_eq→m\*（Slowdown）。
- 単独組織の統治膜計測が見落としていた量。詳細: [`docs/ai-2027.md`](docs/ai-2027.md)（本研究との関係）／[`model/RACE.md`](model/RACE.md)。

### 実証: 監督スケーリング（②を実モデルへ接地）
統治膜の `oversight_error` を実エージェントで接地する最初の実証（`experiments/oversight/`）。弱い監督 gemma4:e2b vs 強い gemma4:latest に巧妙さ別の仕込み欠陥をレビューさせた。
- **結果は予想外**: 両者とも全欠陥を FLAWED と判定（仮説＝弱い監督は見逃す、は**再現せず**）。むしろ**強い監督ほど誤検出が多い**（FP 0.33 vs 0.0）＝失敗モードは見逃し(recall)でなく**過剰flag(precision)**。
- **フロンティア勾配**（gemma4:e2b→haiku→sonnet→opus・claude は無料枠 `claude-cli-run.py` 経由）でも **recall は天井**（弱い e2b だけ subtle で 0.667）／**precision は能力とともに悪化**（FP haiku 0→opus 0.33・2実験で再現）。失敗モードは見逃しでなく**過剰flag**。
- **recall crux も実測**: opus が*自分の水準で*生成した巧妙欠陥（subtlety3×6）に対し、**最弱 e2b は半分見逃す（oversight_error=0.5）**／haiku 以上は全部捕捉。＝「十分に弱い監督は強いモデルの巧妙な誤りを見逃す」を実測（ただし崩壊→1 には超人 producer が要り未到達）。
- **B 実装済み**: precision 失敗モードを `governance.py` に項として還流。over-flag 率↑で最適膜は薄くなり、**実測の opus 率 0.33 では m\*=0（膜が消える）**＝強い監督ほど厚い膜が良いとは限らない。詳細: [`docs/oversight-pilot.md`](docs/oversight-pilot.md)。

### 実証: 構造 F3 — flat vs hierarchy vs market（解析の構造軸を実エージェントで接地）
実 LLM（sonnet）に相互依存タスク（設計→実装→テスト）を3構造で組織させ、コスト（コール数）・静的品質・**正しさ（sandbox 実行）** を測った（`experiments/org_sim.py`）。
- コスト flat3<market4<hierarchy5（構造的）／静的品質は全構造 1.0＝**弁別不能**／実行正しさは高く（0.89–1.0）**コストに比例しない** ＝ flat は hierarchy の 60%コストで同等品質。
- 正しさハーネスは **3交絡を潰して初めて** 真の正しさを測れた（pytest形式→shim・多ファイルimport→drop・main()削除の宙ぶらりblock→pass化）＝measurement-first（§9）。

### 市場という組織軸 — 「市場型組織」の価値は能力差に条件付き（3レジーム＋閾値定理）
「市場（競売）型の配分は単一モデルより良いか」を3レジームで実証し、解析で統一した。
- **① 均質（全 sonnet）→ market 最下位**（活かす能力差なし）／**② frontier 異種（haiku/sonnet/opus）→ 勾配ゼロ（全員満点）→ market = flat-haiku**（利得なし）／**③ 大能力差（gemma 2–8B × frontier）→ market が Pareto 支配**（flat-haiku の半額・flat-opus の 1/28 コストで同正しさ）。
- 機構＝**検証ルーティング型エスカレーション**: 安いモデルで試し、外部 gold で落ちた所だけ上位へ。配分は自己申告でなく *実行検証*（外部錨）。
- **支配定理**（`model/market.py`）: market が単一モデルを Pareto 支配 ⟺ **p > w/s**（安いティアの完全解率 > コスト比）。実測③（market 0.311）と解析が厳密一致。trials=3 較正で p=0.889（gap の "leap 失敗" はノイズと判明）・3ローカルモデルの支配地図も実測（`--map`）。
- → **「AIにとって組織とは何か」への答え: 能力が均質なら flat、能力差があれば *検証ルーティング市場*（＝flat＋検証＋オンデマンド agent の最適な呼び出し方）**。詳細: [`experiments/MARKET_GAP.md`](experiments/MARKET_GAP.md)／[`model/MARKET.md`](model/MARKET.md)。

### 実証: レース・Goodhart・通信コスト較正
- **レース**（`experiments/race_game.py`）: LLM を競争主体に見立て安全水準 S を選ばせた。**中立フレーミングで liability が効く**（賠償責任で S 0.3→0.73 回復）＝race.py を実エージェントで支持。AI安全フレーミングは交絡し de-confound が前の結論（mandate≫liability）を**修正**した。
- **Goodhart**（`experiments/goodhart.py`）: proxy（可視テスト）最適化が真の正しさを下げるか。**損 0.217・難タスク集中**（roman 0.6/wildcard 0.7）＝alignment.py の Goodhart 項を実証。圧スイープでは **指数は同定不可・効果は閾値的**（frontier は明示「ハードコード可」まで overfit しない・§9-8）。
- **通信コスト較正**（`experiments/calibrate_coord.py`）: org_sim から **mgr_overhead = hierarchy−flat = 2コール（coordination.py 既定 2.0 と厳密一致）／c_comm（コール単位）≈0 → flat 勝ち** を接地。

### 多モデルの組み合わせ — 安く/確実に迫るが、「超える」のは能力の縁でだけ
原点の問い「複数 AI モデルの組み合わせは単一モデルを*超え*られるか」を実証（`market_external.py` の各モード・**Claude＋local gemma＋OpenAI codex** の異種ベンダ）。
- **escalation 市場** → 最良モデルの水準を*安く*（能力差があれば・超えはしない）／**best-of-N＋検証器** → 弱モデルの*信頼性*を強に近づける（*欠落能力*は作れず・安くもない）。
- **異種ベンダ（opus × codex）** → 全 checkable タスクで完全一致＝union 利得なし。見かけの「codex が opus を救う」は **opus の agentic harness artifact**（「既存ファイルを検証する」と散文だけ返す）だった → `gen_impl` 反agentic化で抑止（§9-9）。
- **創発の源泉＝誤りの脱相関**: frontier は LeetCode-hard でも誤らず脱相関ゼロ。だが**弱い所では実在**（negabinary で gemma が haiku の盲点を覆う）。→ **cross-vendor mesh は「能力の縁」の組織形態** ── 単一モデルが信頼できなくなる所でだけ点火し、仕事が縁へ動くほど価値が上がる。詳細: [`PAPER.md`](PAPER.md) §5。

## 走らせ方
```bash
python3 -m model.sweep         # ① 通信コスト→構造        → model/RESULTS.md
python3 -m model.governance    # ② stakes→統治膜の厚み      → model/GOVERNANCE.md
python3 -m model.capacity      # ③ 容量→分解粒度            → model/CAPACITY.md
python3 -m model.design_map    # 合成: タスク条件→推奨設計   → model/DESIGN_MAP.md
python3 -m model.joint         # 結合: 構造×膜（分離可能性の反証） → model/JOINT.md
python3 -m model.race          # レース外部性（AI-2027 動機）      → model/RACE.md
python3 -m model.alignment     # F7 整合（仕様+検証が能力を上限）   → model/ALIGNMENT.md
python3 -m model.market        # 市場支配定理 p*=w/s（3レジーム統一） → model/MARKET.md
python3 -m experiments.oversight.calibrate   # 実測較正: 測った oversight_error を両モデルへ → CALIBRATION.md
python3 -m experiments.oversight.run         # 実証: 監督スケーリング（mock即時／--backend ollama で実測）
python3 -m experiments.org_sim --agent claude:sonnet --tasks 3   # 実証: 構造 F3（flat/hierarchy/market・正しさ）
python3 -m experiments.market_external --gap --agent claude:real # 実証: 大能力差で market が Pareto 支配（gemma×frontier）
python3 -m experiments.market_external --ladder --agent claude:real  # 異種ベンダ難易度ラダー（gemma/haiku/sonnet/opus/codex）
python3 -m experiments.market_external --ensemble --agent claude:real # 弱 best-of-N が検証器付きで強に迫るか
python3 -m experiments.market_external --decorr --agent claude:real   # mesh 概念実証: 弱モデルの誤りは脱相関するか
python3 -m experiments.market_external --openended --agent claude:real # open-ended: cross-vendor 合成は単独を超えるか（LLM-judge）
python3 -m experiments.goodhart --agent claude:sonnet            # 実証: Goodhart（proxy 最適化 vs 真の正しさ）
python3 -m experiments.race_game --players claude:haiku,claude:sonnet --framing neutral  # 実証: レース外部性
python3 -m experiments.calibrate_coord       # 較正: 通信コスト（org_sim → mgr_overhead/c_comm）
python3 -m unittest discover -s tests -t .   # テスト（95本・決定的mock・全green）
```

## リポジトリ地図
- `docs/method.md` — 方法論（第一原理＝計測・機能優先・拘束系譜・反擬人化の番人・合否基準）
- `docs/foundations.md` — ③ 本体（最小定義・原始機能 F1–F8・拘束系譜・2つのフロンティア・テーゼ）
- `docs/references.md` — ① の背骨（組織論の正典と「AI再導出の問い」）
- `docs/literature.md` — 文献調査アジェンダ（形式モデル・計算組織論・MAS・近年LLM＝要一次確認）
- `docs/first-measurement.md` / `docs/second-measurement.md` — 計測の解釈・位置づけ
- `docs/ai-2027.md` — AI-2027（実存リスクのシナリオ予測）と本研究の対応・レース計測の動機
- `model/` — ② の胚: `coordination.py`+`sweep.py`（構造）／`governance.py`（統治膜）／`capacity.py`（分解粒度）／`design_map.py`（合成）／`joint.py`（構造×膜の結合）／`race.py`（レース外部性）／`alignment.py`（F7 整合）／`market.py`（市場支配定理 p\*=w/s）＋生成 `*.md`
- `experiments/oversight/` — 監督スケーリング実証＋ `calibrate.py`（測定値を governance/alignment へ還す実測較正）／`docs/oversight-pilot.md`
- `experiments/` — 実証ハーネス群: `org_sim.py`（構造 F3・sandbox 正しさ）／`race_game.py`（レース外部性・2フレーミング）／`market_external.py`（市場3レジーム・外部 gold・**異種ベンダ**＝Claude/gemma/**codex**・`--gap`/`--ladder`/`--ensemble`/`--decorr`/`--novel`/`--openended`/`--map`/`--calibrate`）／`goodhart.py`（code-overfitting・`--curve`）／`calibrate_coord.py`（通信コスト較正）＋生成 `*.md`
- `tests/` — 決定的テスト（95本・全 mock・green）

## 到達点（2026-06-21 着手〜）
- **③ 概念**: 最小定義 + 原始機能 F1–F8 + 拘束系譜 + 2フロンティア（整合の変質 / 統治の残存）+ テーゼ。
- **第一原理**: モデルと実験による計測を最上位規則化。各主張に反証手段を併記。
- **① 文献**: 3件を二次確認・記録（Marschak&Radner チーム理論 / Malone 電子市場 / Carley 計算組織論）。
- **② 解析モデル 7本**: 通信コスト→構造（交差点≈1.12）／stakes→統治膜（内点最適）／容量→分解粒度／処方マップ／構造×膜の結合／レース外部性＋制度内部化／F7 整合（Goodhart）／**市場支配定理 p\*=w/s**。
- **② 実証 6軸**（実 LLM・無料枠＋local gemma）: 監督スケーリング（recall/precision 接地）／レース（中立で liability 有効）／構造 F3（flat 安く同等品質）／**市場3レジーム（能力差で market が Pareto 支配）**／Goodhart（損 0.217・指数は閾値的で同定不可）。決定的部分 **95 tests green**。
- **実測較正**: oversight_error・過剰flag・mgr_overhead（=2コール）・市場閾値 p（trials=3）・spec_quality（0.57–0.78）を実エージェントで接地。
- **方法論**: 計測過程で結論が3度自己修正＋8つの転移可能な教訓（n=1/フレーミング/harness 交絡/自己評価のモデル依存/外部基準の誤り/係数の非同定性…）＝measurement-first が外部錨として機能（PAPER §9）。

## 次の計測（ranked・externally recorded）
1. **能力差の連続スイープ** — 市場が前線を支配し始める能力差の閾値を、より弱いモデル/難タスクで境界(p≈w/s)に寄せて実測。
2. **統計強化** — trials>1 を全実証へ（n=1 ノイズの分離・cold-start artifact 対策）。
3. **一次精読** — 3文献の本文で cost 係数を正当化／反証（Carley の実験データ較正含む）。

> 計測済み: 容量制約 F1（[`model/CAPACITY.md`](model/CAPACITY.md)）／人間の誤判定（`oversight_error` 軸）／軸の相互作用（[`model/JOINT.md`](model/JOINT.md)・分離可能性は高 stakes で破れる）／**レース外部性**（[`model/RACE.md`](model/RACE.md)）／**F7 整合**（[`model/ALIGNMENT.md`](model/ALIGNMENT.md)・仕様+検証が能力 p\* を上限づけ・超えると Goodhart）／**制度内部化**（[`model/RACE.md`](model/RACE.md)・race gap を賠償責任λ=0.25で82%・規制標準・共有検証で回復＝Race↔Slowdown の定量分岐）／**実測較正**（測った oversight_error 0〜0.5・過剰flag 0.33 を governance/alignment に還元 → 大能力差で膜 0.73→0.50、過剰flag で m\*=0、安全な能力 p\* 2.05→1.61）。

> **実証着手**（解析→実測）: 監督スケーリングの第一パイロット（[`docs/oversight-pilot.md`](docs/oversight-pilot.md)）は仮説を**否定**＝oversight_error はまだ未接地。失敗モードは recall でなく precision の可能性。measurement-first が機能。

> tehai とは別リポ・別系譜・PUBLIC。次の一手は上記の**どれを深めるかの選択**（研究方向の分岐）。
