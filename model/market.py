r"""市場配分モデル — 検証ルーティング型エスカレーション市場が単一モデルを支配する閾値。

§5 の実証は3レジームを示した: ①均質→market 最下位 ②frontier 異種（勾配ゼロ）→market=flat-haiku
③大能力差（gemma×frontier）→market が Pareto 支配。ここではその閾値を*解析*で導き、3レジームを
同一モデルの点として統一する（[`../experiments/MARKET_GAP.md`](../experiments/MARKET_GAP.md) と照合）。

2ティアのエスカレーション市場: 安いティア（コスト w・タスク完全解の確率 p）をまず試し、検証で
落ちた時だけ高いティア（コスト s>w・常に解く）へ:
    期待コスト  C_market = w + (1−p)·s          正しさ = 1（高ティアが必ず救う）
単一モデル flat-strong: コスト s・正しさ 1。 flat-weak: コスト w・正しさ p。

**支配定理**: market が flat-strong と同じ正しさ(1) をより安く出す ⟺ C_market < s
    ⟺ w + (1−p)s < s ⟺ w < p·s ⟺ **p > w/s**。
即ち「安いモデルの完全解率 p が、コスト比 w/s を超える」時に市場が単一モデルを Pareto 支配する。
安いほど（w/s 小）バーは低い。均質（w=s）なら p>1 が必要＝不可能＝市場は勝てない（①と一致）。

n ティア梯子 [(cost_i, p_i)] cheap→expensive: C = Σ_i cost_i·Π_{j<i}(1−p_j)、正しさ = 1−Π_i(1−p_i)。
決定的（解析・stdlib のみ）。 run: python3 -m model.market
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass


@dataclass
class MarketParams:
    w: float = 0.2          # weak-tier cost (gemma, list-price-ratio proxy)
    s: float = 1.0          # strong-tier cost (haiku = cheapest single model that solves all)
    p: float = round(4 / 6, 4)   # weak-tier full-solve rate (gemma: 4/6 tasks at 1.0, measured §5)


def escalation_cost(w: float, s: float, p: float) -> float:
    """Expected cost of the 2-tier escalation market: pay w always, pay s when weak fails (1-p)."""
    return round(w + (1 - p) * s, 4)


def p_star(w: float, s: float) -> float:
    """Threshold weak-solve-rate above which the market Pareto-dominates flat-strong."""
    return round(w / s, 4)


def dominates(w: float, s: float, p: float) -> bool:
    """Market gives flat-strong's correctness (1) strictly cheaper <=> p > w/s."""
    return escalation_cost(w, s, p) < s - 1e-9


def ladder(tiers: list) -> dict:
    """n-tier escalation ladder. tiers = [(cost, p_solve)] cheap->expensive."""
    cost, reach, fail = 0.0, 1.0, 1.0
    for c, p in tiers:
        cost += c * reach            # we reach (and pay) this tier with prob `reach`
        reach *= (1 - p)             # still unsolved -> escalate further
        fail *= (1 - p)
    return {"cost": round(cost, 4), "correctness": round(1 - fail, 4)}


def run(prm: "MarketParams | None" = None) -> dict:
    prm = prm or MarketParams()
    w, s, p = prm.w, prm.s, prm.p
    base = {"market_cost": escalation_cost(w, s, p), "flat_strong_cost": s,
            "flat_weak_cost": w, "flat_weak_correctness": round(p, 4),
            "p_star": p_star(w, s), "market_dominates_flat_strong": dominates(w, s, p)}

    # sweep weak-solve-rate p for several cost ratios w/s (normalize s=1) -> crossover at p*=w/s
    p_grid = [round(0.1 * i, 1) for i in range(11)]
    ratio_sweep = [{"w_over_s": ratio, "p_star": round(ratio, 4),
                    "market_cost_by_p": [{"p": pp, "C": escalation_cost(ratio, 1.0, pp),
                                          "dominates": dominates(ratio, 1.0, pp)} for pp in p_grid]}
                   for ratio in (0.05, 0.2, 0.5)]

    # validate the threshold against the 3 measured regimes (§5)
    regimes = [
        {"regime": "①homogeneous (all sonnet)", "w": 1.0, "s": 1.0, "p": 1.0,
         "note": "weak=strong(勾配なし)→p*=1→p>1 不可能→市場勝てず（実測: market 最下位）"},
        {"regime": "②frontier-hetero (haiku/sonnet/opus)", "w": 1.0, "s": 1.0, "p": 1.0,
         "note": "最安 haiku が全解(p=1)→市場=flat-haiku＝最良単一モデルに*厳密な*利得なし"
                 "（実測一致。素朴に opus を選ぶ flat-opus には勝つが、最良単一モデルは超えない）"},
        {"regime": "③large-gap (gemma×haiku)", "w": 0.2, "s": 1.0, "p": round(4 / 6, 4),
         "note": "gemma 4/6 完全解→市場 0.533<flat-haiku 1.0→Pareto 支配（実測 0.533 と厳密一致）"},
    ]
    for rg in regimes:
        rg["market_cost"] = escalation_cost(rg["w"], rg["s"], rg["p"])
        rg["p_star"] = p_star(rg["w"], rg["s"])
        rg["dominates"] = dominates(rg["w"], rg["s"], rg["p"])

    gap_ladder = ladder([(0.2, round(4 / 6, 4)), (1.0, 1.0), (15.0, 1.0)])   # full gemma->haiku->opus

    return {
        "params": dataclasses.asdict(prm),
        "base": base,
        "threshold_theorem": "市場が flat-strong を Pareto 支配 ⟺ p > w/s（安いティアの完全解率 > コスト比）",
        "finding": ("安いほど（w/s 小）市場が勝つバーは低い。均質(w=s)では p>1 が要り不可能＝市場は勝てない。"
                    "大能力差では安いティアが*そこそこ*解けば（p>w/s）市場が単一モデルを支配する。"),
        "ratio_sweep": ratio_sweep,
        "empirical_regimes": regimes,
        "gap_ladder_3tier": gap_ladder,
        "falsifier": "実測 market コストが w+(1−p)s から系統的に外れる、または p>w/s でも市場が支配しないなら"
                     "本モデルは偽。実測③ (0.533) は解析 (0.533) と一致＝現状は支持。",
    }


