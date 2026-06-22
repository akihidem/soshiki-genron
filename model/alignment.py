r"""F7 整合の形式化 — 「管理 → 仕様+検証+監督」を測れる形に。

人間組織の F7（動機づけ・整合）は、人の私利・サボり・離反を管理する装置だった。AI に
私利は無いが、整合の問題は消えず**変質**する: AI は与えた**仕様(spec)を最適化する**ので、
spec が真の目的とずれている（spec gap）と、**強く最適化するほど真の目的は悪化しうる**
（Goodhart / spec-gaming）。これを抑えるのが **仕様の精緻化・検証・監督**。

    真の価値(p) = 生産的ゲイン(p) − Goodhart損(spec, p)·(1 − 検証で捕捉)
        生産的ゲイン  = gain · (1 − e^(−p))                （最適化圧 p で飽和的に増える）
        Goodhart損    = (1 − spec_quality) · p^goodhart_exp  （spec gap × 圧の超線形）
        検証で捕捉      = verification · (1 − oversight_error)  （oversight_error は実測値）

核の予言（測れる・反証可能）:
- 最適な最適化圧 **p\*** が内点に存在する（p\* を超えて能力を強めると真の価値は*下がる*＝Goodhart）。
- **p\* は spec品質・検証とともに上がり、oversight_error とともに下がる** ＝「能力は仕様+検証が
  追いつく範囲までしか安全に上げられない」。これが「整合＝仕様+検証+監督」の定量形。
- 仕様+検証を固定したまま能力 p を上げる（AI-2027 のレース）と、p\* を超えて真の価値は**崩れる**。

oversight_error は `experiments/oversight/` の実測（~0〜0.5）で接地。検証は統治膜（governance.py）に対応。
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AlignParams:
    spec_quality: float = 0.7      # s: how well the spec captures the true objective [0,1]
                                   # (grounded: goodhart.py proxy-quality 0.57 hard / 0.78 full suite)
    verification: float = 0.6      # v: fraction of divergence verification would catch [0,1]
    oversight_error: float = 0.2   # verification itself is imperfect (grounded: experiments/oversight)
    goodhart_exp: float = 1.5      # super-linearity of spec-gaming in optimization pressure
                                   # (structural: goodhart.py --curve finds a THRESHOLD not a smooth
                                   #  power-law on a frontier model -> exp is not identifiable)
    gain: float = 2.0              # scale of the productive gain (saturating)
    p_max: float = 6.0             # max optimization pressure considered
    grid: int = 601


def utility_gain(p: AlignParams, pressure: float) -> float:
    return p.gain * (1.0 - math.exp(-max(0.0, pressure)))


def caught_fraction(p: AlignParams) -> float:
    return p.verification * (1.0 - p.oversight_error)


def goodhart_loss(p: AlignParams, pressure: float) -> float:
    return (1.0 - p.spec_quality) * (max(0.0, pressure) ** p.goodhart_exp)


def true_value(p: AlignParams, pressure: float) -> float:
    return utility_gain(p, pressure) - goodhart_loss(p, pressure) * (1.0 - caught_fraction(p))


def _pressures(p: AlignParams) -> list[float]:
    return [p.p_max * i / (p.grid - 1) for i in range(p.grid)]


def optimal_pressure(p: AlignParams) -> dict:
    best = max(_pressures(p), key=lambda x: true_value(p, x))
    return {"p_star": round(best, 4), "true_value_at_p_star": round(true_value(p, best), 4),
            "interior": 0.0 < best < p.p_max}


def run(p: AlignParams | None = None) -> dict:
    p = p or AlignParams()
    opt = optimal_pressure(p)
    curve = [{"p": round(x, 2), "true_value": round(true_value(p, x), 4)}
             for x in [p.p_max * i / 12 for i in range(13)]]
    spec_sweep = [{"spec_quality": s, "p_star": optimal_pressure(dataclasses.replace(p, spec_quality=s))["p_star"]}
                  for s in (0.3, 0.5, 0.7, 0.9, 0.99)]
    verif_sweep = [{"verification": v, "p_star": optimal_pressure(dataclasses.replace(p, verification=v))["p_star"]}
                   for v in (0.0, 0.3, 0.6, 0.9)]
    # grounded by the oversight experiment: oversight_error ~0 (capable) .. 0.5 (huge gap)
    oversight_sweep = [{"oversight_error": oe,
                        "p_star": optimal_pressure(dataclasses.replace(p, oversight_error=oe))["p_star"]}
                       for oe in (0.0, 0.2, 0.5, 0.9)]
    # AI-2027 race: capability p runs past p* while spec+verification are fixed
    over = round(1.8 * opt["p_star"], 3)
    race = {"p_star": opt["p_star"], "raced_to": over,
            "value_at_p_star": opt["true_value_at_p_star"],
            "value_when_raced": round(true_value(p, over), 4)}
    return {
        "params": dataclasses.asdict(p),
        "optimum": opt,
        "true_value_curve": curve,
        "p_star_vs_spec_quality": spec_sweep,
        "p_star_vs_verification": verif_sweep,
        "p_star_vs_oversight_error": oversight_sweep,
        "race_overshoot": race,
        "falsifier": "true_value が p で単調（peak 無し）／p* が spec・検証に依存しないなら、"
                     "「整合＝仕様+検証が能力を上限づける」は本モデル下で偽。",
    }


def _md(r: dict) -> str:
    o = r["optimum"]
    race = r["race_overshoot"]
    L = ["# F7 整合の形式化 — 仕様+検証が能力（最適化圧）を上限づける",
         "",
         "「管理 → 仕様+検証+監督」を測れる形に。AI は spec を最適化するので、spec gap があると"
         "強い最適化が真の目的を悪化させる（Goodhart）。検証がその一部を捕捉。生数値 "
         "[`alignment_results.json`](alignment_results.json)。",
         "",
         f"## 主結果: 最適な最適化圧 p\\* = {o['p_star']}（内点: {o['interior']}）",
         "p\\* を超えて能力を強めると真の価値は**下がる**（Goodhart）。＝能力は無制限に上げてよくない。",
         "",
         "## p\\* は spec品質とともに上がる（良い仕様ほど強く最適化して安全）",
         "| spec_quality | p\\* |", "|---|---|"]
    for s in r["p_star_vs_spec_quality"]:
        L.append(f"| {s['spec_quality']} | {s['p_star']} |")
    L += ["", "## p\\* は検証とともに上がる / oversight_error とともに下がる", "",
          "| verification | p\\* | | oversight_error | p\\* |", "|---|---|---|---|---|"]
    vs, os_ = r["p_star_vs_verification"], r["p_star_vs_oversight_error"]
    for i in range(max(len(vs), len(os_))):
        a = vs[i] if i < len(vs) else {"verification": "", "p_star": ""}
        b = os_[i] if i < len(os_) else {"oversight_error": "", "p_star": ""}
        L.append(f"| {a['verification']} | {a['p_star']} | | {b['oversight_error']} | {b['p_star']} |")
    L += ["",
          "→ **能力は、仕様+検証が追いつく範囲までしか安全に上げられない**。これが「整合＝仕様+検証+監督」"
          "の定量形。oversight_error は実測（`experiments/oversight/` ~0〜0.5）で接地。",
          "",
          "## AI-2027 のレース（能力が p\\* を追い越す）",
          f"- spec+検証を固定したまま能力を p\\*={race['p_star']} → {race['raced_to']} に上げると、"
          f"真の価値は {race['value_at_p_star']} → **{race['value_when_raced']}** に**崩れる**。",
          "- ＝能力だけ先行（race.py の Race）すると整合が破れ、真の目的が悪化する。"
          "整合は能力と*同率で*仕様+検証を上げて初めて保たれる。",
          "",
          "## 反証手段・妥当性",
          f"- 反証: {r['falsifier']}",
          "- gain 飽和・Goodhart 超線形・捕捉線形は第一原理的だが*仮定*。結論は質的（p\\* の存在と、"
          "spec/検証への単調依存）＋感度で読む。spec gap と Goodhart 指数は実測すべき経験量。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "alignment_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "ALIGNMENT.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    o, race = r["optimum"], r["race_overshoot"]
    print(f"optimal optimization pressure p* = {o['p_star']} (true_value {o['true_value_at_p_star']})")
    print("p* vs spec_quality:", {s["spec_quality"]: s["p_star"] for s in r["p_star_vs_spec_quality"]})
    print(f"race overshoot: value {race['value_at_p_star']} (at p*) -> {race['value_when_raced']} (raced)")
    print(f"\nwrote {os.path.join(out_dir, 'alignment_results.json')} and ALIGNMENT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
