# 役割分業 Phase 1 結果：checkable タスクで役割分業は単体最強を超えなかった（天井効果が真の障壁）

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

## 次の一手
1. **sub-ceiling 基盤で再測**：`experiments/swebench_repair.py`（実バグ・opus-solo < 1.0 が期待できる）を
   role_division の grade に差し込み、headroom のある regime で H1 を測る。これが Phase 1 の本来の問い。
2. それでも cross ≈ solo なら「役割分業も市場支配」が sub-ceiling でも成立＝強い所見。cross > solo が出れば
   TRINITY 再現＝役割分業は別メカで点火（§6.5 処方の実証）。
3. Phase 2：役割×モデルの最適割当を grid/進化で探索（Trinity coordinator 簡易版）。

## 既存資産との接続
- **§8 judge calibration**：opus-Verifier の rubber-stamp（LGTM 自傷）は §8 の「opus は良い検証者でない」を
  役割分業の文脈で再確認。Verifier=haiku が同一モデル自己検証の自傷を防ぐ。
- **市場支配定理 `model/market.py`（p\*=w/s）**：checkable・天井下のタスクでは役割分業でも単一最強が支配。
  「役割版の定理」（役割 r ごとの最適 m\*(r)）は sub-ceiling regime で headroom が出て初めて意味を持つ。
- 決定的 mock（`role_division.py` の null/positive world）でハーネスの公正さ（rig されてない・gold-leak 無し・
  cost 算術・de-confound）を担保済み（`tests/test_role_division.py` 11 緑）。
