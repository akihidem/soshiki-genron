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

──────────────────────────────────────────────────────────────────────────────
**実測は上の臨界（ρ<1 ⟹ 点火）を反証した。** real frontier（opus×codex・実 SWE-bench N=24・trials=2）は
ρ≈0.6<1 で脱相関しているのに **robust gain = 0**。実測で効くのは ρ でなく*相互*相補で、恒等式
    **gain = min(a, b) / n**   （a=|A\B|, b=|B\A|）
が観測を説明する（a>0 かつ b>0 でなければ 0。入れ子なら ρ<1 でも 0）。詳細は [`noise.py`](noise.py) ①。

さらに **非決定な採点ハーネスは gain>0 をノイズだけで作る**。本リポは一度 trials=1 の +0.042 を
「real frontier で初の点火」と報告・commit し、trials=2 で 0 に flip して撤回した
（[`../experiments/SWEBENCH_TRIALS.md`](../experiments/SWEBENCH_TRIALS.md)）。よって本ファイルの実測点は
**trials=2 の頑健値のみ**を載せ、`ignites` は「gain>0」でなく **gain > 検出床**（noise.py ④）で判定する。
──────────────────────────────────────────────────────────────────────────────

決定的（解析・stdlib のみ）。 run: python3 -m model.mesh
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass

# 実測解ベクトルと検出床の正本は noise.py（trial-1/trial-2 の両方を持つ）。
# 単一試行の値は mesh に載せない ── ignites は「gain>0」でなく「gain > 検出床」で判定する。
from model.noise import (
    SWE6_CODEX_T1, SWE6_CODEX_T2, SWE6_OPUS_T1, SWE6_OPUS_T2,
    SWE24_CODEX_T1, SWE24_CODEX_T2, SWE24_OPUS_T1, SWE24_OPUS_T2,
    TrueStructure, detection_floor, disagreement_rate, flip_from_disagreement,
    robust_counts, stable_vector,
)


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


# --------------------------------------------------------------------------- #
# 実測からの接地 — 各エージェントの解ベクトル(1=解けた/0=失敗)から ρ・union・利得を測る。
# モデルは ρ を仮定するが、real ではこれで ρ を*測れる*。点火には ρ<1 だけでなく
# *相互*相補（非入れ子）が要る点も union−best で自然に出る（非対称＝入れ子なら gain 0）。
# --------------------------------------------------------------------------- #
def _phi(fa: list, fb: list) -> float:
    """failure 指標 2 本の phi 係数（=Pearson 相関）。1=comonotone, 0=独立, <0=反相関。"""
    n = len(fa)
    ma, mb = sum(fa) / n, sum(fb) / n
    cov = sum((a - ma) * (b - mb) for a, b in zip(fa, fb)) / n
    va, vb = ma * (1 - ma), mb * (1 - mb)
    return 0.0 if va <= 0 or vb <= 0 else cov / ((va * vb) ** 0.5)


def failure_correlation(solve_vectors: list) -> float:
    """全エージェントの失敗指標の平均ペア相関 ρ。solve_vectors=[[0/1,...],...]（1=解けた）。"""
    fails = [[1 - s for s in v] for v in solve_vectors]
    pairs = [(i, j) for i in range(len(fails)) for j in range(i + 1, len(fails))]
    return round(sum(_phi(fails[i], fails[j]) for i, j in pairs) / len(pairs), 4) if pairs else 0.0


def union_solve(solve_vectors: list) -> float:
    """外部検証で union を取った時の正しさ＝どれか1つでも解けた割合。"""
    n = len(solve_vectors[0])
    return round(sum(1 for k in range(n) if any(v[k] for v in solve_vectors)) / n, 4)


def empirical_mesh(solve_vectors: list) -> dict:
    """実測解ベクトルから per-model / union / best / 利得 / 測定 ρ / 点火 を返す。"""
    per = [round(sum(v) / len(v), 4) for v in solve_vectors]
    u, best = union_solve(solve_vectors), max(round(sum(v) / len(v), 4) for v in solve_vectors)
    return {"per_model": per, "union": u, "best_single": best, "gain": round(u - best, 4),
            "failure_rho": failure_correlation(solve_vectors), "ignites": (u - best) > 1e-9}


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


