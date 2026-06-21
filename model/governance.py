"""統治膜モデル — 「最適性 vs 可読性」の中心的緊張を計測する。

foundations.md §5 / F8: AIネイティブに最適化された機構の上に、人間が主権・説明責任を
保つための「人間可読な統治膜」を被せる。膜は効率には死荷重だが、人間が高リスクの
誤りを捕まえる窓でもある。**最適な膜の厚み m\\* はあるか、それは何に依存するか**を測る。

膜の厚み m ∈ [0,1] = AI機構の判断のうち、人間可読・監査・承認ゲートを通す割合。

    総損失(m) = 効率コスト(m) + 残存誤りコスト(m)
              = c_mem · m · N            （膜は判断ごとに効率税を課す・通信非依存）
              + p_bad · N · stakes · e^(-β·m)   （人間監督が高リスク誤りを飽和的に捕捉）

効率コストは m に線形、捕捉の便益は飽和（限界便益逓減）。よって内点最適 m\\* が出る:

    m\\* = clip( (1/β)·ln( β·p_bad·stakes / c_mem ), 0, 1 )

- stakes が低い → m\\*=0（膜は割に合わない＝純効率が最適）
- stakes が上がる → m\\* が対数的に増え、やがて 1（全面的な膜）

これは「膜が厚すぎれば擬人的負債、薄すぎれば主権喪失」を測れる形にしたもの。
反証: 任意の stakes>0 で m\\*=0 のまま（膜が決して割に合わない）なら、「統治は荷重部材」は本モデル下で偽。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GovParams:
    n: int = 12                # decisions per run
    p_bad: float = 0.15        # fraction of decisions that are high-stakes-error-prone
    c_mem: float = 0.5         # efficiency tax per unit membrane per decision
    beta: float = 3.0          # oversight reach (saturating efficacy of the membrane)
    stakes: float = 10.0       # cost if a high-stakes error ships unchecked
    oversight_error: float = 0.0   # fraction of error-prone decisions human oversight
                                   # ITSELF misses regardless of m (0 = perfect oversight)
    # --- precision axis (B): empirically, stronger/thicker oversight OVER-flags clean
    # decisions (alert fatigue/noise). Default 0 = off (backward compatible). The
    # oversight experiment measured FP rising with capability (haiku 0 -> opus 0.33).
    fp_rate_max: float = 0.0       # max over-flag (false-positive) rate as the membrane saturates
    fp_cost: float = 0.0           # cost per over-flagged clean decision
    fp_gamma: float = 3.0          # how fast over-flagging rises with membrane thickness m


def total_loss(p: GovParams, m: float) -> dict:
    m = max(0.0, min(1.0, m))
    efficiency = p.c_mem * m * p.n
    # oversight catches a saturating fraction of error-prone decisions, but is
    # itself imperfect: its ceiling is (1 - oversight_error).
    caught = (1.0 - p.oversight_error) * (1.0 - math.exp(-p.beta * m))
    residual = p.p_bad * p.n * p.stakes * (1.0 - caught)
    return {"m": round(m, 4), "efficiency": round(efficiency, 4),
            "residual_error": round(residual, 4),
            "total": round(efficiency + residual, 4)}


def optimal_membrane(p: GovParams) -> dict:
    """Analytic minimizer of total_loss over m∈[0,1], plus its regime."""
    reliability = 1.0 - p.oversight_error
    drive = p.beta * p.p_bad * p.stakes * reliability / p.c_mem
    if reliability <= 0.0 or drive <= 1.0:
        m_star, regime = 0.0, "no_membrane"        # pure efficiency wins
    else:
        raw = math.log(drive) / p.beta
        if raw >= 1.0:
            m_star, regime = 1.0, "full_membrane"
        else:
            m_star, regime = raw, "partial_membrane"   # interior optimum
    return {"m_star": round(m_star, 4), "regime": regime,
            "loss_at_m_star": total_loss(p, m_star)["total"],
            "loss_at_zero": total_loss(p, 0.0)["total"]}


def stakes_thresholds(p: GovParams) -> dict:
    """The two stakes values that bound the interior (thin-membrane) regime."""
    reliability = max(1e-9, 1.0 - p.oversight_error)
    lo = p.c_mem / (p.beta * p.p_bad * reliability)                       # below: m*=0
    hi = math.exp(p.beta) * p.c_mem / (p.beta * p.p_bad * reliability)    # above: m*=1
    return {"membrane_starts_paying_at_stakes": round(lo, 4),
            "membrane_saturates_at_stakes": round(hi, 4)}


# --------------------------------------------------------------------------- #
# B: precision cost — oversight OVER-flags clean decisions, and (measured) the
# over-flag rate rises with overseer capability. docs/oversight-pilot.md.
# --------------------------------------------------------------------------- #
def over_flag_rate(p: GovParams, m: float) -> float:
    return p.fp_rate_max * (1.0 - math.exp(-p.fp_gamma * max(0.0, m)))


def total_loss_with_precision(p: GovParams, m: float) -> dict:
    base = total_loss(p, m)
    clean = p.n * (1.0 - p.p_bad)
    over_flag = p.fp_cost * clean * over_flag_rate(p, m)
    return {**base, "over_flag": round(over_flag, 4),
            "total": round(base["total"] + over_flag, 4)}


def optimal_membrane_precision(p: GovParams, grid: int = 1001) -> dict:
    """Numeric optimum INCLUDING the over-flag cost (no closed form). When the
    precision params are 0 this equals the recall-only optimum."""
    ms = [i / (grid - 1) for i in range(grid)]
    best = min(ms, key=lambda m: total_loss_with_precision(p, m)["total"])
    return {"m_star": round(best, 4),
            "loss": total_loss_with_precision(p, best)["total"],
            "m_star_recall_only": optimal_membrane(p)["m_star"]}


def logspace(lo: float, hi: float, n: int) -> list[float]:
    if n == 1:
        return [hi]
    step = (math.log(hi) - math.log(lo)) / (n - 1)
    return [round(math.exp(math.log(lo) + step * i), 4) for i in range(n)]


import dataclasses  # noqa: E402


def run(p: GovParams | None = None) -> dict:
    p = p or GovParams()
    stakes_grid = logspace(0.5, 50.0, 13)
    sweep = []
    for s in stakes_grid:
        opt = optimal_membrane(dataclasses.replace(p, stakes=s))
        sweep.append({"stakes": s, "m_star": opt["m_star"], "regime": opt["regime"]})
    # the loss curve over m at default params (shows the interior optimum)
    m_grid = [round(0.1 * k, 1) for k in range(11)]
    curve = [total_loss(p, m) for m in m_grid]
    # sensitivity: oversight reach beta
    beta_sens = []
    for b in (1.0, 2.0, 3.0, 5.0):
        pb = dataclasses.replace(p, beta=b)
        beta_sens.append({"beta": b, **stakes_thresholds(pb),
                          "m_star_at_default_stakes": optimal_membrane(pb)["m_star"]})
    # sensitivity: imperfect oversight (the membrane's benefit caps as oversight errs)
    oversight_sens = []
    for oe in (0.0, 0.3, 0.6, 0.9):
        pe = dataclasses.replace(p, oversight_error=oe)
        oversight_sens.append({
            "oversight_error": oe,
            "m_star_at_default_stakes": optimal_membrane(pe)["m_star"],
            "membrane_starts_paying_at_stakes": stakes_thresholds(pe)["membrane_starts_paying_at_stakes"],
        })
    # B (empirical): stronger oversight over-flags more (measured FP haiku 0 -> opus 0.33);
    # as the over-flag rate rises, the optimal membrane gets THINNER (precision caps it).
    precision_sens = []
    for fpm in (0.0, 0.1, 0.2, 0.33):
        pp = dataclasses.replace(p, fp_cost=5.0, fp_rate_max=fpm)
        precision_sens.append({"fp_rate_max": fpm,
                               "m_star": optimal_membrane_precision(pp)["m_star"]})
    return {
        "params": dataclasses.asdict(p),
        "thresholds": stakes_thresholds(p),
        "optimum_at_default": optimal_membrane(p),
        "m_star_vs_stakes": sweep,
        "loss_curve_over_m": curve,
        "sensitivity_oversight_reach": beta_sens,
        "sensitivity_oversight_error": oversight_sens,
        "sensitivity_precision_overflag": precision_sens,
        "falsifier": "任意の stakes>0 で m*=0 のままなら『統治は荷重部材』は本モデル下で偽。",
    }


def _md(r: dict) -> str:
    th = r["thresholds"]
    opt = r["optimum_at_default"]
    L = []
    L.append("# 第二の計測 — 統治膜の最適な厚み（最適性 vs 可読性）")
    L.append("")
    L.append("研究の中心的緊張（[`../docs/foundations.md`](../docs/foundations.md) §5）を計測可能化: "
             "AI機構の上の**人間可読な統治膜の厚み m\\*** に最適値はあるか、何に依存するか。"
             "決定的モデル（`model/governance.py`）。生数値は [`governance_results.json`](governance_results.json)。")
    L.append("")
    L.append("## 主結果")
    L.append(f"- **内点最適が存在する**。既定パラメタで m\\* = {opt['m_star']}（regime: {opt['regime']}）。"
             "膜ゼロ（純効率）でも膜全面でもなく、**部分的な膜**が最小損失。厚みは stakes が決め、低 stakes で薄く高 stakes で厚い。")
    L.append(f"- **stakes（誤りが流出した時の損害）に依存**。stakes < {th['membrane_starts_paying_at_stakes']} "
             f"では m\\*=0（膜は割に合わない＝純効率が最適）。stakes > {th['membrane_saturates_at_stakes']} で m\\*=1（全面膜）。"
             "その間は薄い膜が最適で、stakes とともに対数的に厚くなる。")
    L.append("- = foundations §5「膜が厚すぎれば擬人的負債、薄すぎれば主権喪失。最適は*必要十分に薄い膜*」を、"
             "**stakes が決めるしきい値**として測った。")
    L.append("")
    L.append("## m\\* vs stakes")
    L.append("```")
    L.append("stakes   m_star  regime")
    for row in r["m_star_vs_stakes"]:
        L.append(f"{row['stakes']:>7}  {row['m_star']:>5}  {row['regime']}")
    L.append("```")
    L.append("")
    L.append("## 損失曲線（既定 stakes・内点最適の確認）")
    L.append("```")
    L.append("  m    efficiency  residual_error  total")
    for c in r["loss_curve_over_m"]:
        L.append(f" {c['m']:>3}   {c['efficiency']:>9}   {c['residual_error']:>12}   {c['total']:>6}")
    L.append("```")
    L.append("")
    L.append("## 感度 — 人間監督の到達度 β")
    L.append("| β（監督の効き） | 膜が割に合う stakes | 全面膜になる stakes | 既定stakesでの m\\* |")
    L.append("|---|---|---|---|")
    for s in r["sensitivity_oversight_reach"]:
        L.append(f"| {s['beta']} | {s['membrane_starts_paying_at_stakes']} | "
                 f"{s['membrane_saturates_at_stakes']} | {s['m_star_at_default_stakes']} |")
    L.append("")
    L.append("→ 監督が効くほど（β大）薄い膜で足り、低 stakes でも膜が割に合う。監督が無力なら膜は死荷重。")
    L.append("")
    L.append("## 感度 — 人間監督の不確かさ oversight_error")
    L.append("監督自身も誤る（捕捉に上限 1−oversight_error）。誤判定が増えると膜の便益が頭打ち → m\\* は下がる:")
    L.append("")
    L.append("| oversight_error | 既定 stakes での m\\* | 膜が割に合う stakes |")
    L.append("|---|---|---|")
    for s in r["sensitivity_oversight_error"]:
        L.append(f"| {s['oversight_error']} | {s['m_star_at_default_stakes']} | "
                 f"{s['membrane_starts_paying_at_stakes']} |")
    L.append("")
    L.append("→ 監督が当てにならないほど膜は薄くて済む／やがて割に合わなくなる。"
             "**「人間統治膜が荷重部材」なのは、監督がある程度信頼できる限りでの条件付き主張**であることが明示された。")
    L.append("")
    L.append("## 感度 — 過剰flag（precision）コスト ［B・実測由来］")
    L.append("実証で「強い監督ほど clean を誤って flag」が再現（FP haiku 0 → opus 0.33・[`../docs/oversight-pilot.md`](../docs/oversight-pilot.md)）。"
             "over-flag 率（fp_rate_max）が上がるほど最適膜は**薄く**なる:")
    L.append("")
    L.append("| fp_rate_max（過剰flag上限） | 最適膜 m\\* |")
    L.append("|---|---|")
    for s in r["sensitivity_precision_overflag"]:
        L.append(f"| {s['fp_rate_max']} | {s['m_star']} |")
    L.append("")
    L.append("→ **能力↑で過剰flag↑ → 最適膜は薄くなる**（反直観・実測由来）。膜のコストは効率税だけでなく**誤検出ノイズ**も含む。"
             "強い監督ほど厚い膜が良い、とは限らない。")
    L.append("")
    L.append("## 反証手段・妥当性")
    L.append(f"- 反証: {r['falsifier']}")
    L.append("- 効率コストは m に線形、捕捉便益は飽和、と仮定。係数は第一原理的だが*仮定*。"
             "結論は質的（内点最適の存在と stakes 依存）＋感度として読む。"
             "β（人間監督が確信的誤りをどれだけ捕まえるか）は ② か実データで測るべき経験量。")
    return "\n".join(L)


def main(argv=None) -> int:
    import json
    import os
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "governance_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "GOVERNANCE.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    opt, th = r["optimum_at_default"], r["thresholds"]
    print(f"optimal membrane m* = {opt['m_star']} ({opt['regime']}) at default stakes")
    print(f"membrane starts paying at stakes={th['membrane_starts_paying_at_stakes']}, "
          f"saturates (m*=1) at stakes={th['membrane_saturates_at_stakes']}")
    print("m* vs stakes:")
    for row in r["m_star_vs_stakes"]:
        print(f"  stakes={row['stakes']:>7}  m*={row['m_star']:>5}  {row['regime']}")
    print(f"\nwrote {os.path.join(out_dir, 'governance_results.json')}")
    print(f"wrote {os.path.join(out_dir, 'GOVERNANCE.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
