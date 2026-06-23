r"""mesh.py — *合議 mesh*（独立に解いて union）が単体最強を超える臨界点。

[`market.py`](market.py) は **escalation 市場**が flat-strong を支配する閾値 **p > w/s**（＝*コスト*の問題）を
導いた。本ファイルはその対になる **mesh**（同タスクを n エージェントが独立に解き、外部検証で通った解を取る
＝union）が *best-single* を超える臨界を導く ── これは *脱相関*（errors のバラけ）の問題である。

n エージェント・各完全解率 p・失敗の相関 ρ（exchangeable 一因子モデル：確率 ρ で全員が同じ結果＝
comonotone、確率 1−ρ で独立）:
    P(all fail) = ρ·q + (1−ρ)·q^n            （q = 1−p）
    union 正しさ = 1 − P(all fail)
    best single  = p
  ⟹ **mesh 利得 = union − p = (1−ρ)·(1−p)·(1 − (1−p)^{n−1})**

**臨界**: 利得 > 0 ⟺ **ρ < 1**（脱相関がある）かつ 0 < p < 1 かつ n ≥ 2。
  ρ = 1（完全相関＝失敗が入れ子/共通 hard core）→ 利得 0 ＝ **市場支配**（単一最強で足りる）。
  冗長 mesh 実証で測った gain≈0 は「**ρ≈1 の点**」＝errors が hard core を共有していた、と統一できる。
  脱相関 1−ρ が mesh の燃料。n→∞ でも利得は (1−ρ)(1−p) で頭打ち（相関と素の難度が天井）。

**コスト調整**: mesh コスト = n·(w+verify)。weak エージェントの mesh が flat-strong（正しさ 1・コスト s）を
*Pareto 支配*するには union→1（ρ 小 かつ n 大）かつ n·(w+verify) < s が要る。weak で正しさ 1 に届かせる
コストが s を超えやすく、**mesh が strong を置き換えるのは稀**（mesh の本領は「縁」での補完であって置換でない）。

決定的（解析・stdlib のみ）。 run: python3 -m model.mesh
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass


@dataclass
class MeshParams:
    p: float = 0.5          # per-agent full-solve rate
    rho: float = 0.0        # failure correlation (0=independent, 1=comonotone/nested)
    n: int = 2              # number of agents in the mesh
    w: float = 0.2          # per-agent (weak) cost
    s: float = 1.0          # flat-strong cost (single model that solves all, correctness 1)
    verify: float = 0.1     # external-verify cost per attempt (mesh's backbone)


def p_all_fail(p: float, rho: float, n: int) -> float:
    """P(every one of n agents fails), one-factor exchangeable model. ρ=1 comonotone, ρ=0 independent."""
    q = 1.0 - p
    return rho * q + (1.0 - rho) * (q ** n)


def mesh_correctness(p: float, rho: float, n: int) -> float:
    """Union correctness: external verify keeps any passing answer -> solved iff ANY agent solves."""
    return round(1.0 - p_all_fail(p, rho, n), 6)


def mesh_gain(p: float, rho: float, n: int) -> float:
    """union − best_single = (1−ρ)·(1−p)·(1 − (1−p)^{n−1}). >0 iff ρ<1, 0<p<1, n≥2."""
    if n < 1:
        return 0.0
    return round((1.0 - rho) * (1.0 - p) * (1.0 - (1.0 - p) ** (n - 1)), 6)


def ignites(p: float, rho: float, n: int) -> bool:
    """mesh の union が best-single を*厳密に*超える（脱相関の点火条件）。"""
    return mesh_gain(p, rho, n) > 1e-9


def mesh_cost(n: int, w: float, verify: float) -> float:
    """Run n weak agents + verify each (external verification is the backbone)."""
    return round(n * (w + verify), 6)


def dominates_strong(p: float, rho: float, n: int, w: float, s: float, verify: float,
                     target: float = 1.0, eps: float = 1e-9) -> bool:
    """Weak-agent mesh Pareto-dominates flat-strong: reaches strong's correctness cheaper."""
    return mesh_correctness(p, rho, n) >= target - eps and mesh_cost(n, w, verify) < s - eps


