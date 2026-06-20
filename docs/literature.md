# 文献調査 — survey agenda & log

[`method.md`](method.md) の第一原理「モデルと実験による科学的計測」を支える文献台帳。読む目的は3つに限定 —— (1) **再利用できる形式モデル**、(2) **先行する計測・実験**、(3) **空白（まだ測られていない主張）**。各文献は「**仮定した人間拘束 / 何を測ったか / AIへ転移するか**」で記録する。

古典組織論の正典は [`references.md`](references.md)。本ファイルはより広い・非古典・近年のクラスタと、調査の運用を扱う。

> **信頼度の規律（幻覚回避）**: 古典（理論の骨格が確立）は要約してよい。**近年の LLM マルチエージェント等は、一次文献を確認するまで主張・数値を断定しない**。下記の各項目は「読むべき対象」であって「結論」ではない。年・版・主張は精読時に検証して確定する。

## クラスタ B — 形式・経済モデル（②に直接使える数理）
- **Marschak & Radner, *Economic Theory of Teams* (1972)** — チーム＝共通目的だが情報が分散したエージェント群。通信・情報処理の制約下での最適情報構造を数理化。→ **本研究の最有力な形式 backbone**。
- **Malone, Coordination Theory / Malone-Yates-Benjamin, "Electronic Markets and Electronic Hierarchies" (1987)** — IT が調整コストを下げると構造が階層→市場へ寄る、を理論化・観測。→ **AI＝調整コスト低下の極限**の予測元。
- **March (1991), "Exploration and Exploitation in Organizational Learning"** — 探索/活用の均衡。AI組織でどう動くか。
- **Mechanism design（Hurwicz / Myerson / Maskin）** — 分散した私的情報と誘因両立。誘因は AI で変質するが「情報集約と整合」の数理は転移しうる。

## クラスタ C — 計算組織論（シミュレーション＝②の先例）
- **Carley & Prietula (eds.), *Computational Organization Theory* (1994)** ／ 学術誌 *Computational and Mathematical Organization Theory (CMOT)*。組織をエージェントベースで**シミュレートして測る**伝統。②設計の直接の先例。
- **Cohen, March & Olsen (1972), "A Garbage Can Model of Organizational Choice"** — 構造化された無秩序の意思決定モデル。
- **Conway's Law の実証研究** — 組織構造↔システム構造の同型を測った系譜。

## クラスタ D — 分散AI / マルチエージェント（実装＝②の系譜）
- **Smith (1980), Contract Net Protocol** — タスクの入札的分配。市場的割り当ての古典。
- **Blackboard systems（Hayes-Roth ら）** — 共有黒板による統合（F3/F4 の非階層実装）。
- **Market-based control（Clearwater ed., 1996）** — 価格機構で資源・タスクを調整。
- **Wooldridge, *An Introduction to MultiAgent Systems*；Stone & Veloso (2000) MAS survey** — 協調・調整の枠組み。

## クラスタ E — 近年の LLM マルチエージェント（**要一次確認・断定しない**）
読むべき対象（結論ではない）: 生成エージェントの社会シミュレーション、multi-agent debate、役割分担型フレームワーク（AutoGen / MetaGPT / CAMEL 系）、society-of-minds 的議論。
→ 抽出したいもの: (a) 既にどんな構造が試され**何が測られたか**、(b) 人間組織の語彙をどれだけ無批判に借りているか（＝本研究の批判対象）、(c) 失敗モード。
→ **精読し一次確認するまで、個別の主張・数値は本研究に取り込まない。**

## 読了ログ

- **Marschak & Radner, *Economic Theory of Teams* (1972, Yale UP, Cowles Monograph 22, 345pp)**
  - 仮定した人間拘束: 共通目的だが**情報が分散**し通信が有限。各意思決定者は全体を知らない。
  - 何を測ったか: 「**情報構造**（誰が何をいつ知るか）」を所与に、共有コスト関数を最適化する意思決定規則。Shannon の情報理論を経済学へ導入。
  - AIへ転移するか / 使い道: 情報構造＝組織の通信トポロジそのもの。理論は通信が有限という前提に立つ → **c_comm→0 で最適情報構造が変わる**を予言。本研究モデル（`../model/coordination.py`）の c_comm 軸の形式的裏付け。F3/F4 の backbone。
  - 信頼度: **二次確認**（要旨・書誌・レビュー）。一次精読は未。
- **Malone, Yates & Benjamin (1987), "Electronic Markets and Electronic Hierarchies," CACM 30(6):484–497**
  - 仮定した人間拘束: **調整コスト**（IT 以前は高い）。資産特殊性・製品記述の複雑さが市場/階層の選択を左右。
  - 何を測ったか / 主張: 電子市場仮説(EMH) —— IT が調整コストを下げると構造は**階層→市場**へ寄る。
  - AIへ転移するか / 使い道: **AI＝調整コスト低下の極限** → 市場化を強く予言。本研究モデルの計測「c_comm を下げると hierarchy→market→flat」と**整合**（market が中低域で勝つ）。次はモデルに asset-specificity 軸を足す。F2/F3。
  - 信頼度: **二次確認**（要旨・書誌）。一次精読は未。

- **Carley & Prietula (eds.), *Computational Organization Theory* (1994, Routledge/LEA)**
  - 仮定した人間拘束: 組織は有界合理なエージェントの集合。構造（調整様式）が性能を左右。
  - 何を測ったか: **異なる構造の組織の性能**を、シミュレーション・数値解析・記号論理・数理モデル・グラフ理論で系統的に測る方法論を確立。エージェント能力 × 調整 が性能にどう効くか。
  - AIへ転移するか / 使い道: **本研究の ②（モデルと実験による計測）が立つ伝統そのもの**。`model/` の決定的モデルは COT 系譜に位置づく。Carley の「エージェント能力 × 調整」は、次の計測＝**容量制約軸（F1/有界合理性）**を足す動機。
  - 信頼度: 二次確認（要旨・書誌）。一次精読は未。

> メモ: 3件とも本研究と整合。Marschak&Radner が c_comm 軸の数理的土台、Malone が「下げると市場化」の予測元、**Carley が「構造をシミュレーションで測る」方法そのものの正当化**。次は一次精読での係数正当化、または容量制約軸の追加（第三の計測）。

## 記録フォーマット（読んだら追記）
```
- <著者 年, タイトル>
  - 仮定した人間拘束: …
  - 何を測ったか（あれば）: …
  - AIへ転移するか / 本研究での使い道: …
  - 信頼度: 一次確認済 / 二次 / 未読
```

## 次に読む（優先度順）
1. **Marschak & Radner**（形式 backbone）
2. **Malone-Yates-Benjamin 1987**（AI＝調整コスト低下の極限の予測元）
3. **Carley 計算組織論**（②の先例＝測り方）
4. **Smith Contract Net**（市場的割り当て）
5. **クラスタ E の一次確認**（近年 LLM マルチエージェントが何を測ったか）

> 進め方: 1件読むごとに上のフォーマットで追記し、対応する原始機能（[`foundations.md`](foundations.md) F1–F8）へ相互参照を張る。読了が ①（転移マッピング）を前進させ、抽出した形式モデルが ②（実験基盤）の設計に入る。
