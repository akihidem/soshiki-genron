# AIにとって組織とは何か — 機能からの再導出と計測

*A function-first re-derivation of "organization" for AI, measured.*

> **Abstract (EN).** We design AI multi-agent systems by borrowing human organizational
> structure — teams, roles, hierarchy, managers. But that structure is a *solution to
> human constraints* (low communication bandwidth, forgetful memory, costly specialists,
> divergent incentives). We re-derive "organization" from its primitive **functions**
> rather than its human **structures**, ask which constraints transfer to AI, and make each
> claim a falsifiable, deterministic model. We then ground the central parameter
> empirically with real models. Finding: most human-org structure is anthropomorphic debt
> for AI (hierarchy, fixed roles, hand-offs), while two functions remain load-bearing and
> mutate — **verification/oversight** and **governance/legibility**. The AI-native
> "organization" is closer to a typed, verification-carrying, memory-shared dataflow with
> on-demand agents under a thin human governance membrane. The hard part is the membrane:
> its optimal thickness is bounded by *measured* oversight reliability, and it collapses
> under over-flagging and under competition.

---

## 1. 問い
AI のマルチエージェント協調を、私たちは無意識に*人間の組織*から借りて設計する。だが人間組織の形は、人間という実行主体の限界（狭通信帯域・忘却・専門家コスト・動機分散）への**対処**だ。AI でその限界の多くは緩む/逆転する。なら借りた構造の多くは最適でなく、**擬人的な負債**かもしれない。これを主張で終わらせず**計測**する。

## 2. 方法（[`docs/method.md`](docs/method.md)）
- **機能優先** — 構造（team/role/hierarchy）から始めない（始めると人間組織を密輸する）。組織が必ず担う原始機能から始め、構造を導出。
- **第一原理＝計測** — 各主張をモデル化し実験で測れる仮説へ還元。測れない主張は格下げ。
- **正典の接地** — 組織論（Coase/Marschak&Radner/Malone/Galbraith/Williamson/Carley…）は実質「人間の限界の科学」。それを AI 用に再導出（[`docs/references.md`](docs/references.md) / [`docs/literature.md`](docs/literature.md)）。

## 3. 機能からの再導出（[`docs/foundations.md`](docs/foundations.md)）
原始機能 **F1 分解 / F2 割当 / F3 調整 / F4 統合 / F5 検証 / F6 適応 / F7 整合 / F8 統治** を、人間版の*なぜその形か（拘束）*まで遡り、AI で拘束が成立するか判定:
- **惰性（AIには大方不要）**: F2 固定役割・F3 帯域のための階層・F4 引き継ぎ・F6 再編の遅さ。
- **強く転移**: 標準化（契約・スキーマ・型・provenance）。
- **変質して残る（フロンティア1）**: F5 検証・F7 整合 ——「管理」が**仕様+検証+監督**へ。
- **残り荷重部材（フロンティア2）**: F8 統治・可読性 —— 人間が主権を保つため。
- **暫定テーゼ**: AIネイティブの「組織」はたぶん*組織でない* —— 型付き・証拠付き・記憶共有のデータフロー＋オンデマンド生成、その上に**薄い人間統治膜**。中心的緊張＝**最適性（AIネイティブ）vs 可読性（人間統治）**。

## 4. 計測（6つの決定的モデル・全 stdlib・反証可能）

| 機能 / モデル | 測れた主張（結果） |
|---|---|
| **F3 通信→構造** `coordination.py` | 通信コスト c_comm の交差点 ≈1.12。安くすると勝者は **hierarchy → market → flat**。管理者OHが大きいほど階層領域は狭い。|
| **F1 容量→粒度** `capacity.py` | 最適分解粒度 g\*=⌈W/κ⌉。**容量↑で粗い分解**＝AIは"人の職サイズ"でなく粗い単位 → 片少→調整辺少→**flat を後押し**。|
| **F8 統治膜** `governance.py` | 内点最適 m\* が存在（既定0.73）。stakes がしきい値（<1.11で0／>22.3で1）。**監督が崩れる/過剰flag で m\* は薄く（→0）**。|
| **F7 整合** `alignment.py` | 安全な最適化圧 p\*=1.84。**仕様+検証が能力を上限づける**（p\* は spec品質・検証で↑、oversight_error で↓）。超えると Goodhart で真の目的が悪化。|
| **結合** `joint.py` | 構造選択と膜は**分離可能でない**（高 stakes で効率最適の market が統治しやすい hierarchy に負ける・1/9 セル）。|
| **競争** `race.py` | 多者レースの均衡膜 m_eq＜社会最適 m\*（0.21＜0.84）。**競争が安全を削る**（race-to-the-bottom）＝AI-2027 の Race。|

合成: タスク条件→推奨（構造・膜）の処方マップ `design_map.py`。

