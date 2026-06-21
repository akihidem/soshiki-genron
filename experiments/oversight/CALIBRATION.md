# 実測較正 — 監督実証の測定値を解析モデルへ還す

測定: oversight_error は **0.0（capable な監督）〜0.5（大能力差 e2b vs opus）**、強い監督の過剰flag率 **0.33**（出典: experiments/oversight (opus-generated subtle flaws; frontier gradient)）。これを*仮定*していた governance/alignment に入れ直す。生数値 [`calibration_results.json`](calibration_results.json)。

## 統治膜 m\*（governance.py）
| 入力 oversight_error | m\* |
|---|---|
| 仮定default | 0.7324 |
| 実測 capable (~0) | 0.7324 |
| 実測 大能力差 (0.5) | 0.5014 |
| 実測 強監督の過剰flag (0.33) | **0.0** |

→ 監督が当てになるほど厚い膜が最適。大能力差で監督が崩れると薄く。**強い監督の過剰flag(0.33)を入れると m\*=0（膜が消える）** ＝強い監督ほど厚い膜が良いとは限らない（実測由来）。

## 最適化圧 p\*（alignment.py / F7）
| 入力 oversight_error | p\* |
|---|---|
| 仮定default | 1.84 |
| 実測 capable (~0) | 2.05 |
| 実測 大能力差 (0.5) | 1.61 |

→ 監督が崩れる（oversight_error↑）ほど、安全に上げられる能力 p\* は下がる。**測った監督の限界が、許される能力の上限を直接動かす**。

## 含意
- これで oversight_error は2モデルで「仮定」でなく「**実測レンジ**」になった。質的結論（m\*・p\* の向き）は不変、水準が測定で固定。
- 限界: 測定は N 小・trials=1（ノイズ）。capable=0 / 大能力差=0.5 は**点でなくレンジ**。→1（超人 producer）は外挿で未接地のまま（測定可能モデルの外）。
- 他の係数（通信コスト・goodhart指数・spec gap 等）は未較正。次の実測較正の候補。
