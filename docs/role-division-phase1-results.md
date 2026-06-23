# 役割分業 Phase 1 / 1.5 結果：役割分業は単体最強を超えない（checkable 天井下 → 実バグ headroom 下でも貫徹）

> **要旨**：Phase 1（checkable・天井下）では天井効果で H1 を測れなかったが、Phase 1.5（実 SWE-bench 修復・
> headroom 下）で公正に再測した結果、**処方された固定 role 分業は単一最強を超えず、むしろ悪化（−0.167）**。
> 冗長 mesh に続き役割分業でも市場支配が貫徹。詳細は末尾「追記（Phase 1.5）」。

2026-06-24 / 実装 `experiments/role_division.py`・計画 [`role-division-research-plan.md`](./role-division-research-plan.md)

## 設定（外部錨＝checkable・決定的 gold）
役割分業パイプライン（Thinker→Worker→Verifier＋verify→repair loop）を動く実行系にし、3群を外部 sandbox
gold（`market_external.grade`）で採点。**Verifier には gold 非開示**（spec+code のみ＝Goodhart 遮断・H3）。

- **solo**：opus 単発 monolithic（役割分離も repair も無し）＝単一最強 baseline
- **role_same**：Thinker/Worker/Verifier すべて opus（分業だが単一モデル＝*反復効果*の対照）
- **role_cross**：Thinker=opus / Worker=sonnet / Verifier=haiku（§8 で haiku が良い検証者と判明済み）

タスク：`calc3`（再帰下降電卓）/ `negabinary`（負基数）/ `fraction_to_decimal`（循環小数）。trials=2・n_iter=2。
cost = tier-weighted（opus15 / sonnet3 / haiku1）。

## 結果

| task | solo (opus) | role_same (opus×3) | role_cross (opus/sonnet/haiku) |
|---|---|---|---|
| calc3 | 1.0 | 0.916 `[0.833, 1.0]` | 1.0 |
| negabinary | 1.0 | 1.0 | 1.0 |
| fraction_to_decimal | 1.0 | 1.0 | 1.0 |
| **群平均** | **1.0** | **0.972** | **1.0** |
| **平均 cost** | 15.0 | 32.5 | 18.0 |

- **structure_gain** (role_same − solo) = **−0.028**
- **diversity_gain** (role_cross − role_same) = **+0.028**
- **total_gain** (role_cross − solo) = **0.0**

## 判定（反証可能性に照らして）

**H1（役割分業 > solo）＝棄却。** role_cross = solo = 1.0。opus-solo が3タスクすべてで天井(1.0)に達し、
役割分業は単一最強を**超えない**。冗長 mesh で確定した**市場支配が役割分業でも貫徹**した（checkable な
これらのタスク上では）。

**H2（cross > same）＝弱い正(+0.028)だが「solo 超え」ではない。** diversity_gain の全量は role_same が
solo を**下回った**ことに由来する（calc3 trial で 0.833）。cross は天井に留まっただけ。つまり「多様性が
効いた」のでなく「**同一モデル自己検証の自傷を、別モデル(haiku)検証者が回避して天井へ戻した**」。

**唯一の測定可能な実効果は負（構造の自傷）。** role_same で **opus-Verifier が自分の不完全コードを時々
`LGTM` で rubber-stamp** し、0.833 で停止した（calc3 で `[0.833, 1.0]`＝間欠的）。これは §8「generator
最強 ≠ judge 最強・opus は良い検証者でない」が**役割分業 loop でも顕在化**した実機証拠。**単一強モデルを
役割分業構造（同一モデル自己検証）に包むと、わずかに悪化する。**

## 重大な限界：天井効果が H1 の本当の検証を妨げた

MX のアルゴリズム gold タスクは **opus に易しすぎて天井(1.0)**。役割分業（や repair loop）が価値を出すのは
Worker が**初回に失敗する**時だけだが、opus は失敗しないので verify→repair が実質発火しない。

TRINITY が単体超えを示した SWE-Bench Pro は frontier でも **73.7%＝headroom 大**。**sub-ceiling な基盤で
ないと「役割分業は単体最強を超えるか」は公正に測れない。** 本 Phase 1 は H1 に対し *checkable だが天井下* と
いう regime でしか答えられておらず、TRINITY の regime（hard・sub-ceiling）は未検証。

## 追記（Phase 1.5）：sub-ceiling 基盤（実 SWE-bench 修復）でも超えなかった — むしろ悪化
2026-06-24 / `experiments/role_division_repair.py`（role_division の pipeline を再利用し、SEARCH/REPLACE
修復 prompt＋per-instance grade closure＝実 pytest で FAIL_TO_PASS 全 pass ＆ PASS_TO_PASS 新規 regression
ゼロを 0/1 採点）。**Verifier には問題文＋差分のみ**（テスト ID・gold patch 非開示・H3）。pytest 実 repo の
usable 6 instance（trials=1・n_iter=2）。