def min_agents_to_match_strong(p: float, rho: float, w: float, s: float, verify: float,
                               target: float = 0.99, n_max: int = 64):
    """Smallest n whose mesh reaches `target` correctness AND costs < s; None if unreachable within budget.
    Returns the n and whether it cost-dominates strong (correctness reached may still cost >= s)."""
    for n in range(2, n_max + 1):
        if mesh_correctness(p, rho, n) >= target - 1e-9:
            return {"n": n, "cost": mesh_cost(n, w, verify), "cost_dominates_strong": mesh_cost(n, w, verify) < s}
    return {"n": None, "cost": None, "cost_dominates_strong": False}


def run(prm: "MeshParams | None" = None) -> dict:
    prm = prm or MeshParams()
    p, rho, n, w, s, verify = prm.p, prm.rho, prm.n, prm.w, prm.s, prm.verify
    base = {"mesh_correctness": mesh_correctness(p, rho, n), "best_single": round(p, 6),
            "mesh_gain": mesh_gain(p, rho, n), "ignites": ignites(p, rho, n),
            "mesh_cost": mesh_cost(n, w, verify), "flat_strong_cost": s,
            "dominates_strong": dominates_strong(p, rho, n, w, s, verify)}

    # ① 脱相関スイープ: ρ を 1→0 に下げると利得が 0 から立ち上がる（臨界 ρ*=1・燃料は 1−ρ）
    rho_grid = [round(1.0 - 0.1 * i, 1) for i in range(11)]            # 1.0,0.9,...,0.0
    rho_sweep = [{"rho": r, "gain": mesh_gain(p, r, n), "union": mesh_correctness(p, r, n),
                  "ignites": ignites(p, r, n)} for r in rho_grid]

    # ② エージェント数スイープ（脱相関 ρ=0 固定）: union は 1−(1−p)^n に近づくが利得は (1−p) で頭打ち
    n_sweep = [{"n": k, "gain": mesh_gain(p, 0.0, k), "union": mesh_correctness(p, 0.0, k)}
               for k in range(1, 9)]

    # ③ コスト調整の臨界: weak mesh が flat-strong(正しさ1) に届く最小 n と、それが s より安いか
    cost_cross = [{"rho": r, **min_agents_to_match_strong(p, r, w, s, verify, target=0.99)}
                  for r in (0.0, 0.3, 0.6, 0.9)]

    # ④ 実測レジームを ρ 軸上の点として配置（本リポの mesh 実証を統一）
    regimes = [
        {"regime": "冗長並列 mesh（実測 gain≈0）", "rho": 1.0, "n": 3,
         "note": "frontier の errors は入れ子/共通 hard core＝ρ≈1→利得0。5角度すべて不点火＝市場支配。"},
        {"regime": "config 散らし（B−A≈0）", "rho": 1.0, "n": 4,
         "note": "framing を変えても hard core は割れず脱相関できない＝ρ≈1。多様性の寄与は負。"},
        {"regime": "meshflow edge demo（構成で相補）", "rho": 0.0, "n": 3,
         "note": "各ティアが*別の部分*を解くよう構成＝ρ=0→union 点火（gain>0）。real でなく構成。"},
    ]
    for rg in regimes:
        rg["gain"] = mesh_gain(p, rg["rho"], rg["n"])
        rg["ignites"] = ignites(p, rg["rho"], rg["n"])

    return {
        "params": dataclasses.asdict(prm),
        "base": base,
        "gain_formula": "mesh 利得 = (1−ρ)·(1−p)·(1 − (1−p)^{n−1})",
        "critical_point": "利得 > 0 ⟺ ρ < 1（脱相関がある）。ρ=1（入れ子/共通 hard core）で利得 0 ＝ 市場支配。",
        "rho_sweep": rho_sweep,
        "n_sweep": n_sweep,
        "cost_crossover": cost_cross,
        "empirical_regimes": regimes,
        "finding": ("mesh の点火は*脱相関*の問題（market.py の escalation はコストの問題）。本リポの実測 gain≈0 は "
                    "すべて ρ≈1 の点＝errors が共通 hard core を持つから。脱相関(ρ<1)があれば必ず点火するが、"
                    "weak mesh が strong を*コストで*置き換えるのは稀（正しさ1に届く n·(w+verify) が s を超えやすい）"
                    "＝mesh の本領は『縁』での補完であって置換でない。"),
        "falsifier": "実測 mesh union が p+(1−ρ)(1−p)(1−(1−p)^{n−1}) から系統的に外れる、または ρ<1 を実証しても "
                     "union が best-single を超えないなら本モデルは偽。",
    }


