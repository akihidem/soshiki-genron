"""sweep — 計測の実験。c_comm（と密度）を掃引し、構造の交差点・相図を測る。

各構造の総コストは c_comm の一次関数（total = slope·c_comm + const）なので、交差点は
解析的に c* = (const_b - const_a) / (slope_a - slope_b) で厳密に出る。掃引は可視化用。

出力: 標準出力の表 + model/RESULTS.md + model/results.json（決定的・2回で一致）。
run: python3 -m model.sweep
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.coordination import (  # noqa: E402
    Params, STRUCTURES, costs, winner, cost_flat, cost_hierarchy, cost_market,
)

_FN = {"flat": cost_flat, "hierarchy": cost_hierarchy, "market": cost_market}
_INIT = {"flat": "F", "hierarchy": "H", "market": "M"}


def _line(p: Params, name: str) -> tuple[float, float]:
    """(slope, const) of a structure's total cost in c_comm (it is affine)."""
    fn = _FN[name]
    const = fn(p, 0.0)["total"]
    slope = round(fn(p, 1.0)["total"] - const, 6)
    return slope, const


def crossover(p: Params, a: str, b: str) -> float | None:
    """c_comm where a and b cost the same; None if they never cross at c_comm>0."""
    sa, ca = _line(p, a)
    sb, cb = _line(p, b)
    if abs(sa - sb) < 1e-12:
        return None
    c = (cb - ca) / (sa - sb)
    return round(c, 5) if c > 0 else None


def logspace(lo: float, hi: float, n: int) -> list[float]:
    if n == 1:
        return [hi]
    step = (math.log(hi) - math.log(lo)) / (n - 1)
    return [round(math.exp(math.log(hi) - step * i), 5) for i in range(n)]


def sweep_1d(p: Params, c_values: list[float]) -> list[dict]:
    out = []
    for c in c_values:
        cs = costs(p, c)
        w, t = winner(p, c)
        out.append({"c_comm": c, "winner": w,
                    "totals": {k: cs[k]["total"] for k in STRUCTURES}})
    return out


def phase_2d(p: Params, c_values: list[float], density_values: list[float]) -> list[dict]:
    rows = []
    for d in density_values:
        pd = dataclasses.replace(p, density=d)
        rows.append({"density": d,
                     "row": [winner(pd, c)[0] for c in c_values]})
    return rows


def sensitivity_crossover(p: Params, param: str, values: list[float],
                          a: str = "flat", b: str = "hierarchy") -> list[dict]:
    out = []
    for v in values:
        pv = dataclasses.replace(p, **{param: v})
        out.append({param: v, "crossover_c_comm": crossover(pv, a, b)})
    return out


def regime_order(p: Params, c_hi: float, c_lo: float) -> list[dict]:
    """As c_comm falls from c_hi to c_lo, the sequence of winning regimes and the
    c_comm at each handover."""
    cs = sorted({c for a in STRUCTURES for b in STRUCTURES if a < b
                 for c in [crossover(p, a, b)] if c and c_lo < c < c_hi}, reverse=True)
    boundaries = [c_hi] + cs + [c_lo]
    seq = []
    for i in range(len(boundaries) - 1):
        mid = math.sqrt(boundaries[i] * boundaries[i + 1])  # geometric midpoint
        seq.append({"c_comm_from": boundaries[i], "c_comm_to": boundaries[i + 1],
                    "winner": winner(p, mid)[0]})
    return seq