def _md(r: dict) -> str:
    b = r["base"]
    L = ["# 市場配分モデル — エスカレーション市場が単一モデルを支配する閾値",
         "",
         "§5 の異種 market 実証（3レジーム）を統一する解析。2ティアのエスカレーション市場（安い w・"
         "完全解率 p → 落ちた時だけ高い s）の期待コスト **C = w + (1−p)·s**、正しさ 1。"
         "生数値 [`market_results.json`](market_results.json)。",
         "",
         f"## 支配定理：**{r['threshold_theorem']}**",
         f"- 既定（gemma×haiku 較正）: w={r['params']['w']} / s={r['params']['s']} / p={r['params']['p']} "
         f"→ market_cost **{b['market_cost']}** vs flat-strong {b['flat_strong_cost']} "
         f"→ p\\* = **{b['p_star']}**、市場が支配 = **{b['market_dominates_flat_strong']}**。",
         f"- {r['finding']}",
         "",
         "## p（安いティアの完全解率）スイープ — 市場が flat-strong を支配し始める p",
         "| コスト比 w/s | 閾値 p\\* | p=0.2 | p=0.5 | p=0.8 | p=1.0 |",
         "|---|---|---|---|---|---|"]
    for row in r["ratio_sweep"]:
        by = {d["p"]: d for d in row["market_cost_by_p"]}

        def cell(pp):
            d = by[pp]
            return f"{d['C']}{'✓' if d['dominates'] else ''}"
        L.append(f"| {row['w_over_s']} | **{row['p_star']}** | {cell(0.2)} | {cell(0.5)} | "
                 f"{cell(0.8)} | {cell(1.0)} |")
    L += ["", "（セルはコスト C・✓ は flat-strong(コスト=1) を支配＝C<1。p\\* を超えると ✓ が立つ）", "",
          "## 3レジームの統一（実測 §5 と照合）",
          "| レジーム | w | s | p | 閾値 p\\* | market コスト | 支配 |",
          "|---|---|---|---|---|---|---|"]
    for rg in r["empirical_regimes"]:
        L.append(f"| {rg['regime']} | {rg['w']} | {rg['s']} | {rg['p']} | {rg['p_star']} | "
                 f"{rg['market_cost']} | {'**支配**' if rg['dominates'] else '—'} |")
    gl = r["gap_ladder_3tier"]
    L += ["",
          f"3ティア梯子（gemma→haiku→opus）: コスト **{gl['cost']}**・正しさ {gl['correctness']} "
          f"＝実測 §5 (0.533, 1.0) と一致。",
          "",
          "## 含意",
          "- 「市場型組織が有効か」は **agent 間の能力差（p と w/s）** で決まる ── 構造の問題でなく*分布*の問題。",
          "- 安い agent が*そこそこ*（p>w/s）解けるなら、検証ルーティング市場が単一モデルを Pareto 支配。",
          "- 均質に有能（w=s, p=1）なら市場は勝てず flat が最適 ── §5①② と本定理が一致。",
          "",
          "## 反証条件",
          f"- {r['falsifier']}"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "market_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "MARKET.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    b = r["base"]
    print(f"threshold: {r['threshold_theorem']}")
    print(f"base (gemma×haiku): market_cost={b['market_cost']} vs flat-strong={b['flat_strong_cost']} "
          f"p*={b['p_star']} dominates={b['market_dominates_flat_strong']}")
    for rg in r["empirical_regimes"]:
        print(f"  {rg['regime']:<38} market={rg['market_cost']:<7} p*={rg['p_star']:<6} dominates={rg['dominates']}")
    print(f"wrote {os.path.join(out_dir, 'market_results.json')} and MARKET.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
