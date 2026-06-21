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
- **レースの実証 → de-confound**（`experiments/race_game.py`・2フレーミング）: LLM を競争主体に見立て安全/管理水準 S を選ばせた。**AI安全フレーミングは交絡していた**（haiku/sonnet が「安全を下げさせる罠」と*拒否*・sonnet は harness の sentinel まで injection とフラグ・opus は winner-only liability を弱いと推論）。**中立フレーミング（工場×排出規制＝同じ外部性ゲーム・拒否ゼロ・全員プレイ）で測り直すと景色が変わった**: baseline **0.3**（race-to-bottom 再現）／**liability 0.73（強く回復！）**／mandate **0.7**。中立では agents が「全額 cleanup コストが prize を上回る→規制水準を上げる」と推論し、**liability が効く＝解析モデル（liability 効率的）を支持**。→ **前の「mandate≫liability」は安全フレーミングの産物**だった。**頑健な所見**: ①race-to-bottom は両フレーミングで再現／②**mandate は両方で効く**（選択を消すからフレーミング非依存）／③**liability はフレーミング感応**（中立で効く・安全で不安定）。**メタ所見: LLM の制度反応はフレーミング感応** ── 単一フレーミングで AI の制度行動を読むのは危険（de-confound が前の結論を*正した* ── measurement-first の核心）。
- **構造の実証（F3・最大の gap → 深堀: 市場構造・3タスク・実行による正しさ）**（`experiments/org_sim.py`）: 実 LLM エージェント（sonnet）に相互依存タスク（設計→実装→テスト）を **flat（共有黒板・3コール）／hierarchy（管理者が分解・割当・統合・5コール）／market（分散入札・4コール）** の3構造で組織させ、**コスト（コール数）・静的品質（coverage）・正しさ（sandbox 実行＝生成テストを unshare 隔離で実走させた通過率）**を3タスクで測った。クリーン結果（全9セル実走）: コスト **flat3<market4<hierarchy5**（構造的）／**静的品質は全構造 1.0＝弁別不能（盲目）**／**実行正しさ hierarchy 1.0 ≧ flat 0.963 ≧ market 0.889**。読み: **正しさはどの構造でも高く（0.89–1.0）コストに比例しない** ── hierarchy の +67%コールは +0.04 しか買わず、market の +33%コールはむしろ −0.07（均質組織では入札OHが heterogeneity の便益なしに乗る＝解析の予測通り market 最下位）。→ **flat は hierarchy の 60%コストで 96%の正しさ＝「安いが品質はほぼ同等」を実エージェントで支持**（tehai A/B・解析 F3 と整合）。**ただし正しさ差は n=3・trials=1 の単発セル2件（textutil で flat 16/18・market 2/3）に依存＝示唆的・非有意**。頑健なのは①コスト順位②静的品質の盲目性③正しさがコスト非依存で高いこと。**この深堀の最大の収穫は計測規律そのもの**: 正しさハーネスは**3交絡を潰して初めて**正しさを測れた（pytest形式→shim／多ファイル import→local drop／main()削除の宙ぶらり block→pass化）。素の初回（hierarchy 0/3 実走不能）を鵜呑みにすれば「hierarchy はコードを壊す」と**真逆の結論**になった（§9-4）。→ 実証は F8（監督）だけだった → **構造軸 F3 も実証・深堀**。
- claude 監督・プレイヤー・worker は無料枠（`claude-cli-run.py`＝対話TUI）経由。決定的部分は **73 tests 緑**。

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
- ② は解析モデル＋実エージェント実証（監督 F8・レース・**組織シミュレータ＝3構造×3タスク×実行正しさ**）。シミュレータは*最小実装*（flat=黒板逐次／hierarchy=管理者2コール／market=入札1コール）・n=3 trials=1 で、**完全なエージェント組織シミュレータの第一歩**（正しさ差は非有意）。
- テーゼ「組織でない」は*論証＋部分計測*であって証明ではない。

## 9. 方法論的教訓（AIエージェント/組織を*測る*とき）
実証の過程で結論が**3度自己修正**された。その修正自体が、AIの組織・制度行動を計測する上での転移可能な教訓:
1. **n=1 は信用しない** — 「opus がレースした」は n=1 では綺麗な物語に見えたが、複製（trials=3）で「能力単調」は崩れた（opus は一貫してレースするが、それだけ）。striking な単発は要複製。
2. **フレーミング交絡 → 中立フレーミングで de-confound** — 同じ外部性ゲームでも「AI安全」と枠付けると LLM は*拒否*し別のリスク推論をする（liability 弱く見えた）。中立フレーミング（工場×排出）にすると拒否ゼロ・liability が効いた。**単一フレーミングで AI の制度行動を読むのは危険**。
3. **harness を被験モデルに透明化** — claude-cli-run.py の完了 sentinel が漏れ、sonnet が prompt injection としてフラグ＝交絡。`--no-sentinel` で除去。
4. **検証 vs 生成のメトリクス** — 監督実証で「FLAWED と言う」だけを捕捉とすると FLAWED-bias で水増し。**欠陥の*同定一致***で測り直して初めて識別力が出た。
5. **異常値は被験者でなく*測定器*を疑う** — 組織シミュレータの正しさ計測で初回 hierarchy が 0/3 実走不能＝「階層はコードを壊す」に見えた。実際は被験モデルでなく*ハーネス*の交絡（pytest形式・多ファイルimport・main()削除の宙ぶらりblock）で、3つ潰すと hierarchy は実は正しさ 1.0。**素の異常を所見と決めつければ真逆の結論を出す**。対策: 生成物を保存（`org_sim_artifacts.json`）し盲目的再実行なしに診断、`--remeasure` でハーネス修正を*LLM再実行ゼロ*で全セルへ再適用。
> 一般教訓: AIネイティブな組織・制度行動の実証は、**安全訓練・フレーミング・harness 産物・測定器の交絡**に晒される。単発/単一フレーミング/素の異常値は誤導する。本研究が3度自己修正したのは、measurement-first（測定という外部錨）が効いた証拠。

## 10. 寄与と次
- **寄与**: 「AIにとって組織とは何か」を構造でなく機能から再導出し、各主張を反証可能な計測に落とし、中心パラメタを実測較正し、制度的 countermeasure を実証した、再現可能な公開研究。**組織論の AI 版の最初の骨格＋その測り方の教訓**。
- **次（大きな新フェーズ）**: 組織シミュレータの*統計強化*（trials>1・タスク多様化・**異種能力の market**＝heterogeneity を入れて初めて market が flat を超えるかを検定）／他係数の実測較正（通信コスト・Goodhart の code-overfitting）／フレーミング感応自体の一般化測定／F7 整合の形式の精緻化。組織シミュレータは3構造×実行正しさまで接地済み（最小実装・n=3）。

---
*soshiki-genron · github.com/akihidem/soshiki-genron (public) · 2026-06-21 着手・初日。全モデル/実証/較正は repo 内で再現可能。*
