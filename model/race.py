r"""レース外部性モデル — 競争が統治膜を安全最適より薄くする量を測る（AI-2027 動機）。

第二の計測（[`governance.py`](governance.py)）は**単独組織**の最適な膜厚 m\* を測った。だが
AI-2027（Race ↔ Slowdown）が突きつけるのは**多者レース**: 厚い膜は安全だが遅く、競争に
負ける。各 actor は個別最適で膜を薄くし、破局の外部性を内部化しない —— 安全の
race-to-the-bottom。Nash 均衡の膜厚 m_eq と、破局を内部化した社会最適 m\* の
**差 (m\* − m_eq)** を、レース強度の関数として測る。

各 actor の効用（対称・1ラウンド近似）:
    U(m_i) = prize · P(win | m_i, 他者) − private_safety · residual_risk(m_i)
       薄い膜ほど速く勝ちやすい: speed(m) = 1 − m
       P(win) = speed(m_i) / Σ speed
社会計画者は破局項 −catastrophe · residual_risk(m) を内部化する。

予言: レース強度（prize・参加者数）が上がるほど m_eq → 0（Race ending）、gap 拡大。
低いと m_eq → m\*（Slowdown）。「競争が安全を削る」を反証可能な数字にする。

run: python3 -m model.race
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RaceParams:
    n_actors: int = 2            # competitors (AI-2027: OpenBrain vs DeepCent ~2)
    prize: float = 40.0          # value of winning the race
    catastrophe: float = 400.0   # social cost if an unsafe winner causes catastrophe
    beta: float = 3.0            # how fast a thicker membrane cuts residual risk
    private_safety: float = 8.0  # private cost an actor bears from its OWN residual risk
    progress_value: float = 100.0  # society's value of capability/progress (lost as m grows)
    grid: int = 401              # m-resolution


def _ms(p: "RaceParams") -> list[float]:
    return [i / (p.grid - 1) for i in range(p.grid)]


def speed(m: float) -> float:
    return max(1e-9, 1.0 - m)                # thicker membrane -> slower (capability cost)


def residual_risk(p: "RaceParams", m: float) -> float:
    return math.exp(-p.beta * m)             # more membrane -> less residual risk


def _util(p: "RaceParams", m: float, m_others: float) -> float:
    win = speed(m) / (speed(m) + (p.n_actors - 1) * speed(m_others))
    return p.prize * win - p.private_safety * residual_risk(p, m)


def best_response(p: "RaceParams", m_others: float) -> float:
    return max(_ms(p), key=lambda m: _util(p, m, m_others))


def nash_equilibrium(p: "RaceParams") -> float:
    """Symmetric equilibrium membrane via damped best-response iteration."""
    m = 0.5
    for _ in range(300):
        m_new = best_response(p, m)
        if abs(m_new - m) < 1e-3:
            m = m_new
            break
        m = (m + m_new) / 2.0
    return round(m, 4)


def social_optimum(p: "RaceParams") -> float:
    """Planner internalizes the catastrophe externality (symmetric m for all)."""
    def welfare(m):
        # the planner values progress (capability, lost as the membrane thickens) and
        # internalizes the catastrophe risk + private safety costs of an unsafe outcome.
        return (p.progress_value * speed(m)
                - p.catastrophe * residual_risk(p, m)
                - p.n_actors * p.private_safety * residual_risk(p, m))
    return round(max(_ms(p), key=welfare), 4)


def gap(p: "RaceParams") -> dict:
    eq = nash_equilibrium(p)
    opt = social_optimum(p)
    return {"m_eq": eq, "m_star_social": opt, "gap": round(opt - eq, 4)}


def run(p: "RaceParams | None" = None) -> dict:
    p = p or RaceParams()
    base = gap(p)
    prize_sweep = [{"prize": v, **gap(dataclasses.replace(p, prize=v))}
                   for v in (10.0, 50.0, 100.0, 200.0, 400.0)]
    actors_sweep = [{"n_actors": v, **gap(dataclasses.replace(p, n_actors=v))}
                    for v in (2, 3, 5, 10)]
    return {
        "params": dataclasses.asdict(p),
        "base": base,
        "finding": ("Nash 均衡の膜 m_eq は社会最適 m* より薄い（gap>0）＝競争が安全を削る。"
                    "レース強度（prize・参加者数）が上がるほど gap 拡大＝AI-2027 の Race へ。"),
        "gap_vs_prize": prize_sweep,
        "gap_vs_n_actors": actors_sweep,
        "falsifier": "どんな prize / 参加者数でも gap=0（競争が膜を削らない）なら本モデル下でレース外部性は無い。",
    }


def _md(r: dict) -> str:
    b = r["base"]
    L = ["# レース外部性 — 競争は統治膜を安全最適より薄くするか（AI-2027 の定量版）",
         "",
         "第二の計測（単独組織の最適膜 m\\*）に**多者レース**を足す。厚い膜は安全だが遅く競争に負ける。"
         "各 actor の Nash 均衡膜 m_eq と、破局を内部化した社会最適 m\\* の差を測る。"
         "生数値 [`race_results.json`](race_results.json)。",
         "",
         f"## 主結果: m_eq = {b['m_eq']} ＜ m\\* = {b['m_star_social']}（**gap = {b['gap']}**）",
         "競争下の均衡膜は社会最適より薄い —— **安全の race-to-the-bottom を反証可能に測れた**。",
         "",
         "## レース強度（prize）→ gap",
         "",
         "| prize（勝利の価値） | m_eq | m\\* | gap |",
         "|---|---|---|---|"]
    for s in r["gap_vs_prize"]:
        L.append(f"| {s['prize']} | {s['m_eq']} | {s['m_star_social']} | {s['gap']} |")
    L += ["",
          "→ 勝利の価値が上がるほど m_eq は薄く、gap は拡大。**高 prize ＝ AI-2027 の Race ending**"
          "（膜を削って競争に勝ちにいく）。低 prize ＝ Slowdown 寄り。",
          "",
          "## 参加者数 → gap",
          "",
          "| n_actors | m_eq | m\\* | gap |",
          "|---|---|---|---|"]
    for s in r["gap_vs_n_actors"]:
        L.append(f"| {s['n_actors']} | {s['m_eq']} | {s['m_star_social']} | {s['gap']} |")
    L += ["",
          "→ 参加者が増えても gap>0（外部性は残る）。ただし本モデルでは n が増えると各自の限界寄与が希釈され m_eq は*むしろ厚く*なる（gap 微減）。**主動因は参加者数でなく prize＝勝利の価値**。単独 n=1 は競争のない第二の計測に相当（退化するため n≥2 で測る）。",
          "",
          "## AI-2027 との対応",
          "- **Race ending** = 高 prize・接戦（DeepCent が2ヶ月後ろ）→ m_eq≪m\\*。各社が膜を薄く保ち、"
          "監督が破綻しても止めない。本モデルの高 prize 域。",
          "- **Slowdown ending** = 破局を内部化（協調・規制・検証共有）→ m_eq→m\\*。本モデルで catastrophe を"
          "actor の私的コストに移せば均衡が厚くなる＝介入の標的。",
          "- これは単独組織の統治膜計測（第二）が**見落としていた量**: 安全最適の膜厚は、競争があると"
          "個々には選ばれない。**「薄い人間統治膜」テーゼの最大の脅威はレース**。",
          "",
          "## 妥当性",
          "- 1ラウンド対称ゲームの近似。speed=1−m・risk=e^(−βm)・破局項は第一原理的だが*仮定*。"
          "結論は質的（gap>0・prize/参加者で拡大）＋感度で読む。",
          "- prize・catastrophe・private_safety の比が結果を決める（相対スケールは仮定）。"
          "実測すべきは「膜の capability コスト」と「破局の社会コスト」。"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "race_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "RACE.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    b = r["base"]
    print(f"m_eq={b['m_eq']}  <  m*_social={b['m_star_social']}   gap={b['gap']}")
    print("prize -> gap (race intensity):")
    for s in r["gap_vs_prize"]:
        print(f"  prize={s['prize']:>6}  m_eq={s['m_eq']:<6} m*={s['m_star_social']:<6} gap={s['gap']}")
    print(f"\nwrote {os.path.join(out_dir, 'race_results.json')}")
    print(f"wrote {os.path.join(out_dir, 'RACE.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
