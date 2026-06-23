# 研究計画：役割分業 coordinator は冗長 mesh と違い単体を超えるか（2026-06-24）

## 背景
2026-06-23 の実験で「**冗長並列 mesh**（同タスクを独立に解いた union / synthesis）」は5角度（古典アルゴ escalation・opus×haiku math・physics・gemma×haiku・自由記述 mesh）で不点火＝**市場支配（単一最強が最適）**を確認（`industry-benchmarks.md` §1–9）。

だが Sakana の **TRINITY**（ICLR 2026）/ **Fugu**（製品）は「**役割分業＋検証＋学習協調**」（Thinker / Worker / Verifier をマルチターンで動的割当）で単体超えを実証（SWE-Bench Pro 73.7 > Opus 4.8）。**両者は別メカニズム**。soshiki-genron は §6.5 で役割分業を処方しておきながら、実験では冗長 mesh しか潰していなかった＝**盲点**。Fugu はその処方の学習最適化実装に見える。

## 問い
冗長並列が超えないのは確定。では **役割分業（Thinker/Worker/Verifier）は単一最強モデルを超えるか? そしてその利得は「役割別配置の多様性」由来か、それとも「単に強モデルを反復呼び」由来か?**

## 仮説
- **H1**：役割分業（役割別に最適モデルを配置）は単一最強モデル（solo）を超える（Trinity 再現）。
- **H2**：その利得は「役割別配置」由来で、「同一モデルで役割分業（＝反復）」では小さい（cross-model > same-model role division）。
- **H3**：利得は checkable タスクで外部 gold により客観測定でき、judge 依存でない（§8 の judge confound を回避）。

## 設計（外部錨＝checkable・決定的）
タスク：`swebench_repair`（実バグ修復・pytest/sympy gold）or `org_sim` のコードタスク（sandbox gold 採点）。**自由記述や judge 依存は使わない**（§8–9 の confound 回避）。

比較群：
1. **solo**：単一最強（opus）が1人で 計画→実装→検証。
2. **redundant mesh**：3モデル独立に全タスク→union（2026-06-23 で不点火確認済み・既知対照）。
3. **role-division (same-model)**：Thinker/Worker/Verifier すべて opus（分業だが単一モデル＝**反復効果の対照**）。
4. **role-division (cross-model)**：役割別に最適モデル。例 Thinker=opus（計画）/ Worker=sonnet（実装）/ **Verifier=haiku（検証←§8 で haiku/sonnet が opus より良い検証者と判明済み）**。
5. **role-division (searched)**：役割×モデルの割当を探索（**Trinity coordinator の簡易版**＝grid / 進化で最適 delegation を発見）。

測定：各群の正答率（gold テスト pass 率）とコスト（tier-weighted）。
- **H1 判定**：群4/5 > 群1（solo）なら役割分業が点火。
- **H2 判定（de-confound）**：群4 > 群3 なら「役割別配置の多様性」が効く（単なる反復でない）。群3 が baseline、**群4 − 群3 = cross-model 配置の純利得**。
- 2026-06-23 の作法（trials で非決定を均す・cross vs same で de-confound）をそのまま適用。

## 段階
- **Phase 1（MVP）**：`meshflow` に役割分業パイプライン（Thinker→Worker→Verifier・固定割当）を実装。群 1/3/4 を checkable タスクで測定。決定的 mock テスト＋ `--real` LLM。
- **Phase 2**：役割×モデルの最適割当を grid/進化で探索（群5＝Trinity coordinator 簡易版）。
- **Phase 3**：de-confound（群3 vs 群4＝分業 vs 反復）＋ コスト効率（正答率×コストの Pareto front）。

## 既存資産との接続
- **§8 judge calibration**：Verifier 役割には haiku/sonnet（opus でない）＝「役割別配置」の実証済み一例。役割分業の理論的根拠。
- **`model/market.py`（市場支配定理 p\*=w/s）**：冗長 mesh では市場支配だが、役割分業では「役割ごとに p が違う」→ **定理の役割版へ拡張**（役割 r ごとの最適モデル m\*(r)）。
- **`meshflow.py`**：既存の検証ルーティング/escalation を役割分業に拡張。

## 反証可能性（外部錨原則）
- 群4/5 ≤ 群1（solo）→ 役割分業も超えない（市場支配が役割分業でも貫徹）＝H1 棄却。
- 群4 ≈ 群3 → 利得は分業でなく反復（多様性は役割分業でも無効）＝H2 棄却。
- judge 依存に逃げたら無効（checkable な外部 gold を必須とする）＝H3 を構造で強制。

## 参考
- TRINITY: An Evolved LLM Coordinator (arXiv 2512.04695, ICLR 2026)
- Sakana Fugu（2026-06-22 製品・TRINITY + Conductor 基盤）
- 本リポ §1–9（冗長 mesh 不点火）, §8（generator≠judge）