# 実測解ベクトル（1=resolved・index は experiments/swebench_all_results.json の rows 順）は noise.py が正本。
# fable-5 を pytest6 で試みたが単一試行では非再現(trial1 [0,1,1,0,1,1] vs trial2 [0,0,0,1,1,1]・3/6 flip・
# 一部は fable が非コード出力を返し parse 不能)＝mesh に載せる値にならない。詳細は SWEBENCH_FABLE_PT6.md・§9-11。


def _grounded_point(name: str, trials_a: list, trials_b: list, note: str) -> dict:
    """複数試行から**頑健な** mesh 点を作り、noise.py の検出床でゲートする。

    - gain は *安定*セル（全試行で一致）だけで数える（robust_counts）。
    - `ignites` は「gain>0」ではなく「**gain が検出床を超えた**」ときだけ True。
      trials=1 のセル不一致率（opus は 3/24）が作る偽の相補を、機械で弾くため。
    """
    rb = robust_counts(trials_a, trials_b)
    fa = flip_from_disagreement(disagreement_rate(trials_a))
    fb = flip_from_disagreement(disagreement_rate(trials_b))
    trials = len(trials_a)
    h0 = TrueStructure(common=rb["common"] + rb["unstable"], a_only=rb["a_only"],
                       b_only=rb["b_only"], neither=rb["neither"])
    floor = detection_floor(h0, fa, fb, trials=trials)
    observed_m = min(rb["a_only"], rb["b_only"])

    # ρ も単一試行では決まらない ── 試行ごとに測って振れ幅を出す（解析モデルが依存する量なのに不安定）。
    rho_by_trial = [failure_correlation([va, vb]) for va, vb in zip(trials_a, trials_b)]
    # 頑健 ρ: 両モデルとも全試行で一致したセルだけで測る（割れたセルは相関の証拠に使えない）。
    sa, sb = stable_vector(trials_a), stable_vector(trials_b)
    keep = [k for k in range(len(sa)) if sa[k] is not None and sb[k] is not None]
    rho_stable = (failure_correlation([[sa[k] for k in keep], [sb[k] for k in keep]])
                  if len(keep) >= 2 else 0.0)

    return {"name": name, "trials": trials,
            "per_model_by_trial": [[round(sum(v) / len(v), 4) for v in (va, vb)]
                                   for va, vb in zip(trials_a, trials_b)],
            "a_only": rb["a_only"], "b_only": rb["b_only"], "unstable_cells": rb["unstable"],
            "gain": rb["gain"], "gain_tasks": observed_m,
            "failure_rho_by_trial": rho_by_trial, "failure_rho_stable": rho_stable,
            "flip_a": round(fa, 4), "flip_b": round(fb, 4),
            "floor_tasks": floor["m"], "floor_gain": floor["gain"],
            "ignites": floor["m"] is not None and observed_m >= floor["m"],
            "note": note}


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

    # ⑤ 実測（実 SWE-bench・opus×codex）── **trials=2 の頑健値のみ**を載せる。
    #    単一試行の値は noise.py の検出床を下回るため mesh の点にしない（SWEBENCH_TRIALS.md で撤回済み）。
    empirical_real = {
        "opus×codex full-24 (trials=2, robust)": _grounded_point(
            "opus×codex full-24", [SWE24_OPUS_T1, SWE24_OPUS_T2], [SWE24_CODEX_T1, SWE24_CODEX_T2],
            "安定な相互相補ゼロ＝**点火しない**。安定 opus-only は sympy-24443 の1件のみ(*一方向*)・"
            "安定 codex-only は 0 件。trial-1 で見えた codex-only 3件は全部 opus の run noise(3/24)だった。"),
        "opus×codex pytest-6 (trials=2, robust)": _grounded_point(
            "opus×codex pytest-6", [SWE6_OPUS_T1, SWE6_OPUS_T2], [SWE6_CODEX_T1, SWE6_CODEX_T2],
            "trials=2 で両者の安定解集合は一致（a=b=0）。ただし n=6 の検出床は 2 タスク＝**gain 0.333 未満は"
            "そもそも検出できない**ので、この『gain 0』は非点火の証拠として弱い（検出力が無い）。"),
    }

    # 撤回済みの点を*見える形で*残す（本リポの作法）。単一試行で「初の点火」と報告し commit した値。
    retracted = {
        "opus×codex full-24 (trial-1 のみ) — RETRACTED": {
            **empirical_mesh([SWE24_OPUS_T1, SWE24_CODEX_T1]),
            "trials": 1, "gain_tasks": 1,
            "note": "2026-06-23 撤回(SWEBENCH_TRIALS.md)。gain +0.042 は 1 タスク分で、trials=1 の"
                    "**検出床 3 タスク(0.125)の 1/3**。H0(相互相補ゼロ)＋opus の実測ノイズ(f≈0.067)だけで"
                    "同じ観測が出る確率は **0.68** ＝ ノイズの*期待される*出力。trial-2 を回す前に計算できた。"},
    }

    return {
        "params": dataclasses.asdict(prm),
        "base": base,
        "gain_formula": "mesh 利得 = (1−ρ)·(1−p)·(1 − (1−p)^{n−1})",
        "critical_point": "利得 > 0 ⟺ ρ < 1（脱相関がある）。ρ=1（入れ子/共通 hard core）で利得 0 ＝ 市場支配。",
        "rho_sweep": rho_sweep,
        "n_sweep": n_sweep,
        "cost_crossover": cost_cross,
        "empirical_regimes": regimes,
        "empirical_real": empirical_real,
        "retracted": retracted,
        "gain_identity": "実測では gain = min(a,b)/n（a=|A\\B|, b=|B\\A|）＝**相互**相補がなければ 0（noise.py ①）",
        "reporting_gate": ("実測の『点火』は gain>0 でなく **gain > 検出床**（noise.py ④）で判定する。"
                           "非決定な採点ハーネスは gain>0 をノイズだけで作るため（opus は 3/24=12.5% の"
                           "セル不一致）。trials=1 は頑健推定が naive に退化する＝床を持てない。"),
        "finding": ("mesh の点火は*脱相関*の問題（market.py の escalation はコストの問題）。本リポの実測 gain≈0 は "
                    "すべて ρ≈1 の点＝errors が共通 hard core を持つから。**解析では**脱相関(ρ<1)があれば必ず"
                    "点火するが、**実測では ρ<1 でも点火しない**：real frontier(opus×codex・実 SWE-bench N=24・"
                    "trials=2)は ρ≈0.6<1 なのに*安定な*相互相補がゼロで robust gain=0（一度 +0.042 を「初の点火」と"
                    "報告して撤回・SWEBENCH_TRIALS.md）。点火に要るのは脱相関でなく**相互相補**（gain=min(a,b)/n）。"
                    "また weak mesh が strong を*コストで*置き換えるのは稀（正しさ1に届く n·(w+verify) が s を"
                    "超えやすい）＝mesh の本領は『縁』での補完であって置換でない。"),
        "falsifier": "実測 mesh union が p+(1−ρ)(1−p)(1−(1−p)^{n−1}) から系統的に外れる、または ρ<1 を実証しても "
                     "union が best-single を超えないなら本モデルは偽（後者は real frontier で*実際に起きた*→ "
                     "解析の ρ 版は実測を説明できず、min(a,b) 版へ差し替えた）。",
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
    L += ["", "## ⑤ 実測（real SWE-bench・opus×codex）── **trials=2 の頑健値のみ**を載せる",
          "",
          f"> 実測の恒等式: **{r['gain_identity']}**",
          "",
          "| 集合 | trials | a=A-only | b=B-only | 不安定セル | 利得 | 試行ごとの ρ | 安定セルの ρ | 検出床 | 点火 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for name, e in r["empirical_real"].items():
        fl = f"{e['floor_tasks']} タスク ({e['floor_gain']})" if e["floor_tasks"] else "n を超える"
        L.append(f"| {name} | {e['trials']} | {e['a_only']} | {e['b_only']} | {e['unstable_cells']} | "
                 f"**{e['gain']:+}** | {e['failure_rho_by_trial']} | {e['failure_rho_stable']} | "
                 f"{fl} | {'✓' if e['ignites'] else '—'} |")
    full = r["empirical_real"]["opus×codex full-24 (trials=2, robust)"]
    L += ["",
          f"- **real frontier（opus×codex・N=24・trials=2）は ρ={full['failure_rho_stable']}<1 で脱相関して"
          "いるのに点火しない。** 安定な opus-only は `sympy-24443` の1件（*一方向*）、安定な codex-only は "
          "**0 件**。gain = min(a,b)/n = min(1,0)/24 = **0**。",
          "- **点火に要るのは ρ<1（脱相関）でなく*相互*相補**。解析の ρ 版は「ρ<1 なら必ず点火」と言うが、"
          "実測はそれを**反証した**（ρ<1 かつ gain 0）。恒等式 min(a,b)/n の方が実測を説明する。",
          f"- **ρ 自体も単一試行では決まらない**: 同じ N=24 を2回回すと ρ は "
          f"{full['failure_rho_by_trial'][0]} → {full['failure_rho_by_trial'][1]} と振れる"
          "（解析モデルが依存する量なのに、非決定な採点の下では不安定）。",
          "- pytest-6 は n=6 の検出床が 2 タスク＝**gain 0.333 未満はそもそも検出できない**。"
          "その『gain 0』は非点火の証拠として弱い（検出力が無い）。",
          ""]
    L += ["## ⑤' 撤回済みの点（見える形で残す）", "",
          "| 集合 | trials | 利得 | 測定 ρ | なぜ撤回したか |", "|---|---|---|---|---|"]
    for name, e in r["retracted"].items():
        L.append(f"| {name} | {e['trials']} | **{e['gain']:+}** | {e['failure_rho']} | {e['note']} |")
    L += ["",
          f"> **報告ゲート**: {r['reporting_gate']} 床の計算は [`NOISE.md`](NOISE.md)。",
          "",
          "## 含意",
          "- mesh の点火は **構造でなく相互相補** ── market.py（コスト）と対。冗長 mesh が不点火だったのは ρ≈1"
          "（errors が共通 hard core）だが、**ρ<1 でも入れ子なら点火しない**（real frontier がその実例）。",
          "- 「超えたところ」を見るには相互相補を*作る*しかない（meshflow edge demo＝構成で相補）。real frontier の"
          "errors は入れ子で、自然には相互相補にならない。",
          "- たとえ点火しても weak mesh が strong を*価格で*置換するのは稀。mesh の本領は『縁』での補完。",
          "- **非決定な採点ハーネスでは「gain>0」は主張にならない**。床を超えて初めて点火と呼ぶ（NOISE.md）。",
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
    print("\n④ empirical regimes placed on the rho axis (analytical):")
    for rg in r["empirical_regimes"]:
        print(f"  rho={rg['rho']:<4} n={rg['n']} gain={rg['gain']:<8} ignites={str(rg['ignites']):<5} {rg['regime']}")
    print("\n⑤ MEASURED (real SWE-bench, opus×codex) — trials=2 robust only; gain = min(a,b)/n:")
    for name, e in r["empirical_real"].items():
        print(f"  {name}: trials={e['trials']} a={e['a_only']} b={e['b_only']} "
              f"unstable={e['unstable_cells']} gain={e['gain']:+} "
              f"rho_by_trial={e['failure_rho_by_trial']} rho_stable={e['failure_rho_stable']} "
              f"floor={e['floor_tasks']} tasks -> ignites={e['ignites']}")
    print("\n⑤' RETRACTED (kept visible):")
    for name, e in r["retracted"].items():
        print(f"  {name}: trials={e['trials']} gain={e['gain']:+} rho_fail={e['failure_rho']}")
    print(f"\ngate: {r['reporting_gate']}")
    print(f"\nwrote {os.path.join(out_dir, 'mesh_results.json')} and MESH.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
