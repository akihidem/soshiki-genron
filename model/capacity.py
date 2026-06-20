r"""容量制約モデル — エージェントの処理上限が最適な分解粒度を決める（F1）。

March & Simon の限定合理性 / Galbraith。目標の総作業 W を g 個に分解する。各片の
負荷は W/g。エージェント容量 κ を超える片は過負荷（誤り/遅延）。細かく割れば過負荷は
減るが、片が増えて調整（通信）が増える —— 分解粒度のトレードオフ。

    総コスト(g) = 過負荷(g) + 調整(g)
              = oc·max(0, W − κ·g)              （容量超過分の総量）
              + c_comm·ρ·g(g−1)/2               （片どうしの調整辺）

最適粒度 g\* を測る。核心の予言（F1）:
- 容量 κ が上がる（AI）→ 最適 g\* は**小さく**＝**粗い分解**（"人の職サイズ" は AI の自然単位でない）。
- 通信が安い → やや細かく割れるが、AI 域（高 κ・低 c_comm）では正味**粗い** → 片が少なく調整辺も少ない
  → flat を後押し（第一の計測 F3 と接続）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CapParams:
    work: float = 100.0      # total work units in the goal
    kappa: float = 10.0      # per-agent processing capacity
    overload_cost: float = 1.0   # cost per work-unit above capacity
    c_comm: float = 0.1      # communication cost per coordination edge (AI regime: cheap)
    density: float = 0.4     # interdependency density among pieces
    g_max: int = 60          # max pieces considered


def total_cost(p: CapParams, g: int) -> dict:
    g = max(1, g)
    overload = p.overload_cost * max(0.0, p.work - p.kappa * g)
    coordination = p.c_comm * p.density * g * (g - 1) / 2.0
    return {"g": g, "overload": round(overload, 4),
            "coordination": round(coordination, 4),
            "total": round(overload + coordination, 4)}


def optimal_granularity(p: CapParams) -> dict:
    best = min(range(1, p.g_max + 1), key=lambda g: total_cost(p, g)["total"])
    tc = total_cost(p, best)
    return {"g_star": best, "piece_size": round(p.work / best, 3),
            "covers_capacity": p.work / best <= p.kappa,
            "min_pieces_for_capacity": math.ceil(p.work / p.kappa),
            "total": tc["total"]}


import dataclasses  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402


def run(p: CapParams | None = None) -> dict:
    p = p or CapParams()
    kappa_sweep = [{"kappa": k, **{kk: optimal_granularity(dataclasses.replace(p, kappa=k))[kk]
                                   for kk in ("g_star", "piece_size")}}
                   for k in (2.0, 5.0, 10.0, 20.0, 50.0, 100.0)]
    ccomm_sweep = [{"c_comm": c, "g_star": optimal_granularity(dataclasses.replace(p, c_comm=c))["g_star"]}
                   for c in (0.05, 0.2, 0.5, 1.0, 3.0, 8.0)]
    return {
        "params": dataclasses.asdict(p),
        "optimum_at_default": optimal_granularity(p),
        "g_star_vs_capacity": kappa_sweep,
        "g_star_vs_c_comm": ccomm_sweep,
        "claim": "容量 κ が上がるほど最適粒度 g* は小さく（粗く）なる＝AIの高容量は粗い分解を最適化する。",
        "falsifier": "κ を上げても g* が下がらない／c_comm を上げても g* が下がらない、なら本モデル下で F1 の含意は偽。",
    }


def _md(r: dict) -> str:
    opt = r["optimum_at_default"]
    L = ["# 第三の計測 — 容量制約と最適な分解粒度（F1）",
         "",
         "研究の問いを計測可能化: **エージェント容量 κ が上がると最適な分解粒度 g\\* はどう動くか**"
         "（[`../docs/foundations.md`](../docs/foundations.md) F1 / 限定合理性）。生数値は "
         "[`capacity_results.json`](capacity_results.json)。",
         "",
         "## 主結果",
         f"- 既定で g\\* = {opt['g_star']}（片サイズ {opt['piece_size']}、容量を満たす最小片数 "
         f"{opt['min_pieces_for_capacity']}）。通信が安いと g\\* ≈ 容量を満たす最小片数。",
         "- **容量 κ が上がると g\\* は小さく（粗く）なる**:"]
    L.append("")
    L.append("| 容量 κ | 最適粒度 g\\* | 片サイズ |")
    L.append("|---|---|---|")
    for s in r["g_star_vs_capacity"]:
        L.append(f"| {s['kappa']} | {s['g_star']} | {s['piece_size']} |")
    L += ["",
          "→ **AI＝高容量 → 粗い分解**（少ない片）。「人の職サイズ」の細かい単位は AI の自然単位ではない。",
          "",
          "## 通信コスト感度", "",
          "| c_comm | 最適粒度 g\\* |", "|---|---|"]
    for s in r["g_star_vs_c_comm"]:
        L.append(f"| {s['c_comm']} | {s['g_star']} |")
    L += ["",
          "→ 通信が高いほど g\\* は小さい（調整を避けるため過負荷を許容してでも粗く割る）。",
          "AI 域（高 κ・低 c_comm）は正味**粗い分解 → 片が少なく調整辺も少ない → flat を後押し**（F3 と接続）。",
          "",
          "## 反証手段・妥当性",
          f"- 反証: {r['falsifier']}",
          "- 過負荷コスト線形・調整は片数の二乗、と仮定。係数は第一原理的だが*仮定*。"
          "結論は質的（g\\* が κ で単調減少）＋感度として読む。κ（AIの実効容量）は ② か実測で。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "capacity_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "CAPACITY.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print(f"optimal granularity g* = {r['optimum_at_default']['g_star']} at default")
    print("g* vs capacity κ (higher κ -> coarser):")
    for s in r["g_star_vs_capacity"]:
        print(f"  κ={s['kappa']:>6}  g*={s['g_star']:>3}  piece={s['piece_size']}")
    print(f"\nwrote {os.path.join(out_dir, 'capacity_results.json')}")
    print(f"wrote {os.path.join(out_dir, 'CAPACITY.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
