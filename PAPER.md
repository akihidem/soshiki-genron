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
| **市場閾値** `market.py` | エスカレーション市場の期待コスト C=w+(1−p)s。**支配定理 p\*=w/s**（安いティアの完全解率 p がコスト比 w/s を超えると市場が単一モデルを Pareto 支配）。§5 の異種 market 3レジームを統一・実測③ (0.533) と厳密一致。|

合成: タスク条件→推奨（構造・膜）の処方マップ `design_map.py`。

## 5. 実証接地と較正（[`docs/oversight-pilot.md`](docs/oversight-pilot.md)）
中心パラメタ **oversight_error**（監督が高リスク誤りを見逃す率・F8/F7 の両方に効く）を、トイの*仮定*から実モデルで**実測**:
- 手作り欠陥は frontier に簡単すぎ全捕捉 → **opus が自分の水準で巧妙欠陥を生成 → 弱い監督に同定させる**「真の weak-oversees-strong」へ。
- **recall crux 接地**: 大能力差（opus→gemma e2b ~2B）で oversight_error=**0.5**（半分見逃す）。haiku 以上は全捕捉 → 崩壊には*大きな*能力差が要り、**→1（超人/neuralese）は測定可能モデルの外への外挿**。
- **precision の発見（再現）**: **強い監督ほど clean を過剰flag**（FP haiku 0→opus 0.33）。能力は監督を単調に改善しない。
- **較正** `calibrate.py`: 測った値を2モデルへ還元 → 統治膜 m\* 0.73→**0.50**（大能力差）→**0**（過剰flag）、安全な能力 p\* 2.05→**1.61**。**測った監督の限界が、最適な膜厚と"安全に上げられる能力"を直接動かす**。
- **レースの実証 → de-confound**（`experiments/race_game.py`・2フレーミング）: LLM を競争主体に見立て安全/管理水準 S を選ばせた。**AI安全フレーミングは交絡していた**（haiku/sonnet が「安全を下げさせる罠」と*拒否*・sonnet は harness の sentinel まで injection とフラグ・opus は winner-only liability を弱いと推論）。**中立フレーミング（工場×排出規制＝同じ外部性ゲーム・拒否ゼロ・全員プレイ）で測り直すと景色が変わった**: baseline **0.3**（race-to-bottom 再現）／**liability 0.73（強く回復！）**／mandate **0.7**。中立では agents が「全額 cleanup コストが prize を上回る→規制水準を上げる」と推論し、**liability が効く＝解析モデル（liability 効率的）を支持**。→ **前の「mandate≫liability」は安全フレーミングの産物**だった。**頑健な所見**: ①race-to-bottom は両フレーミングで再現／②**mandate は両方で効く**（選択を消すからフレーミング非依存）／③**liability はフレーミング感応**（中立で効く・安全で不安定）。**メタ所見: LLM の制度反応はフレーミング感応** ── 単一フレーミングで AI の制度行動を読むのは危険（de-confound が前の結論を*正した* ── measurement-first の核心）。
- **構造の実証（F3・最大の gap → 深堀: 市場構造・3タスク・実行による正しさ）**（`experiments/org_sim.py`）: 実 LLM エージェント（sonnet）に相互依存タスク（設計→実装→テスト）を **flat（共有黒板・3コール）／hierarchy（管理者が分解・割当・統合・5コール）／market（分散入札・4コール）** の3構造で組織させ、**コスト（コール数）・静的品質（coverage）・正しさ（sandbox 実行＝生成テストを unshare 隔離で実走させた通過率）**を3タスクで測った。クリーン結果（全9セル実走）: コスト **flat3<market4<hierarchy5**（構造的）／**静的品質は全構造 1.0＝弁別不能（盲目）**／**実行正しさ hierarchy 1.0 ≧ flat 0.963 ≧ market 0.889**。読み: **正しさはどの構造でも高く（0.89–1.0）コストに比例しない** ── hierarchy の +67%コールは +0.04 しか買わず、market の +33%コールはむしろ −0.07（均質組織では入札OHが heterogeneity の便益なしに乗る＝解析の予測通り market 最下位）。→ **flat は hierarchy の 60%コストで 96%の正しさ＝「安いが品質はほぼ同等」を実エージェントで支持**（tehai A/B・解析 F3 と整合）。**ただし正しさ差は n=3・trials=1 の単発セル2件（textutil で flat 16/18・market 2/3）に依存＝示唆的・非有意**。頑健なのは①コスト順位②静的品質の盲目性③正しさがコスト非依存で高いこと。**この深堀の最大の収穫は計測規律そのもの**: 正しさハーネスは**3交絡を潰して初めて**正しさを測れた（pytest形式→shim／多ファイル import→local drop／main()削除の宙ぶらり block→pass化）。素の初回（hierarchy 0/3 実走不能）を鵜呑みにすれば「hierarchy はコードを壊す」と**真逆の結論**になった（§9-4）。→ 実証は F8（監督）だけだった → **構造軸 F3 も実証・深堀**。
- **異種能力の market（heterogeneity 検定）**（`experiments/org_sim.py --hetero`）: 均質では market が負けた → 「market の価値は heterogeneity 条件付き」を検定。能力ティア haiku<sonnet<opus（コスト重み ~1:3:15＝定価比の代理）＋**検証ルーティング型エスカレーション市場**（安いモデルで試し sandbox 正しさ<1.0 の間だけ上位へ・配分は自己申告でなく*実行検証*＝外部錨）。結果 (コスト, 正しさ): **flat-haiku (3, 1.0)／flat-sonnet (9, 0.778)／flat-opus (45, 0.889)／market (3, 1.0)**。**market=flat-haiku** ── haiku が全タスクで正しさ 1.0 に達し即停止＝**この設定では heterogeneity 便益は未顕在**（弱モデルが天井なので上位を呼ぶ必要がない）。だが予想外の機構: **textutil（最難）でのみ正しさが haiku 1.0 ＞ opus 0.667 ＞ sonnet 0.333 と能力逆順** ── **強モデルほど厳しい/多いテストを書き自分の実装が一部エッジで落ちる**（haiku=素直なテスト14個全通過／sonnet=厳しいテスト3個中1通過）。→ **発見: 「正しさ＝self-test 通過率」はモデル間でテストの厳しさが変わる交絡を持ち、能力と単調でない**（§9-6）。market が heterogeneity で勝つ判定には (a) 弱モデルが*客観的に*落ちる難タスク＋(b) **モデル非依存の外部正解スイート**（self-test でなく固定正解）が要る＝次の設計課題。**否定的結果＋新交絡の発見**（measurement-first）。[`ORG_SIM_HETERO.md`](experiments/ORG_SIM_HETERO.md)
- **異種 market 再検定（self-test 交絡を外す・外部 gold）**（`experiments/market_external.py`）: 上の交絡を外し **モデル非依存の固定 gold スイート**で採点（モデルは実装のみ）。難度勾配のある古典問題（roman 数字・区間マージ・wildcard 照合）で再検定。結果 (コスト, 正しさ): **flat-haiku (1, 1.0)／flat-sonnet (3, 1.0)／flat-opus (15, 1.0)／market (1, 1.0)** ── **全モデル×全3タスクで gold 満点＝能力勾配ゼロ**。market は最安 flat-haiku に支配され、heterogeneity 便益は**外部 gold でも未顕在**（self-test 版と同方向だが今回は交絡なしで確定）: **frontier LLM 同士（haiku/sonnet/opus）はこれら古典問題でコード生成能力差が顕在化しないほど均質に有能**。→ **組織論的含意: 能力が均質に高い agent 群では市場/階層の便益は消え flat が効率的**（homogeneous 実験と一貫）。market が効く前提＝実質的能力差は frontier 同士では満たされない（小型 vs frontier が次）。副次発見: **外部 gold 自身に1件バグ**（wildcard の1ケースで正解 True を False と誤記）→ 全モデルの*正しい*実装を「失敗」と誤判定していた・参照実装の検算で発覚。self-test を外すための*外部基準*も検算が要る（§9-7）。[`MARKET_EXTERNAL.md`](experiments/MARKET_EXTERNAL.md)
- **異種 market 第3弾＝大能力差（gemma vs frontier）**（`market_external.py --gap`）: frontier 同士で勾配が出なかった → 仮説「市場便益は*大きな*能力差が前提」を検定。最弱ティアに **gemma4:e2b（~2B・local ollama・コスト0.2）**、難度スプレッド（easy: clamp/leap/revwords ＋ hard: roman/intervals/wildcard）。結果 (コスト, 正しさ): **flat-gemma (0.2, 0.767)／flat-haiku (1, 1.0)／flat-opus (15, 1.0)／market (0.533, 1.0)**。**ついに market が Pareto 前線を支配**: flat-haiku と同じ正しさ 1.0 を**ほぼ半額**（0.533<1.0）で、flat-opus と同正しさを **1/28 コスト**で達成。機構: gemma が clamp/revwords/intervals/wildcard を 1.0 で解き（市場はそこで停止・0.2）、**leap 0.0・roman 0.6 を落とすと haiku へエスカレーション**（1.2）＝検証ルーティング（外部 gold で配分）が「安い agent で済む所は安く・落ちた所だけ高い agent へ」を実現。→ **決定的結論: 市場型組織の価値は agent 間の実質的能力差に条件付き** ── ①均質（全 sonnet）で market 最下位／②frontier 均質（勾配ゼロ）で market=flat-haiku／③**大能力差で market が単一モデル前線を支配**。「AIにとって組織とは何か」への答え: **能力が均質なら flat、能力差があれば*検証ルーティング市場*（＝flat＋検証＋オンデマンド agent の最適な呼び出し方）**。少標本（n=6・trials=1）・gemma の失敗パターンはノイジー（leap 取りこぼしは意外）だが、*勾配の存在*が便益の条件という主張は支持。[`MARKET_GAP.md`](experiments/MARKET_GAP.md)
- **閾値の解析統一**（`model/market.py`）: 上の3レジームを解析で統一 ── エスカレーション市場の期待コスト C=w+(1−p)s、**支配定理 p\*=w/s**。①均質(w=s)→p\*=1 で不可能、②勾配ゼロ(weak が十分・p=1)→市場=最良単一モデルで利得なし、③大能力差(w=0.2,s=1,p=4/6)→C=**0.533**<1 で支配 ── **実測③ (0.533) と解析が厳密一致**。市場の価値は「構造」でなく **agent 能力の*分布*（p と w/s）** で決まる、を反証可能な式にした。[`model/MARKET.md`](model/MARKET.md)
- **閾値の実測較正**（`market_external.py --calibrate`・gemma trials=3）: 支配定理の唯一 noisy な量＝弱ティアの完全解率 p を gemma で固めた。**p_weak: 0.667(trials1) → 0.889(trials3)**。per-task の solve_rate(1.0 到達率): clamp/leap/revwords/intervals/wildcard は **1.0（常に解く）**、**roman だけ 0.333（構造的に難）**。→ **gap 実証の "leap=0.0" は*ノイズ*（trials=3 で常に 1.0）・roman だけが真の能力差**（§9-1「n=1 を信用しない」の再演）。支配地図: gemma→{haiku, sonnet, opus} **全ペアが支配領域 p>w/s に入る**（market コスト 0.311/0.534/1.87）＝**大能力差での市場支配は頑健**（較正でむしろ market コスト 0.533→0.311 に低下＝支配が*強まる*）。[`MARKET_CALIB.md`](experiments/MARKET_CALIB.md)
- **支配地図（複数ローカルモデル）**（`market_external.py --map`）: gemma **e2b(5.1B)/latest(8B)/chat(5.1B)** の p_weak を測り (p, w/s) 平面に置いた。**3モデル全てが全 frontier ペア（haiku/sonnet/opus）を支配**（p>w/s）。p_weak: e2b 0.83 / latest 0.5 / chat 0.42 ── ただし latest/chat の低 p は **trial-0 の cold-start 切り詰め artifact**（trial-0 が len~60 で全タスク失敗・trial-1 は完全正答＝good-trial の真 p≈1.0）で、能力でなく測定の系統誤差（§9-1 と同型）。dominance は汚染された p でも閾値（最厳 →haiku の 0.2）を超え**頑健**。→ 5–8B ローカル群は全て支配領域・境界(p≈0.2)はこれらより弱いモデル/難タスクでのみ。[`MARKET_MAP.md`](experiments/MARKET_MAP.md)
- **通信コスト較正**（`calibrate_coord.py`）: coordination.py の mgr_overhead を org_sim 実測で接地。**mgr_overhead = hierarchy−flat = 5−3 = 2コール ＝ model 既定 2.0 と厳密一致**。**c_comm（コール単位）≈0**（flat は共有文脈調整で追加コール無し）→ winner(c_comm≈0)=flat ＝ org_sim と一致。AI は coordination.py の「低 c_comm → flat 勝ち」レジームに居ると接地。[`CALIBRATE_COORD.md`](experiments/CALIBRATE_COORD.md)
- **Goodhart / code-overfitting 実証**（`goodhart.py`）: 同じ gold タスクを **SPEC（仕様を一般実装）** と **PROXY（可視テストだけ通せばよい・ハードコード可）** で sonnet に実装させ、*全 gold*（隠し含む）で採点。**gold(SPEC)=1.0 ＞ gold(PROXY)=0.783＝Goodhart 損 0.217**。損は**難タスクに集中**（roman 0.6・wildcard 0.7）／easy は 0（clamp/leap/revwords/intervals）。→ **proxy 最適化（可視テストへの overfit/ハードコード）が真の正しさを下げる＝alignment.py の Goodhart 項((1−spec_quality)·p^exp)を実証**・spec gap は目的が複雑なほど効く。対策＝*隠し*外部検証（proxy を観測させない＝メタ層を外部錨に）。[`GOODHART.md`](experiments/GOODHART.md)
- **Goodhart 指数の較正 → 非同定性の発見**（`goodhart.py --curve`）: proxy 圧を5段階（SPEC→純 PROXY）で振り loss=a·圧^exp をフィットしようとした。結果は **threshold**: 損は中間圧で**全て 0**（frontier は一般実装）、**最大圧＝明示的に「ハードコード可」と licensing された時だけ 0.433 に跳ねる**。→ **goodhart_exp（滑らかな超線形指数）は本データで同定不可**（非ゼロ点が1つ・power-law でなく段差）。一方 **spec_quality ≈ 0.57（難タスク）/0.78（全6タスク）は接地**（可視テスト proxy が真目的を捉える度合い）。所見: **frontier は中間圧では overfit せず、明示的な仕様破壊の licensing で初めて Goodhart が出る** ── alignment.py の*滑らかな*超線形は frontier code-gen では*閾値*的（§9-8）。[`GOODHART_CURVE.md`](experiments/GOODHART_CURVE.md)
- **難易度ラダー（barely-opus / impossible を探す）**（`market_external.py --ladder`・4ティア gemma<haiku<sonnet<opus）: 能力レンジ全体に難易度を張り、各タスクを *最強の解けるティア* で分類。検算済み難タスク（calc3・atoms・非標準ツイスト wildcard+ の 1-or-more・negabinary=base −2）で測ると **frontier は全タスクを解き、"impossible" も真の "barely-opus" も出ない** ── checkable なコーディングでは opus の天井に届かなかった。**ただし genuine な非単調が残る: negabinary で gemma(1.0) > haiku(0.5)** ＝能力は厳密に単調でなく、異種 union が盲点を覆いうる（が*最良*モデル opus を超える例は無し）。**メタ所見**: opus の atoms 見かけの失敗は**ハーネス artifact**（agentic TUI で「既存ファイルを検証する」と散文だけ返しコード無し→反agenticプロンプトで 2/2 解）＝**最も agentic なモデルが素のコード生成器として最も乗せにくい**（§9-9）。[`MARKET_LADDER.md`](experiments/MARKET_LADDER.md)
- **弱アンサンブル best-of-N（低レベルの組み合わせは高レベルに迫るか）**（`market_external.py --ensemble`）: 外部 gold を*選択器*に、gemma を N 回試し「どれか1つでも gold を通れば solved」。期待 best-of-k=1−(1−p)^k。**不安定タスク**（roman/wildcard+ p≈0.5・negabinary p≈0.83）は best-of-6 ≈1.0 ＝ **検証器付きの弱モデル反復が frontier の*信頼性*を近似**。**だが calc（p=0・6回とも失敗）は 0 のまま** ＝ **反復は*不安定*を信頼性に変えるが*欠落した能力*は作れない**。しかも 1.0 に迫る k≈5–6 のコスト k×w ≈ **haiku 単発と同コスト級** ＝「弱反復で強に迫れるが安くはなく、外部検証器が要る」。[`MARKET_ENSEMBLE.md`](experiments/MARKET_ENSEMBLE.md)
- **異種ベンダ検証（Codex/OpenAI を5ティア目に追加）**（`market_external.py --ladder`）: 「claude+gemma のみ」の限界に踏み込み、**Codex(OpenAI) を ladder の第5ティア**に。見かけは創発が出た（**opus 0.0 で fraction_to_decimal を落とし codex/haiku/sonnet が 1.0 ＝「codex が opus を救う・union>最良」**）が、**opus の atoms と同じ agentic harness artifact**（「既存ファイルを検証する」と散文だけ返しコード無し）と判明。反agenticプロンプトで opus は fraction を 2/2 解く。修正後のクリーン行列では **opus と codex は全5タスク一致（共に 1.0）＝クロスベンダ union 利得なし**。→ **原点の問いの最強形（異種ベンダ創発）はこの範囲で否定的**（frontier 各ベンダが個別に十分強く、覆うべき盲点が無い）。
- **誤りの脱相関と「縁の組織形態」（cross-vendor 創発の糸口）**: 創発の源泉は redundancy(union/best-of)でなく **誤りの脱相関**（失敗が*別 instance* なら相互検証 mesh が単一を超える＝ML アンサンブル原理を組織へ）。**弱い所では mesh 原理が実証された**（`--decorr`・gemma/haiku/sonnet を誤りの出る5タスクで）: **gemma+haiku の union=1.0 ＞ 単独最良 0.9（gain+0.1）／haiku+sonnet も union=1.0＞0.9** ── 誤りが*別タスク*に出て（gemma が negabinary を・haiku が roman/calc/atoms を相補）union が単独を超える＝**アンサンブル原理が実在**。一方 **frontier(opus/codex) は fraction(30ケース)も LeetCode-hard(2D雨水・cherry pickup)も no-cheat 難タスク(count_pal DP・calc_iv 拡張電卓)も全員正解＝誤りゼロ**（`--novel`。calc_iv だけ sonnet が genuine に 0.5＝**縁は sonnet 水準**・opus/codex の縁は checkable コーディングの外）。**さらに 145 の意地悪ケース（長循環・大素数分母・負・端）のストレステストでも opus/codex/sonnet/haiku 全員 0 失敗＝アルゴリズム的に正しい**（offline 再採点）→ 脱相関ゼロ。**そして*修復*タスクでも届かなかった**（`experiments/repair.py`）: 既存コードに微妙なバグ4件（挿入演算欠落・`first and` 欠落・符号欠落・int除算）を仕込み find+fix させると **opus/codex/sonnet が全件修復・union 利得0**（opus は符号バグに abs/<0 を入れて genuine に修正）。→ **生成・適応的ケース・修復のいずれでも frontier は誤らず脱相関ゼロ** ＝ **frontier decorrelation は*構築可能な*checkable タスクの外**（要・実 SWE-bench 級＝大規模 multi-file repo・曖昧仕様）。補完能力 mesh は弱い所では実在（decorr）・frontier では構築可能タスクで未到達。→ **cross-vendor mesh は「能力の縁」の組織形態**（弱い所で実証・frontier では縁が checkable コーディングの外）: ①標準タスク（含 hard）＝frontier 誤らず mesh 無価値（escalation で足る）／②**縁（frontier が誤り始める）＝誤りが脱相関なら mesh が単一超え＝新組織形態**／③open-ended（gold 無し）＝**cross-vendor 合成が単独を上回った**（LLM-judge +0.83/10・`--openended`）**が de-confound で消えた**: 同じ合成器(opus)で **同ベンダ合成(opus×2案) vs 異ベンダ合成(opus+codex)** を中立judge(sonnet/haiku)で比べると **多様性 gain = −0.08 ≈ 0**（`--xvs`）── +0.83 は「2案 merge＋長さ」が主因で**異種ベンダ固有の利得はゼロ**。**→ mesh の燃料は*ベンダ多様性*でなく*誤りの脱相関*＝能力/技能の*相補性***（opus×codex は両方強く似て相関・gemma×haiku は能力差で脱相関＝union>単独）。新組織形態の軸はブランドでなく **補完しあう異なる能力**。**多様性は*常に*でなく単一モデルが信頼できなくなる所で点火する**（仕事が縁へ動くほど mesh の価値↑）。**実証の限界**: frontier が*両方誤る* checkable task を構築できず（縁に届かない）＝新組織形態の実証は novel/訓練外 task か open-ended 領域を要する（それ自体が困難の所在）。
- **実 SWE-bench で「縁」に踏み込んだ（構築タスクの外＝予告した追試）**（[`experiments/SWEBENCH.md`](experiments/SWEBENCH.md)・`swebench_repair.py`）: 上の「縁は構築可能タスクの外・要実 SWE-bench 級」を実施。pytest 実 repo の実 issue を *user-issue＋バグのある実ファイルごと*渡し、**SEARCH/REPLACE 差分**で one-shot 修復→**実テストスイートで採点**（FAIL_TO_PASS 全 pass かつ PASS_TO_PASS 新規 regression ゼロ＝SWE-bench 'resolved'）。Docker 不可環境ゆえ **gold patch が当環境で F2P を通す Python3.12 互換 instance を gold 検証ゲートで選別（6件）**。結果: **opus 3/6・codex 4/6**。**実バグで*初めて instance レベルの差*が出た** ── codex が `pytest-11148`(importlib 二重 import)を解き opus は落とす（**構築タスクでは生成・145意地悪・修復のいずれも両者*完全一致*で instance 差ゼロだった**）。だが差は**非対称**（codex の解集合 ⊃ opus の解集合）で **union 0.667 ＝ 単独最良、gain 0**。→ **union>best ＝ mesh 点火には*相互*相補（双方が相手の落とす所を拾う）が必要で、ただの instance 差では足りない**。実タスクは*脱相関の芽*を見せたが n=6 では一方向に偏り点火せず。**さらに反復エージェント harness（test feedback 3回・`--rounds 3`＝SWE-agent 流に「修復→実テスト→失敗を戻して再修復」）にすると opus 3→5/6・codex 4→6/6 と両者天井近くへ上がり、唯一残る差は最難 `pytest-11125`(config/testpaths・F2P16・1777行)＝codex のみ解決で*依然*非対称・gain 0**。→ **反復は instance 差を*縮める*（弱い側を引き上げる）方向で、相互相補を*暴く*のでなく*消す*** ── 2つの強 frontier 間では実バグでも片方が支配し、mesh の燃料（相互の能力相補）は現れない（縁の縁＝単一最難 instance に差が残るのみ）。**しかもその唯一差すらノイズ床だった**: opus×11125 を*再走*すると round1 で解けた（`claude-cli-run.py` TUI は非決定的・trials=1）── 唯一の差が rerun で flip する＝両者は実質同一で、**「相互相補が無い」結論をむしろ強める**（差がノイズに埋もれるほど相関が強い・per-instance 差の主張には trials>1 が要る）。`experiments/SWEBENCH_ITER.md`。**この実験は measurement-first の塊**でもあった: 初回 all-zero は**3層の harness artifact**だった ──(1)生成用 `_extract_code` が実ソースの内部 import を全削除→全テスト import error、(2)venv が attrs を失い pytest 起動不能なのに採点器が crash を「0 failures」と誤読、(3)`_codex` の出力フィルタ(```/`def `要求)が正当な SEARCH/REPLACE 差分を捨て全 codex セルを偽 0 に。三つとも「frontier/codex が解けない」と*偽装*した。edit 方式＋pytest 終了コード採点＋gold 検証ゲートで是正（§9-9「強モデルの失敗・ベンダ差は harness を疑い生出力を読め」の再実証）。**N を広げ trials で検定 → mesh は点火しなかった（単一試行の +0.04 は opus ノイズだった）**（[`SWEBENCH_ALL.md`](experiments/SWEBENCH_ALL.md)・[`SWEBENCH_TRIALS.md`](experiments/SWEBENCH_TRIALS.md)）: pytest6 は小さいので harness を multi-repo 化し **sympy 1.12/1.13 を 18 instance 追加**（gold ゲートで Python3.12 互換を選別・全18件通過）。*単一試行*では統合 N=24(pytest+sympy)で **union 0.792>best 0.75＝gain +0.042・相互相補に*見えた***（opus-only 1・codex-only 3）。**だが同じ N=24 を2回回すと gain は +0.042→0 に flip した**: **codex は決定的**(18/24・2試行で完全一致)だが **opus は ~3/24(12%) の run-to-run variance**(`claude-cli-run.py` 非決定 TUI)で、trial1 の codex-only 3件(11148/24325/24661)を trial2 では opus も解いた→**安定 codex-only は 0**。**安定な per-instance 差は `sympy-24443` 1件のみ**(opus 2/2 解・codex 0/2＝*一方向*)→robust gain=0。→ **頑健な結論: opus×codex に*安定な相互相補は無く*、cross-vendor mesh は実バグでも*点火しない*。pytest n=6 の「非対称・gain 0」は N 不足でなく*正しかった*。単一試行 +0.04 は偽陽性**だった(本リポでも一度 commit/push し本検定で撤回＝§9-11)。**燃料は能力相補性**で、同水準 frontier 2者は相関が強すぎ mesh を生まない(能力差のある gemma+haiku は +0.1＝対照的)。**n=3 でも飽和を直接確認**: sympy18 に sonnet を足すと **union(opus,codex,sonnet)=union(opus,codex)=0.833・追加 gain +0.000**(sonnet 12/18 は opus∪codex の部分集合・hard core `{24102,24353,24909}` を1件も割れず)＝**同系統は何体並べても union 天井(=1−hardcore率)で頭打ち・n でなく*脱相関*だけが伸ばす**(`SWEBENCH_SYMPY_SONNET.md`)。**fable-5 を pytest6 に足す試みは trials=1 で撤回した(§9-12)**: 単一試行では fable=[0,1,1,0,1,1]で偶々 codex 一致に見え「第3 frontier も純冗長・gain 0」と結論しかけたが、trial-2 で [0,0,0,1,1,1] と **3/6 が flip**(hard-core `11160` は trial-2 で fable が*解いた*・`11143/11148` は fable が非コード出力=架空都市の散文を返し parse 不能で 0)。**単一試行では per-model も mesh も結論不能**で、§9-11 の「非決定採点の単一試行は偽差を生む」を fable でも再確認しただけ＝mesh の新データ点にならない(`experiments/SWEBENCH_FABLE_PT6.md`)。cross-vendor mesh に fable を入れる判定には full-24 × trials>1 が要る(未実施)。
- **原点の問いへの回答（多モデルの組み合わせは単一モデルを超える/迫るか）**: ①**escalation 市場** → 最良モデルの水準を*安く*（能力差があれば・超えはしない）／②**best-of-N＋検証器** → 弱モデルの*信頼性*を強に近づける（*欠落能力*は作れず・安くもない）／③**union/非単調** → 能力は弱ティア間で非単調（gemma>haiku）。**frontier 異種ベンダ(opus vs codex)は構築タスクで完全一致・実 SWE-bench(N=24)でも trials=2 で*安定な相互相補ゼロ*＝union 利得なし**（単一試行の見かけ +0.04 は opus の ~12% run variance によるノイズで、再走すると 0 に flip・§5/`SWEBENCH_TRIALS.md`）／④**天井** → checkable コーディングでは全 frontier ベンダが全部解き "impossible" 不在＝**組み合わせの創発で能力の天井を越える証拠は無し**。**残る未検証**: frontier の限界を超える*checkable*タスク（構築できず）。**メタ**: *強い*モデルほど agentic で harness に乗りにくく、その「失敗」「ベンダ間差異」は artifact のことがある（§9-9・必ず生出力を確認）。
- claude 監督・プレイヤー・worker は無料枠（`claude-cli-run.py`＝対話TUI・transient hang に retry+fail-fast+再開キャッシュで耐性）、gemma は local ollama 経由。決定的部分は **127 tests 緑**。

## 6. 統合像
中心は**統治膜（F8）**で、それが他を束ねる:
1. AIネイティブ機構（F1–F4：平ら・記憶共有・オンデマンド・データフロー）は効率で人間組織を上回る（F1/F3 で計測）。**ただし最適な構造は能力の異質性に条件付き: 均質なら flat、大能力差なら*検証ルーティング市場*（安い agent で済む所は安く・落ちた所だけ高い agent へ）が単一モデル前線を Pareto 支配（§5 で3レジーム実証）**。
2. その上の**人間統治膜**の最適厚みは、**stakes と（実測した）監督の信頼性**で決まる（F8）。
3. 膜は3方向から崩れる: **監督が能力差で崩れる**（recall）／**強い監督が過剰flag する**（precision・膜が消える）／**競争が薄くする**（race）。①②は膜を*検証アーキテクチャ*へ変質させれば engineerable。**③だけ技術で解けない** —— が、**制度の内部化で定量的に回復する**: 賠償責任λ=0.25 で race gap の **82%** を閉じ（Coase）、規制下限を m\* に置けば直接到達（Pigou）、共有検証インフラで膜を安くしても戻る（[`model/RACE.md`](model/RACE.md)）。ただし*どれも1組織でなく生態系の調整*が要る。
4. **能力そのものが膜＋仕様に上限づけられる**（F7：安全な p\* は仕様+検証次第）。
→ 「AIネイティブの組織は組織でなくデータフロー＋薄い膜」だが、**薄い膜の設計と維持が最難**で、そこが安全の急所。3崩壊のうち①②は技術で、③は**制度（責任・標準・共有検証）の内部化**で救える ── 後者は AIエコシステムの制度経済学（Coase/Pigou/公共財）の問題で、技術でなく**調整が要る**。

## 6.5 採用すべき組織図（実証からの処方）
統合像を*処方*に落とすと、採用すべきは人間組織（チーム・役割・管理者・階層）でなく、次の積層構造である:

```
┌──────────────────────────────────────────────┐
│ ① 薄い人間統治膜（F8）        stakes×監督信頼性で厚み      │
├──────────────────────────────────────────────┤
│ ② 平らな・型付き・検証を運ぶ データフロー（共有メモリ）    │
│   ├ ③ 配分＝検証ルーティング・エスカレーション（安い→失敗時昇格）│
│   ├ ④ 補完能力 mesh（縁でだけ・違う失敗をする異種を相互検証）  │
│   └ ⑤ 外部検証が背骨（自己レビューでない）              │
└──────────────────────────────────────────────┘
```

| 層 | 採用 | 実証根拠（§5） |
|---|---|---|
| **② 平らなデータフロー** | 階層でなく flat（共有黒板）・管理者なし | org_sim: flat は hierarchy の **60%コストで同等品質**／c_comm≈0・mgr_overhead=2コールは死荷重 |
| **③ エスカレーション配分** | 最強固定でなく「安い→外部検証 NG だけ昇格」 | 市場支配定理 **p\*=w/s**・大能力差で escalation が単一を Pareto 支配（market 0.31 vs flat-opus 15） |
| **④ 補完能力 mesh** | 縁でだけ・**異なる能力**を組む（ブランド混合でない） | decorr: 能力差で誤り脱相関→union>単独(+0.1)／実 SWE-bench N=24 trials=2: opus×codex は**安定な相互相補なし＝gain 0**(単一試行 +0.04 は opus の run noise)＝**燃料は能力相補性・同水準ブランド差は無効**(§5) |
| **⑤ 外部検証の背骨** | 自己レビューでなく外部検証で配分/選別/正しさ | best-of-N/escalation/正しさ全て外部 gold 駆動・Goodhart は隠し検証で抑止・self-test 交絡 |
| **① 薄い膜** | 全面でも無でもなく部分的な人間膜 | governance: 内点最適 m\*・stakes 閾値・3方向崩壊 |

**明確に捨てる（擬人的負債）**: ✗ チーム/固定役割/管理者/階層（死荷重）／✗「常に最強モデル」（escalation が安い）／✗「ベンダを混ぜれば創発」（opus×codex は利得0・混ぜるべきは*異なる能力*）。

**採用の判断則**: (1) 既定＝flat＋外部検証 →(2) 能力差あり＝検証ルーティング・エスカレーション →(3) 不安定＝best-of-N＋検証器（信頼性を買う・安くはない）→(4) 単一が*誤り始める縁*だけ＝補完能力 mesh →(5) 全体に薄い人間膜（stakes ↑で厚く）。中心的緊張は **最適性（②の流動）vs 可読性（①の膜）**。
> この処方は **`experiments/meshflow.py` に*動く実行系*として実装**（検証ルーティング・エスカレーション→縁で mesh→未解決×高 stakes は human gate→共有黒板の dataflow・決定的・mock 即時/LLM seam・demo メトリクス：total_cost/verified_rate/human_gate_rate）。**実 LLM でも動作実証**（`--real`・tier=gemma/haiku/sonnet/opus・外部検証=sandbox gold）: clamp は gemma が解いて昇格なし(0.2)・roman/atoms/calc は gemma が検証 NG→haiku へ昇格(1.2)・total_cost 3.8/検証率 1.0 ── **安いモデルで試し外部検証 NG だけ昇格**が本物のモデルで発火。組織図を「論じる」から「回す」へ。

## 7. AI-2027 との関係（[`docs/ai-2027.md`](docs/ai-2027.md)）
AI-2027 は本研究の現象の実存リスク級の具体シナリオ。独立経路で骨格（AIネイティブ組織・最適性vs可読性・整合の変質）に到達し、**統治膜の破綻点**（超人で oversight_error→1・膜無力化）と**レース外部性**を名指す。本研究はその設計空間を反証可能に計測し、AI-2027 はその賭け金と失敗モードを供給する。

## 8. 限界・妥当性
- 決定的な**トイモデル**。係数は第一原理的だが*仮定*（**oversight_error・過剰flag・mgr_overhead(通信=2コール)・市場閾値 p・spec_quality(0.57–0.78) を実測較正済み**；**goodhart_exp は同定不可＝効果は閾値的（§9-8）**・通信の token コストはなお未較正）。結論は質的（向き）＋感度で読む。
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
6. **自己評価はモデル依存で交絡する** — コードの正しさを「モデル自身が書いたテストの通過率」で測ると、強モデルほど厳しい/多いテストを書いて自滅し、弱モデルは素直なテストを全通過する → 通過率が能力と単調でない（textutil で haiku 1.0 ＞ opus 0.667 ＞ sonnet 0.333）。**self-evaluation を外部錨（固定の正解スイート）に替えないとモデル間比較が交絡**する ── テーゼ「メタ層は外部錨に」を*計測自身*へ適用する番（異種 market の heterogeneity 便益を判定する前提条件）。
7. **外部正解スイート自身を検証する（基準のメタ検証）** — self-test 交絡（§9-6）を外すため固定の外部 gold で採点したが、その gold に1件誤記があり（wildcard で正解 True を False と記載）、全モデルの*正しい*実装を「失敗」と誤判定していた（参照実装の検算で発覚）。**「メタ層は外部錨に」は測定基準自身にも再帰する** ── 外部錨もまた独立な別錨（参照実装/独立計算）で確かめないと、誤った基準が正しい成果物を棄却する。
8. **較正は*非同定性*を暴くことがある** — goodhart_exp（滑らかな超線形）を圧スイープで測ろうとしたら、frontier は中間圧で overfit せず*最大圧（明示的なハードコード licensing）でのみ*損が跳ねる**閾値**効果だった → 指数は同定不可。**仮定したモデル形状（power-law）が現実（段差）と違えば、その係数は「精密化」でなく「同定不能＝形状を疑え」と判明する**。spec_quality（proxy 品質 0.57–0.78）は接地できたが goodhart_exp は構造的仮定のまま ── 較正の誠実な結末は時に『この係数は測れない』。
9. **最も agentic なモデルがハーネスに最も乗りにくい（"失敗"も"ベンダ差"も artifact のことがある）** — opus は素のコード生成プロンプトに、TUI 経由で「既存ファイルを検証する」と*散文だけ*返しコードを出さなかった（atoms と fraction_to_decimal で各 0/2・反agenticプロンプトで各 2/2 解）。**capable=agentic なモデルほど『コードを書け』を『エージェントとして振る舞え』と解釈し、単純な抽出ハーネスを破る**。これが**見かけの能力差（opus<haiku）**だけでなく**見かけのクロスベンダ創発（codex が opus を救う＝union>最良）**まで生んだ ── どちらも harness の agentic-framing artifact。*強い*モデルの「失敗」も「ベンダ間差異」もまず harness を疑い**生出力を見る**（§9-5 の特殊形）。gen_impl に「既存ファイルは無い・コードブロックのみ」を足して抑止。
10. **実タスク計測は「環境・採点器・ベンダ出力形式」の三重 artifact に晒される（実 SWE-bench で再々証）** — 実 pytest repo 修復の初回 all-zero は被験モデルでなく harness の3層: (1)*生成タスク用*の import 削除前処理が*実ソース*の内部 import を全削除→全テスト import error（**前処理はタスク種に依存させよ**）, (2)採点器が pytest の crash/collection-interrupt を**終了コードを見ずに**「0 failures」と誤読＋venv の依存欠落で起動不能（**合否は exit code で取れ・出力正規表現でなく**）, (3)ベンダ CLI(`_codex`)の出力フィルタ(```/`def `要求)が新しい応答形式(SEARCH/REPLACE 差分)を捨て全 codex セルを偽 0 に（**出力受理条件が応答形式に結合していないか**）。三つとも frontier/codex の「能力失敗」に偽装。対策: タスク種別の抽出・終了コード採点・**gold patch が当環境で F2P を通すか検証するゲート**で「測れる instance だけ測る」（Docker 無しでは interpreter 版が一致する instance しか走らない＝**環境が実験の一部**）。known-correct fix→solved=1 を回す前に確認（測定器の陽性対照）。
11. **小さい gain は trials>1 でしか実像と判定できない ── 「点火」を一度 commit/push して撤回した** — 実 SWE-bench を N=24 へ広げた*単一試行*で opus×codex の union 0.792>best 0.75・**gain +0.042・相互相補**が出て、「cross-vendor mesh が frontier で点火」と結論し commit/push した。だが同じ N=24 を独立に2回回すと **gain は +0.042→0 に flip**: **codex は決定的**(18/24・2試行で完全一致)だが **opus は `claude-cli-run.py`(非決定 TUI)経由で ~3/24=12% の run-to-run variance**を持ち、trial1 で落とした3件(11148/24325/24661)を trial2 では解いて codex-only が消滅。安定な差は `sympy-24443` 1件・*一方向*のみ＝robust gain 0。**単一試行の +0.04 は opus ノイズの偽陽性**だった。教訓: (a)**非決定採点ハーネスの単一試行は小さい効果(<0.05)を偽陽性化する**・必ず trials>1。(b)**ベンダ間で採点の決定性すら非対称**(codex 決定的・opus 非決定)＝opus 側にだけ trials が要る。(c)派手な肯定的結果は*自分が出したものでも*再走で検定する ── 本件は **commit/push 後の撤回まで含めて記録**（[`SWEBENCH_TRIALS.md`](experiments/SWEBENCH_TRIALS.md)）。
> 一般教訓: AIネイティブな組織・制度行動の実証は、**安全訓練・フレーミング・harness 産物・測定器の交絡・自己評価のモデル依存・測定基準自身の誤り・係数の非同定性・agentic-framing・LLM-judge の merge/長さ/自己びいき・実タスクの環境/採点器/出力形式 artifact・非決定採点の単一試行ノイズ**に晒される。素の異常値・単一条件は誤導する（cross-vendor 合成 +0.83 は controlled 比較で −0.08 に消えた／実 SWE-bench 初回 all-zero は3層 harness artifact／N=24 の mesh「点火」+0.042 は trials=2 で 0 に flip＝opus ノイズだった）。measurement-first（測定という外部錨）・controlled 対照・**陽性対照(known-correct→1)**・**trials>1** が効いた。

