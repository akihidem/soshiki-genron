"""通信コスト較正 — coordination.py の mgr_overhead と c_comm を org_sim 実測で接地する。

coordination.py は構造の総コストを c_comm（通信1単位のコスト）の関数とし、mgr_overhead（管理者の
通信非依存OH）を仮定していた（§8: 未較正）。org_sim（実 LLM エージェント）はコストを*モデルコール数*で
測った: flat=3 / hierarchy=5 / market=4。これを使って2つを接地する:

- **mgr_overhead** = hierarchy − flat のコール差 = 5−3 = **2**（管理者の分解+統合の2コール）。
  ＝ coordination.py の既定 2.0 と*厳密一致*。market OH = market − flat = 4−3 = 1（入札1コール）。
- **c_comm（コール単位）≈ 0**: flat の相互依存調整は*共有黒板/文脈*経由で追加コールを生まない
  （調整は token に乗るがコール数は増えない）。→ AI は coordination.py の「c_comm 低 → flat 勝ち」領域に居る。

検証: 測定した mgr_overhead を入れ、c_comm≈0 で winner() が flat を返す（org_sim と一致）かを確認。
決定的（LLM 不要）。 run: python3 -m experiments.calibrate_coord
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.coordination import Params, cost_flat, cost_hierarchy, cost_market, winner  # noqa: E402


def run() -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    osr = json.load(open(os.path.join(here, "org_sim_results.json"), encoding="utf-8"))
    calls = {k: osr["aggregate"][k]["avg_calls"] for k in ("flat", "hierarchy", "market")}

    mgr_overhead_measured = round(calls["hierarchy"] - calls["flat"], 3)   # manager decompose+integrate
    market_overhead_measured = round(calls["market"] - calls["flat"], 3)   # bidding round
    model_default = Params().mgr_overhead

    # c_comm in CALL units ~ 0: flat coordinates via shared context, not extra calls.
    # Plug the MEASURED manager overhead and confirm the winner at c_comm->0 is flat.
    p = dataclasses.replace(Params(), mgr_overhead=mgr_overhead_measured, same_error=True)
    sweep = []
    for c_comm in (0.0, 0.01, 0.05, 0.1, 0.3, 1.0):
        w, tot = winner(p, c_comm)
        sweep.append({"c_comm": c_comm, "winner": w, "total": round(tot, 3),
                      "flat": round(cost_flat(p, c_comm)["total"], 3),
                      "hierarchy": round(cost_hierarchy(p, c_comm)["total"], 3),
                      "market": round(cost_market(p, c_comm)["total"], 3)})
    winner_at_zero = winner(p, 0.0)[0]

    return {
        "measured_calls": calls,
        "mgr_overhead": {"measured": mgr_overhead_measured, "model_default": model_default,
                         "match": abs(mgr_overhead_measured - model_default) < 1e-6},
        "market_overhead_measured": market_overhead_measured,
        "c_comm_in_calls": 0.0,
        "winner_at_c_comm_0": winner_at_zero,
        "sweep": sweep,
        "finding": (f"org_sim が mgr_overhead を {mgr_overhead_measured} と接地（model 既定 {model_default} と一致）。"
                    f"c_comm（コール単位）≈0（共有文脈調整）→ winner({winner_at_zero}) が org_sim の flat 勝ちと一致。"),
        "falsifier": "測定 mgr_overhead が model 既定から大きく外れる、または c_comm≈0 で winner が flat 以外なら"
                     "本接地は崩れる（coordination.py の AI レジーム想定が偽）。",
    }


def _md(r: dict) -> str:
    mo = r["mgr_overhead"]
    L = ["# 通信コスト較正 — coordination.py を org_sim 実測で接地",
         "",
         "coordination.py（解析）のコストはコール数でなく抽象単位だった。org_sim（実エージェント）の"
         "コール数で **mgr_overhead** と **c_comm** を接地する。",
         "",
         "## 実測コール数（org_sim）",
         f"- flat={r['measured_calls']['flat']} / hierarchy={r['measured_calls']['hierarchy']} / "
         f"market={r['measured_calls']['market']}",
         "",
         "## 接地",
         f"- **mgr_overhead = hierarchy − flat = {mo['measured']}**（管理者の分解+統合2コール）"
         f"／model 既定 {mo['model_default']} と **{'一致' if mo['match'] else '不一致'}**。",
         f"- market OH = market − flat = {r['market_overhead_measured']}（入札1コール）。",
         f"- **c_comm（コール単位）≈ {r['c_comm_in_calls']}**: flat の調整は共有文脈経由＝追加コール無し。"
         f"→ AI は「c_comm 低 → flat 勝ち」レジーム。",
         "",
         "## 検証: 測定 mgr_overhead を入れた winner() の c_comm スイープ",
         "| c_comm | winner | flat | hierarchy | market |",
         "|---|---|---|---|---|"]
    for s in r["sweep"]:
        mark = "**" if s["winner"] == "flat" else ""
        L.append(f"| {s['c_comm']} | {mark}{s['winner']}{mark} | {s['flat']} | {s['hierarchy']} | {s['market']} |")
    L += ["",
          f"→ c_comm≈0 で winner = **{r['winner_at_c_comm_0']}**（org_sim の flat 勝ちと一致）。",
          "",
          "## 含意",
          "- AI 設定では通信が*共有文脈*で安く（コール単位 c_comm≈0）、階層の mgr_overhead が死荷重になり flat が勝つ。"
          "解析 coordination.py の低-c_comm レジームが実測で接地された。",
          "",
          "## 反証条件",
          f"- {r['falsifier']}"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "calibrate_coord_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "CALIBRATE_COORD.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print(f"mgr_overhead measured={r['mgr_overhead']['measured']} (model={r['mgr_overhead']['model_default']}, "
          f"match={r['mgr_overhead']['match']})")
    print(f"c_comm~0 winner={r['winner_at_c_comm_0']} (org_sim: flat)")
    print("wrote calibrate_coord_results.json and CALIBRATE_COORD.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
