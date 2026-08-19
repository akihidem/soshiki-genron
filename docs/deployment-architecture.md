# 実証ベースの AI 配置構造（deployment architecture）

2026-06-24 / 本リポの実証（[`role-division-phase1-results.md`](./role-division-phase1-results.md)・
[`../model/mesh.py`](../model/mesh.py)＝[`MESH.md`](../model/MESH.md)・[`../model/market.py`](../model/market.py)＝
[`MARKET.md`](../model/MARKET.md)・[`../experiments/meshflow.py`](../experiments/meshflow.py)）を、実際の AI 配置の
処方に落とす。PAPER §6.5「採用すべき組織図」の証拠付き精緻化。

> **核心**：前線を動かすのは *マルチエージェント構造*（mesh／役割分業）でなく、**① 外部検証への接地**と
> **② 脱相関の分布**。配置は「役割を増やす」でなく「**検証を背骨に据え、安く接地し、脱相関のある所だけ束ねる**」。
>
> **スコープ**：以下の数値は **checkable（コーディング／gold あり）で実測**。自然言語など検証性の低い出力へは
> 「§検証性の軸」で一般化するが、その部分は **外挿**（§8 judge calibration ＋ config_mesh の Goodhart 実測が
> 支えだが直接は未測）。実測と外挿を本文中で明示する。

## 根拠（本リポの実証・すべて checkable）

| 観測 | 結果 | 配置への含意 | 出典 |
|---|---|---|---|
| 冗長並列 mesh | solo 超えず（市場支配） | 同モデル N 並列はしない | 5角度実証・`mesh.py` ρ≈1 |
| 固定役割分業（Thinker/Worker/Verifier・gold 非開示 verifier） | solo 未満（**−0.167**）・時に悪化 | 役割を切らない（**弱い根拠**・下記⚠） | `1513c66` |
| **テスト接地反復**（単一モデル＋実テスト feedback） | **全解決（+0.333）** | これが既定ユニット（**弱い根拠**・下記⚠） | `b69a7d1` |
| model verifier（opus/haiku） | 落ちるコードに LGTM（rubber-stamp） | gate に使わない | §8 / `b69a7d1` |
| escalation 市場 | 安モデルが p>w/s なら単一最強を Pareto 支配 | コスト層に使う | `market.py` |
| mesh 点火（実測 opus×codex） | **撤回済み** ── 単一試行の gain +0.042 はノイズ由来の偽陽性で、trials=2 で 0 に flip（`fcbfa5c`） | 縁 mesh に**実証的裏付けは無い** | `SWEBENCH_TRIALS.md` / `MESH.md` |

> ⚠ **役割分業まわりの数値（−0.167 / +0.333 / +0.5）は検出床の下にある。**
> 出典 `experiments/role_division_repair_real.json` は **trials=1・n=6**。厳密符号検定を通すと
> 5 主張すべてが p ≥ 0.25（有意 0 件）で、**この標本は差の有無を決められない**
> （[`../model/REPLICATION.md`](../model/REPLICATION.md) ②）。以下の L0/L1 の処方は、
> 本リポの他の証拠（§8 judge calibration・market.py・mesh の非点火）と整合するが、
> **この 1 ファイルだけでは支えられていない**。n≥6 かつ trials≥2 での再測が返済すべき負債。

## 配置（5 層）

### L0 — 背骨：入手可能な最強の外部アンカー（全層がここで gate）
- 第一候補は **外部決定的検証**（test／compiler／typecheck／sandbox gold／schema）。自己申告でなく外部。
- 🔬 test_loop=**1.0** vs model-verifier loop=0.5。model verifier は opus も haiku も落ちるコードに LGTM。
- 配置則：**受け入れ判定は必ず外部アンカー**。model 批評は repair の *種(prior)* に使ってよいが、acceptance を
  決めさせない。アンカーが弱い領域では「§検証性の軸」で*製造*する。

### L1 — 既定ユニット：単一最強モデル × アンカー接地の反復ループ
- 1 モデルが文脈を保持し「提案 → 外部アンカーで採点 → 失敗を戻して修正」を反復。
- 🔬 test_loop（単一 opus＋実テスト）が役割分業を **+0.5** 上回り全解決。
- 避ける：固定 Thinker/Worker/Verifier の分業（plan-handoff drift＋verifier 見逃しで **−0.167**）。**役割を
  切らない**のが既定。複数モデルは「縁」(L3) でだけ。

### L2 — コスト層：検証ルーティング型エスカレーション（安 → 強）
- 安ティアで解き、外部アンカーで落ちた時だけ上位へ昇格。
- 🔬 market 臨界 **p > w/s**（安モデルの完全解率がコスト比を超えれば単一最強を Pareto 支配）。
- 配置則：タスク分布の p と w/s を測って梯子を組む。均質（w≈s）なら梯子は無駄＝最強 1 本。