def _md(r: dict) -> str:
    b = r["base"]
    L = ["# mesh 配分モデル — 合議 mesh が単体最強を超える臨界点（脱相関）",
         "",
         "[`MARKET.md`](MARKET.md) の escalation 版（コスト閾値 p>w/s）に対する **mesh 版**。n エージェントが独立に"
         "解いて外部検証で union を取るとき、**mesh 利得 = (1−ρ)(1−p)(1−(1−p)^{n−1})**（ρ=失敗相関）。"
         "生数値 [`mesh_results.json`](mesh_results.json)。",
         "",
         f"## 臨界：**{r['critical_point']}**",
         f"- 既定 p={r['params']['p']} / ρ={r['params']['rho']} / n={r['params']['n']} → union "
         f"**{b['mesh_correctness']}** vs best-single {b['best_single']} → 利得 **{b['mesh_gain']}**"
         f"（点火={b['ignites']}）。",
         f"- {r['finding']}",
         "",
         "## ① 脱相関スイープ（p, n 固定）── ρ を下げると利得が立ち上がる",
         "| ρ（失敗相関） | union | mesh 利得 | 点火 |",
         "|---|---|---|---|"]
    for d in r["rho_sweep"]:
        L.append(f"| {d['rho']} | {d['union']} | **{d['gain']}** | {'✓' if d['ignites'] else '—'} |")
    L += ["", "（ρ=1 で利得 0＝市場支配。ρ<1 で点火。燃料は脱相関 1−ρ）", "",
          "## ② エージェント数スイープ（ρ=0）── union↑だが利得は (1−p) で頭打ち",
          "| n | union | mesh 利得 |", "|---|---|---|"]
    for d in r["n_sweep"]:
        L.append(f"| {d['n']} | {d['union']} | {d['gain']} |")
    L += ["", "## ③ コスト調整の臨界 ── weak mesh が flat-strong(正しさ1) に届く最小 n と、それが s より安いか",
          "| ρ | 正しさ0.99 到達 n | mesh コスト | strong を価格支配 |", "|---|---|---|---|"]
    for d in r["cost_crossover"]:
        nn = d["n"] if d["n"] is not None else "—（届かず）"
        cc = d["cost"] if d["cost"] is not None else "—"
        L.append(f"| {d['rho']} | {nn} | {cc} | {'**支配**' if d['cost_dominates_strong'] else '—'} |")
    L += ["", "（weak mesh は正しさ1へ多数の agent を要し n·(w+verify) が s を超えやすい＝置換は稀）", "",
          "## ④ 実測レジームを ρ 軸に配置（本リポの mesh 実証を統一）",
          "| レジーム | ρ | n | 利得 | 点火 |", "|---|---|---|---|---|"]
    for rg in r["empirical_regimes"]:
        L.append(f"| {rg['regime']} | {rg['rho']} | {rg['n']} | {rg['gain']} | {'✓' if rg['ignites'] else '—'} |")
    L += ["", "## 含意",
          "- mesh の点火は **構造でなく脱相関** ── market.py（コスト）と対。冗長 mesh が不点火だったのは ρ≈1"
          "（errors が共通 hard core）だから。",
          "- 「超えたところ」を見るには ρ<1 を*作る*しかない（meshflow edge demo＝構成で相補）。real frontier の"
          "errors は入れ子＝ρ≈1 で、自然には脱相関しない。",
          "- たとえ点火しても weak mesh が strong を*価格で*置換するのは稀。mesh の本領は『縁』での補完。",
          "",
          "## 反証条件",
          f"- {r['falsifier']}"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "mesh_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "MESH.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    b = r["base"]
    print(f"critical: {r['critical_point']}")
    print(f"formula:  {r['gain_formula']}")
    print(f"base (p={r['params']['p']}, rho={r['params']['rho']}, n={r['params']['n']}): "
          f"union={b['mesh_correctness']} vs best-single={b['best_single']} gain={b['mesh_gain']} "
          f"ignites={b['ignites']}")
    print("\n① decorrelation sweep (gain rises as rho falls):")
    for d in r["rho_sweep"]:
        bar = "#" * int(d["gain"] * 80)
        print(f"  rho={d['rho']:<4} gain={d['gain']:<8} union={d['union']:<8} {bar}")
    print("\n④ empirical regimes placed on the rho axis:")
    for rg in r["empirical_regimes"]:
        print(f"  rho={rg['rho']:<4} n={rg['n']} gain={rg['gain']:<8} ignites={str(rg['ignites']):<5} {rg['regime']}")
    print(f"\nwrote {os.path.join(out_dir, 'mesh_results.json')} and MESH.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
