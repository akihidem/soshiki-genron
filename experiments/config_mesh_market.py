"""config_mesh_market — 検証ルーティング市場を実モデル grid から導出（§5 p*=w/s の実測）。

profile（能力は梯子でなく非単調）が判明した後の capstone。各タスクを 安い→高い tier に投げ
verifier(held-out)を通った最初の tier で止める「検証ルーティング市場」を、既に測った 3-tier grid
（7B/24B/122B × tasks の held_solve_rate）から導出し、(コスト, 正しさ) を単一モデル flat と比較。

市場が非単調 profile を吸収できる理由＝能力順を仮定せず*検証*で止めるから。
run: python3 -m experiments.config_mesh_market
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# cheap -> expensive。weight = 相対コスト代理（price/compute proxy）。
TIERS = [("qwen2.5-coder:7b", "7B", 1.0),
         ("devstral", "24B", 3.0),
         ("qwen122", "122B", 10.0)]
TAGS = ["robust7b", "robust24b", "robust122b", "robust122b_extra"]
TASKS = ["negabinary", "calc3", "wildcard_plus", "calc"]
SOLVE = 0.5   # held_solve_rate >= 0.5 を「その tier が(再現的に)解く」とする


def load_grid():
    held = {}
    for tag in TAGS:
        p = os.path.join(HERE, f"config_mesh_rich_{tag}_results.json")
        if not os.path.exists(p):
            continue
        for r in json.load(open(p))["rows"]:
            held[(r["model"], r["task"])] = r["heldout_solve_rate"]
    return held


def solves(held, model, task):
    return held.get((model, task), 0.0) >= SOLVE


def main():
    held = load_grid()
    print("=== 3-tier grid (held_solve_rate, trials=3) ===")
    print(f"{'task':<14}" + "".join(f"{n:>8}" for _, n, _ in TIERS))
    for t in TASKS:
        print(f"{t:<14}" + "".join(f"{held.get((m, t), float('nan')):>8.2f}" for m, _, _ in TIERS))

    # --- 市場: cheap->expensive、最初に解いた tier で停止。cost=試した tier の weight 累積 ---
    print("\n=== verification-routing market (cheap->expensive, stop at first pass) ===")
    market_cost = 0.0
    market_solved = 0
    for t in TASKS:
        cost = 0.0
        routed = None
        for m, name, w in TIERS:
            cost += w
            if solves(held, m, t):
                routed = name
                break
        market_cost += cost
        market_solved += 1 if routed else 0
        print(f"  {t:<14} -> {routed or 'UNSOLVED':<8} cost={cost:>5.1f}")
    n = len(TASKS)

    # --- flat ベースライン ---
    print("\n=== comparison (cost, correctness) — lower cost & higher solved is better ===")
    rows = []
    for m, name, w in TIERS:
        fc = w * n
        fs = sum(1 for t in TASKS if solves(held, m, t))
        rows.append((f"flat-{name}", fc, fs))
    rows.append(("MARKET", market_cost, market_solved))
    print(f"  {'strategy':<12}{'cost':>8}{'solved':>10}")
    for name, c, s in rows:
        print(f"  {name:<12}{c:>8.1f}{f'{s}/{n}':>10}")

    best_single_cost = next(c for nm, c, s in rows if nm == "flat-122B")
    print(f"\n読み: 市場は {market_solved}/{n} を cost {market_cost:.1f} で達成。"
          f"flat-122B は同 {n} を cost {best_single_cost:.1f}。"
          f" → 市場は単一最強モデルを (コスト, 正しさ) で {'Pareto 支配' if market_cost < best_single_cost and market_solved >= next(s for nm, c, s in rows if nm == 'flat-122B') else '非支配'}。")
    print("p*=w/s: 安い tier が再現的に解くタスク(negabinary/calc3)ほど市場が安く勝つ。")


if __name__ == "__main__":
    main()