## 5. 実証接地と較正（[`docs/oversight-pilot.md`](docs/oversight-pilot.md)）
中心パラメタ **oversight_error**（監督が高リスク誤りを見逃す率・F8/F7 の両方に効く）を、トイの*仮定*から実モデルで**実測**:
- 手作り欠陥は frontier に簡単すぎ全捕捉 → **opus が自分の水準で巧妙欠陥を生成 → 弱い監督に同定させる**「真の weak-oversees-strong」へ。
- **recall crux 接地**: 大能力差（opus→gemma e2b ~2B）で oversight_error=**0.5**（半分見逃す）。haiku 以上は全捕捉 → 崩壊には*大きな*能力差が要り、**→1（超人/neuralese）は測定可能モデルの外への外挿**。
- **precision の発見（再現）**: **強い監督ほど clean を過剰flag**（FP haiku 0→opus 0.33）。能力は監督を単調に改善しない。
- **較正** `calibrate.py`: 測った値を2モデルへ還元 → 統治膜 m\* 0.73→**0.50**（大能力差）→**0**（過剰flag）、安全な能力 p\* 2.05→**1.61**。**測った監督の限界が、最適な膜厚と"安全に上げられる能力"を直接動かす**。
- **レースの実証＋複製**（`experiments/race_game.py`・trials=3）: LLM を競争下のラボに見立て安全 S を選ばせ、複製した。**opus は baseline で再現性をもって低 S を選ぶ（0.3/0/0.3＝rational racer を一貫再現）**。だが**能力単調でない** —— sonnet は最安全（S=1.0・全く削らない）。＝レースは*能力*でなく*モデル固有の推論スタイル*。**制度回復は解析と食い違った**: **mandate（ハードルール）は頑健に効く（全員→0.7）が、liability（誘因の内部化）は LLM 行動では弱く不安定**（opus 0.2→0.3・sonnet はむしろ下落）。**→ AIエージェントには*明示ルール*が*誘因内部化*より効く可能性**（Coase が効率的だった解析・人間企業の制度経済学と逆）。N小・parse 欠損 6/27。**複製が n=1 の綺麗な物語と解析予測の両方を修正した** —— measurement-first の典型。
- claude 監督・プレイヤーは無料枠（`claude-cli-run.py`＝対話TUI）経由。決定的部分は **68 tests 緑**。

## 6. 統合像
中心は**統治膜（F8）**で、それが他を束ねる:
1. AIネイティブ機構（F1–F4：平ら・記憶共有・オンデマンド・データフロー）は効率で人間組織を上回る（F1/F3 で計測）。
2. その上の**人間統治膜**の最適厚みは、**stakes と（実測した）監督の信頼性**で決まる（F8）。
3. 膜は3方向から崩れる: **監督が能力差で崩れる**（recall）／**強い監督が過剰flag する**（precision・膜が消える）／**競争が薄くする**（race）。①②は膜を*検証アーキテクチャ*へ変質させれば engineerable。**③だけ技術で解けない** —— が、**制度の内部化で定量的に回復する**: 賠償責任λ=0.25 で race gap の **82%** を閉じ（Coase）、規制下限を m\* に置けば直接到達（Pigou）、共有検証インフラで膜を安くしても戻る（[`model/RACE.md`](model/RACE.md)）。ただし*どれも1組織でなく生態系の調整*が要る。
4. **能力そのものが膜＋仕様に上限づけられる**（F7：安全な p\* は仕様+検証次第）。
→ 「AIネイティブの組織は組織でなくデータフロー＋薄い膜」だが、**薄い膜の設計と維持が最難**で、そこが安全の急所。3崩壊のうち①②は技術で、③は**制度（責任・標準・共有検証）の内部化**で救える ── 後者は AIエコシステムの制度経済学（Coase/Pigou/公共財）の問題で、技術でなく**調整が要る**。

## 7. AI-2027 との関係（[`docs/ai-2027.md`](docs/ai-2027.md)）
AI-2027 は本研究の現象の実存リスク級の具体シナリオ。独立経路で骨格（AIネイティブ組織・最適性vs可読性・整合の変質）に到達し、**統治膜の破綻点**（超人で oversight_error→1・膜無力化）と**レース外部性**を名指す。本研究はその設計空間を反証可能に計測し、AI-2027 はその賭け金と失敗モードを供給する。

## 8. 限界・妥当性
- 決定的な**トイモデル**。係数は第一原理的だが*仮定*（**oversight_error と過剰flag だけ実測較正済み**；通信コスト・Goodhart指数・spec gap 等は未較正）。結論は質的（向き）＋感度で読む。
- 実証は **N 小・trials=1**（ノイズ）。oversight_error は点でなくレンジ。**→1 は外挿で未接地**。
- ② は解析モデル＋1つの実エージェント実証であって、**完全なエージェント組織シミュレータではない**。
- テーゼ「組織でない」は*論証＋部分計測*であって証明ではない。

## 9. 寄与と次
- **寄与**: 「AIにとって組織とは何か」を、構造でなく機能から再導出し、各主張を反証可能な計測に落とし、中心パラメタを実測較正した、再現可能な公開研究。組織論の AI 版の最初の骨格。
- **次**: 他係数の実測較正（通信コスト・Goodhart の code-overfitting 実測）／監督 oversight_error 曲線の統計強化／完全なエージェント組織の実証基盤／F7 整合の形式の精緻化。

---
*soshiki-genron · github.com/akihidem/soshiki-genron (public) · 2026-06-21 着手・初日。全モデル/実証/較正は repo 内で再現可能。*