| instance | solo (opus) | role_same (opus×3) | role_cross (opus/sonnet/haiku) |
|---|---|---|---|
| pytest-11125 | 0.0 | 0.0 | 0.0 |
| pytest-11143 | 1.0 | 1.0 | 1.0 |
| pytest-11148 | **1.0** | **0.0** | **0.0** |
| pytest-11160 | 0.0 | 0.0 | 0.0 |
| pytest-11178 | 1.0 | 1.0 | 1.0 |
| pytest-11217 | 1.0 | 1.0 | 1.0 |
| **群平均** | **0.667** | **0.500** | **0.500** |
| 平均 cost | 15.0 | 37.5 | 18.5 |

- **structure_gain** (role_same − solo) = **−0.167** / **diversity_gain** (cross − same) = **0.0** /
  **total_gain** (cross − solo) = **−0.167**

**headroom はあった**：opus-solo は 2/6（11125・11160）で **0.0＝失敗**＝Phase 1 の天井効果は解消。にもかかわらず：

**H1 棄却（より強く：役割分業は solo を下回る）。** role_cross(0.5) < solo(0.667)。
- **solo が落とす hard 2件（11125・11160）を役割分業も拾えなかった**（縁での補完能力なし＝冗長 mesh と同じ）。
- **決定的なのは 11148**：solo opus が解けた実バグを role_same/role_cross が**両方 0.0 に壊した**。thinker の
  plan が worker を別箇所（`insert_missing_modules`）の不十分な修正へ誘導し、**Verifier（opus も haiku も）が
  落ちる fix に LGTM** して見逃した（n_iter=2 でも repair 発火せず）。−0.167 はこの 1 件の 1→0 反転が全量。
  ※ 3 群の diff はいずれも**適用は成功**（harness artifact でなく公正な計測）。
- **diversity_gain = 0.0**：role_cross は全 instance で role_same と同値。**役割別モデル配置は何も足さなかった**
  （haiku verifier も 11148 の誤 fix を LGTM）。Phase 1 で haiku が良い検証者だったのは codegen 限定で、
  実バグ repair では haiku も rubber-stamp＝**検証者の質はタスク依存**。

**結論（Phase 1 と 1.5 が同じ向き）**：処方された固定 role 分業（Thinker→Worker→Verifier・外部検証*非開示*の
Verifier）は、checkable でも実バグでも、天井下でも headroom 下でも **単一最強を超えない・時に悪化する**。
冗長 mesh に続き **役割分業でも市場支配が貫徹**。自傷源は ① plan-handoff drift ② Verifier の rubber-stamp。

**TRINITY との整合（refute ではない）**：TRINITY は*学習された* coordinator＋多ターン動的割当＋（おそらく）
テスト接地反復で伸びた。本実験が示したのは「**素朴な固定 role 分業＋gold 非開示 Verifier は伸びない**」。
差分＝価値は「役割分業そのもの」でなく「**学習された協調＋テスト接地の反復**」にある、と仮説を絞れる。

**限界**：n=6・trials=1（−0.167 は 11148 単独由来・小標本）。方向は Phase 1＋pilot＋本走で一貫だが数値は要追試。

## 次の一手
1. **robustness**：trials↑・instance↑（usable は現状 6）。−0.167 が 11148 以外でも出るか。
2. **「テスト接地の反復」を分離**：Verifier を gold-blind でなく**実テスト出力 feedback**に替えた loop（swebench
   `_repair_iterative` 型）が solo を超えるか＝「価値は role 分業でなく test-grounded 反復」仮説の直接検証。
3. Phase 2：役割×モデルの最適割当を grid/進化で探索（Trinity coordinator 簡易版）。ただし固定割当が伸びない
   以上、coordinator の価値は「割当探索」より「学習＋接地」にある可能性が高い。

## 既存資産との接続
- **§8 judge calibration**：opus-Verifier の rubber-stamp（LGTM 自傷）は §8 の「opus は良い検証者でない」を
  役割分業の文脈で再確認。Verifier=haiku が同一モデル自己検証の自傷を防ぐ。
- **市場支配定理 `model/market.py`（p\*=w/s）**：checkable・天井下のタスクでは役割分業でも単一最強が支配。
  「役割版の定理」（役割 r ごとの最適 m\*(r)）は sub-ceiling regime で headroom が出て初めて意味を持つ。
- 決定的 mock（`role_division.py` の null/positive world）でハーネスの公正さ（rig されてない・gold-leak 無し・
  cost 算術・de-confound）を担保済み（`tests/test_role_division.py` 11 緑）。
