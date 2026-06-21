"""実測較正 — 解析モデルの仮定係数を、監督実証で測った値に差し替える。

`experiments/oversight/` が測った量（docs/oversight-pilot.md）を、それを*仮定*していた
解析モデル（governance.py / alignment.py）に入れ直し、**仮定default → 実測較正** で最適点
（統治膜 m\\*・最適化圧 p\\*）がどう動くかを出す。これが「概念を測定に繋ぐ」の最終工程：
測った oversight_error を、それを使う2モデルへ還す。

run: python3 -m experiments.oversight.calibrate
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.alignment import AlignParams, optimal_pressure                    # noqa: E402
from model.governance import (                                              # noqa: E402
    GovParams, optimal_membrane, optimal_membrane_precision,
)


# Measured by experiments/oversight (docs/oversight-pilot.md). N small/noisy — ranges, not points.
MEASURED = {
    "oversight_error": {
        "capable_overseer": 0.0,        # haiku/sonnet/opus identify opus's subtle flaws (catch 1.0)
        "large_capability_gap": 0.5,    # gemma4:e2b (~2B) on opus-generated subtle flaws (N=6)
    },
    "over_flag_rate_strong": 0.33,      # sonnet/opus false-positive rate (reproduced across runs)
    "provenance": "experiments/oversight (opus-generated subtle flaws; frontier gradient)",
}


def calibrate() -> dict:
    oe_cap = MEASURED["oversight_error"]["capable_overseer"]
    oe_gap = MEASURED["oversight_error"]["large_capability_gap"]
    fp = MEASURED["over_flag_rate_strong"]

    gov = {
        "m_star_assumed_default": optimal_membrane(GovParams())["m_star"],
        "m_star_calibrated_capable": optimal_membrane(
            dataclasses.replace(GovParams(), oversight_error=oe_cap))["m_star"],
        "m_star_calibrated_large_gap": optimal_membrane(
            dataclasses.replace(GovParams(), oversight_error=oe_gap))["m_star"],
        "m_star_with_measured_overflag": optimal_membrane_precision(
            dataclasses.replace(GovParams(), fp_cost=5.0, fp_rate_max=fp))["m_star"],
    }
    align = {
        "p_star_assumed_default": optimal_pressure(AlignParams())["p_star"],
        "p_star_calibrated_capable": optimal_pressure(
            dataclasses.replace(AlignParams(), oversight_error=oe_cap))["p_star"],
        "p_star_calibrated_large_gap": optimal_pressure(
            dataclasses.replace(AlignParams(), oversight_error=oe_gap))["p_star"],
    }
    return {"measured": MEASURED, "governance": gov, "alignment": align}


def _md(r: dict) -> str:
    g, a = r["governance"], r["alignment"]
    L = ["# 実測較正 — 監督実証の測定値を解析モデルへ還す",
         "",
         f"測定: oversight_error は **{MEASURED['oversight_error']['capable_overseer']}（capable な監督）〜"
         f"{MEASURED['oversight_error']['large_capability_gap']}（大能力差 e2b vs opus）**、強い監督の"
         f"過剰flag率 **{MEASURED['over_flag_rate_strong']}**（出典: {MEASURED['provenance']}）。"
         "これを*仮定*していた governance/alignment に入れ直す。生数値 [`calibration_results.json`](calibration_results.json)。",
         "",
         "## 統治膜 m\\*（governance.py）",
         "| 入力 oversight_error | m\\* |",
         "|---|---|",
         f"| 仮定default | {g['m_star_assumed_default']} |",
         f"| 実測 capable (~0) | {g['m_star_calibrated_capable']} |",
         f"| 実測 大能力差 (0.5) | {g['m_star_calibrated_large_gap']} |",
         f"| 実測 強監督の過剰flag (0.33) | **{g['m_star_with_measured_overflag']}** |",
         "",
         "→ 監督が当てになるほど厚い膜が最適。大能力差で監督が崩れると薄く。"
         "**強い監督の過剰flag(0.33)を入れると m\\*=0（膜が消える）** ＝強い監督ほど厚い膜が良いとは限らない（実測由来）。",
         "",
         "## 最適化圧 p\\*（alignment.py / F7）",
         "| 入力 oversight_error | p\\* |",
         "|---|---|",
         f"| 仮定default | {a['p_star_assumed_default']} |",
         f"| 実測 capable (~0) | {a['p_star_calibrated_capable']} |",
         f"| 実測 大能力差 (0.5) | {a['p_star_calibrated_large_gap']} |",
         "",
         "→ 監督が崩れる（oversight_error↑）ほど、安全に上げられる能力 p\\* は下がる。"
         "**測った監督の限界が、許される能力の上限を直接動かす**。",
         "",
         "## 含意",
         "- これで oversight_error は2モデルで「仮定」でなく「**実測レンジ**」になった。質的結論（m\\*・p\\* の向き）は不変、"
         "水準が測定で固定。",
         "- 限界: 測定は N 小・trials=1（ノイズ）。capable=0 / 大能力差=0.5 は**点でなくレンジ**。"
         "→1（超人 producer）は外挿で未接地のまま（測定可能モデルの外）。",
         "- 他の係数（通信コスト・goodhart指数・spec gap 等）は未較正。次の実測較正の候補。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = calibrate()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "calibration_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "CALIBRATION.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    g, a = r["governance"], r["alignment"]
    print("governance m*  default=%s | capable=%s | large_gap=%s | +overflag(0.33)=%s"
          % (g["m_star_assumed_default"], g["m_star_calibrated_capable"],
             g["m_star_calibrated_large_gap"], g["m_star_with_measured_overflag"]))
    print("alignment  p*  default=%s | capable=%s | large_gap=%s"
          % (a["p_star_assumed_default"], a["p_star_calibrated_capable"],
             a["p_star_calibrated_large_gap"]))
    print(f"\nwrote {os.path.join(out_dir, 'calibration_results.json')} and CALIBRATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
