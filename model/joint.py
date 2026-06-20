"""joint — 構造選択と統治膜を *結合* して最適化し、design_map の分離可能性を反証する。

design_map は「構造（効率）と膜（監督）はほぼ独立」と仮定した。だが**構造によって膜の
張りやすさが違う**はず: 階層は判断が管理者に集中し監査・ゲートしやすい（膜が安い）；
市場は判断が多数の入札に分散し人間可読な膜を張りにくい（膜が高い）。flat は中間。

そこで構造ごとに膜の効率コストを `gov_factor` で重み付けし、各タスク profile で
(構造, 膜厚 m) を**同時に**最小化する。分離最適（design_map）と結合最適が食い違えば、
**分離可能性は偽**＝高 stakes では「統治しやすい構造」が効率を多少犠牲にして選ばれうる。

    結合総コスト(s) = 調整コスト(s, c_comm, 密度) + 統治損失(s, m*_s, stakes)
       ただし 統治損失の効率税 c_mem は gov_factor[s] 倍

run: python3 -m model.joint
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.coordination import Params, STRUCTURES, costs, winner    # noqa: E402
from model.governance import GovParams, optimal_membrane, total_loss  # noqa: E402


# How costly each structure is to wrap in a human-legible governance membrane.
# Concentrated decision points (hierarchy) are cheap to audit/gate; dispersed
# ones (market) are expensive. This is the cross-axis coupling design_map ignored.
GOV_FACTOR = {"hierarchy": 0.7, "flat": 1.0, "market": 1.5}


def joint_optimum(c_comm: float, stakes: float, density: float = 0.4,
                  base_gov: GovParams | None = None) -> dict:
    base_gov = base_gov or GovParams(stakes=stakes)
    coord = costs(Params(density=density), c_comm)
    best = None
    per_structure = {}
    for s in STRUCTURES:
        gp = dataclasses.replace(base_gov, stakes=stakes, c_mem=base_gov.c_mem * GOV_FACTOR[s])
        m = optimal_membrane(gp)["m_star"]
        gov_loss = total_loss(gp, m)["total"]
        total = round(coord[s]["total"] + gov_loss, 4)
        per_structure[s] = {"coord": coord[s]["total"], "membrane_m": m,
                            "gov_loss": gov_loss, "total": total}
        if best is None or total < per_structure[best]["total"]:
            best = s
    return {"joint_structure": best, "joint_membrane_m": per_structure[best]["membrane_m"],
            "per_structure": per_structure}


def compare(c_comm: float, stakes: float, density: float = 0.4) -> dict:
    sep_struct = winner(Params(density=density), c_comm)[0]      # design_map (separable)
    sep_m = optimal_membrane(GovParams(stakes=stakes))["m_star"]
    j = joint_optimum(c_comm, stakes, density)
    return {"c_comm": c_comm, "stakes": stakes,
            "separable": {"structure": sep_struct, "membrane_m": sep_m},
            "joint": {"structure": j["joint_structure"], "membrane_m": j["joint_membrane_m"]},
            "separability_holds": sep_struct == j["joint_structure"]}


def run(density: float = 0.4) -> dict:
    c_regimes = {"human≈3.0": 3.0, "transition≈1.0": 1.0, "AI≈0.1": 0.1}
    stakes_levels = {"low≈0.8": 0.8, "mid≈8": 8.0, "high≈40": 40.0}
    grid = []
    breaks = 0
    for s_name, s in stakes_levels.items():
        row = {"stakes": s_name, "cells": {}}
        for c_name, c in c_regimes.items():
            cmp = compare(c, s, density)
            row["cells"][c_name] = cmp
            if not cmp["separability_holds"]:
                breaks += 1
        grid.append(row)
    return {"density": density, "gov_factor": GOV_FACTOR,
            "c_regimes": c_regimes, "stakes_levels": stakes_levels,
            "grid": grid, "separability_breaks": breaks,
            "n_cells": len(c_regimes) * len(stakes_levels),
            "finding": ("結合最適が分離最適と食い違うセルの数。>0 なら design_map の"
                        "分離可能性は偽＝統治しやすさが構造選択に効く。")}


def _md(r: dict) -> str:
    cols = list(r["c_regimes"])
    L = ["# 結合最適 — 構造×統治膜の分離可能性を反証する",
         "",
         f"design_map の「構造と膜は独立」を検証。構造ごとの膜の張りにくさ gov_factor="
         f"{r['gov_factor']}（階層=集中で安い／市場=分散で高い）を入れ、(構造, 膜) を同時最適化。"
         f"密度 ρ={r['density']}。生数値 [`joint_results.json`](joint_results.json)。",
         "",
         f"## 主結果: 分離可能性が破れたセル = **{r['separability_breaks']} / {r['n_cells']}**",
         "",
         "各セル = 分離最適の構造 → 結合最適の構造（★=食い違い）。",
         "",
         "| stakes \\ 通信 | " + " | ".join(cols) + " |",
         "|" + "---|" * (len(cols) + 1)]
    for row in r["grid"]:
        cells = []
        for c in cols:
            cell = row["cells"][c]
            sep, joint = cell["separable"]["structure"], cell["joint"]["structure"]
            mark = "" if cell["separability_holds"] else " ★"
            cells.append(f"{sep}→{joint}{mark}")
        L.append(f"| **{row['stakes']}** | " + " | ".join(cells) + " |")
    L += ["",
          "## 読み",
          "- ★のセルでは、**統治しやすさが効率を上書きする** — 効率最適でない構造が、膜が安いがゆえに結合では選ばれる。",
          "- 典型: 高 stakes（厚い膜が要る）で、市場のように膜が高くつく構造が、より統治しやすい構造に負ける。",
          f"- ★が1つでもあれば design_map の**分離可能性は偽**（本モデル下）。今回 {r['separability_breaks']} 個。",
          "",
          "## 妥当性",
          "- gov_factor は第一原理的だが*仮定*（集中度↔統治しやすさ）。結論は質的（分離が破れうる・破れる向き）＋感度で読む。",
          "- 調整コストと統治損失は同一の抽象コスト単位として加算。相対スケールは仮定。",
          "- [`../docs/foundations.md`](../docs/foundations.md) §5 の「最適性 vs 可読性」が、構造選択そのものに食い込むことを示す。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "joint_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "JOINT.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print(f"separability breaks in {r['separability_breaks']}/{r['n_cells']} cells")
    for row in r["grid"]:
        cells = "  ".join(
            f"{row['cells'][c]['separable']['structure']:>9}->{row['cells'][c]['joint']['structure']:<9}"
            f"{'*' if not row['cells'][c]['separability_holds'] else ' '}"
            for c in r["c_regimes"])
        print(f"  {row['stakes']:<10} {cells}")
    print(f"\nwrote {os.path.join(out_dir, 'joint_results.json')}")
    print(f"wrote {os.path.join(out_dir, 'JOINT.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