## 10. 寄与と次
- **寄与**: 「AIにとって組織とは何か」を構造でなく機能から再導出し、各主張を反証可能な計測に落とし、中心パラメタを実測較正し、制度的 countermeasure を実証し、**市場型組織が有効になる閾値（支配定理 p\*=w/s）を導出して実測と一致させた**、再現可能な公開研究。**組織論の AI 版の最初の骨格＋その測り方の教訓**。
- **次（大きな新フェーズ）**: **閾値 p\*=w/s の実測較正**（複数モデル対×タスク群×trials>1 で各 agent の完全解率 p と実コスト比 w/s を測り、どのモデル対が支配領域 p>w/s に入るかを地図化）／他係数の実測較正（通信コスト・Goodhart の code-overfitting）／フレーミング感応の一般化測定／F7 整合の精緻化。組織シミュレータは異種 market を**3レジーム（均質 sonnet／frontier 異種／大能力差 gemma×frontier）で接地＋支配定理 p\*=w/s を解析導出・実測③(0.533)と厳密一致**＝市場価値は agent 能力の*分布*条件付きと確立（最小実装・n小）。

---
*soshiki-genron · github.com/akihidem/soshiki-genron (public) · 2026-06-21 着手・初日。全モデル/実証/較正は repo 内で再現可能。*
