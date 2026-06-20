"""design_map — 二つの計測を合成した処方マップ。

第一の計測（[`coordination.py`](coordination.py)）は「通信コスト→最適構造」を、
第二（[`governance.py`](governance.py)）は「stakes→統治膜の厚み」を測った。両者は
ほぼ独立な軸（構造＝効率 / 膜＝監督）なので、合成して

    タスク profile (c_comm 域, 密度, stakes) → 推奨(構造, 膜の厚み m*)

を返す処方マップを作る。これは研究の暫定テーゼ「AIネイティブ機構＋薄い人間統治膜」を、
具体的なタスク条件に対する**設計推奨**へ落とした最初の形。

注意（妥当性）: 構造選択と膜の厚みを**分離可能**と仮定（第一近似）。実際は相互作用が
ありうる（例: 市場構造は監督点が分散し膜を張りにくい）。これは次の計測で検証すべき。
run: python3 -m model.design_map
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.coordination import Params, winner            # noqa: E402
from model.governance import GovParams, optimal_membrane  # noqa: E402


_C_COMM_REGIMES = {"human≈3.0": 3.0, "transition≈1.0": 1.0,
                   "AI≈0.1": 0.1, "deep-AI≈0.03": 0.03}
_STAKES_LEVELS = {"low≈0.8": 0.8, "mid≈8": 8.0, "high≈40": 40.0}


def recommend(c_comm: float, stakes: float, density: float = 0.4) -> dict:
    struct, _ = winner(Params(density=density), c_comm)
    gov = optimal_membrane(GovParams(stakes=stakes))
    return {"structure": struct, "membrane_m_star": gov["m_star"],
            "membrane_regime": gov["regime"]}


def run(density: float = 0.4) -> dict:
    grid = []
    for s_name, s in _STAKES_LEVELS.items():
        row = {"stakes": s_name, "cells": {}}
        for c_name, c in _C_COMM_REGIMES.items():
            row["cells"][c_name] = recommend(c, s, density)
        grid.append(row)
    return {"density": density, "c_comm_regimes": _C_COMM_REGIMES,
            "stakes_levels": _STAKES_LEVELS, "grid": grid,
            "assumption": "構造選択と膜の厚みは分離可能と仮定（第一近似）。"}


def _md(r: dict) -> str:
    cols = list(r["c_comm_regimes"])
    L = ["# 処方マップ — タスク条件 → 推奨(構造, 統治膜)",
         "",
         f"二つの計測の合成（密度 ρ={r['density']} 固定）。各セル = (推奨構造 / 膜の厚み m*)。",
         "",
         "| stakes \\ 通信コスト | " + " | ".join(cols) + " |",
         "|" + "---|" * (len(cols) + 1)]
    for row in r["grid"]:
        cells = " | ".join(f"{c['structure']} / m*={c['membrane_m_star']}"
                           for c in (row["cells"][c] for c in cols))
        L.append(f"| **{row['stakes']}** | {cells} |")
    L += ["",
          "## 読み",
          "- 横（通信コスト低下＝AI化）: 構造は **hierarchy → market → flat** へ（第一の計測）。",
          "- 縦（stakes 上昇）: 統治膜 **m* が 0 → 部分 → 1** へ厚くなる（第二の計測）。",
          "- 右下（AI域・高 stakes）= **平ら/市場な機構に厚い統治膜** ＝ テーゼ「AIネイティブ機構＋人間統治膜」の具体形。",
          "- 左上（人間域・低 stakes）= 階層で膜不要、という*人間組織の既定*に一致（モデルの sanity check）。",
          "",
          f"## 妥当性\n- {r['assumption']} 実際は相互作用がありうる（市場は監督点が分散し膜を張りにくい等）→ **検証済み（[`JOINT.md`](JOINT.md)）: 高 stakes で分離が破れる（市場→階層、1/9 セル）**。",
          "- 各軸の限界は [`first-measurement.md`](../docs/first-measurement.md) / [`second-measurement.md`](../docs/second-measurement.md) を参照。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "design_map_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "DESIGN_MAP.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    cols = list(r["c_comm_regimes"])
    print("処方マップ (構造 / m*)   " + "  ".join(f"{c:>14}" for c in cols))
    for row in r["grid"]:
        cells = "  ".join(f"{c['structure']:>9}/{c['membrane_m_star']:<4}"
                          for c in (row["cells"][c] for c in cols))
        print(f"  {row['stakes']:<10} {cells}")
    print(f"\nwrote {os.path.join(out_dir, 'design_map_results.json')}")
    print(f"wrote {os.path.join(out_dir, 'DESIGN_MAP.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
