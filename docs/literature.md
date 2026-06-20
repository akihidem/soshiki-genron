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