### L3 — 縁の mesh：cross-vendor のみ・union は外部アンカーで選ぶ
- 梯子の最上位でも落ちる「縁」で、**別系統モデル（cross-vendor）がある時だけ**並列 union。
- 🔬 mesh 臨界＝脱相関 **ρ<1 ＋ 相互相補（非入れ子）**。ただし **実測は点火していない**：
  一度 opus×codex で ρ=0.61・gain +0.042 を「点火」と報告したが、trials=2 で **gain 0 に flip して撤回**
  （[`../experiments/SWEBENCH_TRIALS.md`](../experiments/SWEBENCH_TRIALS.md)）。安定な相互相補はゼロで、
  観測された利得は opus 側の run noise（f≈0.067）だった。同系統/冗長は ρ≈1 で無駄。
- 配置則：同モデルの N 並列はしない（市場支配）。**cross-vendor 並列も、実証された利得は現状ゼロ**
  ── 理屈（ρ<1 なら点火しうる）で残す層であって、測って勝ったから残す層ではない。

### L4 — 人間膜：高 stakes × 未解決は黙って ship しない
- 梯子＋縁でも未解決 ＆ stakes 高 → 人間へエスカレーション。
- 🔬 meshflow ①＋governance（薄い膜が真品質を守る・膜=0 は wrong ship）。
- 配置則：膜は**薄く**（過剰確認は失速）。gate は「高 stakes × 外部アンカー未通過」に限定。

## 判断表（いつ何を足すか）

| 状況 | 配置 |
|---|---|
| 既定（まずこれ） | 単一最強＋アンカー接地ループ（L0+L1） |
| 安くしたい ＆ 安モデル p>w/s | エスカレーション追加（L2） |
| 最上位も落ちる縁 ＆ cross-vendor 在り | 縁 mesh（L3・**実証利得ゼロ**・理屈で残す層） |
| 高 stakes 未解決 | 人間膜（L4） |
| **やらない** | 役割分業の固定パイプライン／同系統の冗長 mesh／model verifier を gate に |

## 検証性の軸（一般化 ── checkable から自然言語へ）

L0 の「アンカー」の強さはタスクの**検証性**で決まり、それが実装を変える。**この行は段階的に外挿が増える。**

| 検証性 | 例 | L0 アンカー | L1 ループ | 実測/外挿 |
|---|---|---|---|---|
| **高** | コード・数学・スキーマ抽出 | 決定的テスト/型/sandbox | テスト接地反復が**王** | **実測**（本セッション） |
| **中** | 事実ベース NL（要約・レポート・QA） | 主張分解 → retrieval/citation/NLI 接地＋制約チェック | 主張ごとに接地して反復 | 外挿（docs-first の作法） |
| **低** | 開放/創作 NL（文章・対話） | cross-vendor 多様 judge パネル（較正）＋人間膜 | 弱い・Goodhart 注意 | 外挿 |

**NL で背骨を*製造*する順（強 → 弱）**：
1. **検証可能な小主張へ分解**：「良い要約か」（測れない）→「各事実主張がソースに接地してるか」（retrieval/
   citation/NLI で**測れる**）。
2. **制約・形式チェック**：長さ/必須節/スキーマ/禁止語/安全分類器/groundedness＝NL でも決定的アンカー。
3. **model judge は最後の砦**、かつ §8 を適用：**生成器に自己採点させない**（generator≠judge）／**cross-vendor の
   多様 judge パネル**（判定誤差も系統間で脱相関＝mesh の ρ<1 が *judge 側*に効く）／human ラベルで較正。
4. **人間膜が重くなる**（検証性が低い＝高 stakes escalation が増える）。

## スコープと反証可能性（正直）

- **コーディングは実測**（上表の数値・commit）。**NL の一般化は外挿**＝直接は測っていない。支える既存データ点は
  §8（generator≠judge・model judge は弱い）と config_mesh richloop の **Goodhart 実測**（可視判定は満点なのに
  held-out 真品質が落ちる）。
- **反証可能な予測**：検証性が下がるほど test-grounded 反復の +0.333 級の勝ちは 0 に縮み、model-judge ループは
  Goodhart（judge スコア↑・真品質横ばい）を示すはず。これは config_mesh の visible/held-out split で**測れる**
  （未実施・次の一手）。
- 本配置が偽となる条件：① 外部アンカー無しの model-judge ループが真品質（held-out/human）を継続的に改善する、
  ② 同系統の冗長 mesh が外部アンカー下で union>best を出す、③ 固定役割分業が単一最強＋接地ループを超える。

## meshflow.py への精緻化差分

[`../experiments/meshflow.py`](../experiments/meshflow.py) は既に escalation（L2）＋edge-mesh（L3）＋human-membrane
（L4）を実装。本実証が足す差分：

- **(a)** 各ティアの agent を *one-shot* でなく **アンカー接地の反復ループ**（L1）に（test_loop が王）。
- **(b)** edge-mesh を **cross-vendor 限定**に（同系統は ρ≈1 で無駄）。
- **(c)** model-verifier を **gate から seed へ降格**（rubber-stamp 回避）。
- **(d)** L0 を「決定的検証」から「**入手可能な最強アンカー**」へ一般化し、**検証性の軸**で実装を切り替える。