def run(p: Params | None = None) -> dict:
    p = p or Params()
    c_hi, c_lo, n = 5.0, 0.02, 19
    c_values = logspace(c_lo, c_hi, n)                       # high -> low
    density_values = [round(0.1 * k, 2) for k in (2, 4, 6, 8)]

    cross_fh = crossover(p, "flat", "hierarchy")
    cross_fm = crossover(p, "flat", "market")
    cross_hm = crossover(p, "hierarchy", "market")

    p_same = dataclasses.replace(p, same_error=True)         # isolate coordination effect

    return {
        "params": dataclasses.asdict(p),
        "headline": {
            "flat_vs_hierarchy_crossover_c_comm": cross_fh,
            "interpretation": (
                "同条件で c_comm がこの値より高いと hierarchy が flat を上回り、低いと flat が上回る。"
                "3構造すべての勝敗は密度依存で相図参照（高 c_comm=階層 / 中=平ら / 極低=市場）。"
                "tehai の A/B（1点観測で flat 有利）を曲線へ一般化し、交差点を測った。"),
        },
        "regime_sequence_as_c_comm_falls": regime_order(p, c_hi, c_lo),
        "crossovers": {"flat_hierarchy": cross_fh, "flat_market": cross_fm,
                       "hierarchy_market": cross_hm},
        "sweep_1d": sweep_1d(p, c_values),
        "phase_2d": {"c_values": c_values, "rows": phase_2d(p, c_values, density_values)},
        "sensitivity_mgr_overhead": sensitivity_crossover(
            p, "mgr_overhead", [0.0, 1.0, 2.0, 4.0, 8.0]),
        "isolate_coordination_only": {
            "note": "same_error=True で検証軸を中立化し、純粋な調整コストだけの交差点。",
            "flat_vs_hierarchy_crossover_c_comm": crossover(p_same, "flat", "hierarchy"),
        },
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _phase_ascii(report: dict) -> str:
    cv = report["phase_2d"]["c_values"]
    lines = ["density \\ c_comm  " + "  ".join(f"{c:>5.2f}" for c in cv)]
    for row in report["phase_2d"]["rows"]:
        cells = "      ".join(_INIT[w] for w in row["row"])
        lines.append(f"  ρ={row['density']:<4}        {cells}")
    lines.append("  (H=hierarchy  F=flat  M=market) — c_comm 高 → 低")
    return "\n".join(lines)


def _fmt(report: dict) -> str:
    L = []
    fh = report["headline"]["flat_vs_hierarchy_crossover_c_comm"]
    L.append(f"flat↔hierarchy 交差点  c_comm* = {fh}")
    L.append("  → これより高コスト通信では hierarchy、安いと flat が勝つ\n")
    L.append("c_comm が下がるときの勝者の系列:")
    for s in report["regime_sequence_as_c_comm_falls"]:
        L.append(f"  c_comm {s['c_comm_from']:>6} → {s['c_comm_to']:<6} : {s['winner']}")
    L.append("\n2D 相図:")
    L.append(_phase_ascii(report))
    L.append("\nmgr_overhead 感度（flat↔hierarchy 交差点）:")
    for s in report["sensitivity_mgr_overhead"]:
        L.append(f"  mgr_overhead={s['mgr_overhead']:<4} -> c_comm* = {s['crossover_c_comm']}")
    iso = report["isolate_coordination_only"]["flat_vs_hierarchy_crossover_c_comm"]
    L.append(f"\n検証軸を中立化（純調整コストのみ）の交差点: c_comm* = {iso}")
    return "\n".join(L)


def _results_md(report: dict) -> str:
    fh = report["headline"]["flat_vs_hierarchy_crossover_c_comm"]
    iso = report["isolate_coordination_only"]["flat_vs_hierarchy_crossover_c_comm"]
    M = []
    M.append("# 第一の計測 — 通信コストと最適な組織構造")
    M.append("")
    M.append("研究の問いを計測可能化: **「通信コスト c_comm が下がると、コスト最小の調整構造は "
             "階層→平ら→市場へ動くか」**（[`../docs/foundations.md`](../docs/foundations.md) F3 ＋ "
             "Malone「調整コスト低下→市場化」）。決定的モデル（`model/coordination.py`）を c_comm で掃引。")
    M.append("")
    M.append("## 主結果")
    M.append(f"- **flat↔hierarchy 交差点 c_comm\\* = {fh}**。これより通信が高コストなら **hierarchy**、"
             "安いなら **flat** が最小コスト。tehai の A/B（1点で flat 有利）を**曲線**へ一般化し、交差点を測った。")
    seq = " → ".join(f"{s['winner']}" for s in report["regime_sequence_as_c_comm_falls"])
    M.append(f"- c_comm を高→低に動かすと勝者は **{seq}** と推移（Malone の予測と整合：調整コストが下がると階層→市場へ）。")
    M.append(f"- **検証軸を中立化**しても（`same_error=True`）交差点は c_comm\\*={iso} に残る "
             "→ flat 優位の一部は純粋な調整コスト由来で、盲点流出（検証）由来と分離できる。")
    M.append("")
    M.append("## 2D 相図（どの領域でどの構造が勝つか）")
    M.append("```")
    M.append(_phase_ascii(report))
    M.append("```")
    M.append("")
    M.append("## 感度分析（結果は仮定に依存することを明示）")
    M.append("`mgr_overhead`（管理者の構造コスト）を動かすと flat↔hierarchy 交差点が動く:")
    M.append("")
    M.append("| mgr_overhead | 交差点 c_comm\\* |")
    M.append("|---|---|")
    for s in report["sensitivity_mgr_overhead"]:
        M.append(f"| {s['mgr_overhead']} | {s['crossover_c_comm']} |")
    M.append("")
    M.append("→ **mgr_overhead=0 だと階層は負けない**（交差点が消える/上端へ）。つまり "
             "「階層は通信が安いと惰性」という主張は、*管理者に通信非依存のオーバーヘッドがある*という"
             "経験的前提に懸かる。これは ② で（あるいは実組織データで）測るべき量。")
    M.append("")
    M.append("## 反証手段（第一原理）")
    M.append("- mgr_overhead>0 でも交差点が現れない／c_comm を下げても hierarchy が負けない、なら F3 は偽。")
    M.append("- market が低 c_comm 域で決して勝たない、なら Malone の市場化予測は本モデルの想定下で偽。")
    M.append("")
    M.append("## 妥当性の限界")
    M.append("- これは**決定的な解析モデル**。通信量・オーバーヘッド・誤りの各係数は第一原理的だが*仮定*。"
             "結果は質的主張（交差点の存在と向き）＋パラメタ依存（感度）として読む。単一の数値を絶対視しない。")
    M.append("- 構造は3つの純粋型に限定（実組織は混合）。エージェント容量の有界性は未モデル（AIでは緩いと仮定）。")
    M.append("- tehai の A/B（実コードの2点観測）と本モデル（解析の曲線）は**独立の経路**。両者が同じ向き"
             "（通信が安いと flat 有利）を示すのは弱い相互裏取り。")
    return "\n".join(M)


def main(argv=None) -> int:
    report = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write(_results_md(report) + "\n")
    print(_fmt(report))
    print(f"\nwrote {os.path.join(out_dir, 'results.json')}")
    print(f"wrote {os.path.join(out_dir, 'RESULTS.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
