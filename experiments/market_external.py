"""実証: 外部正解スイートでの heterogeneity 再検定 (market_external.py)

異種 market 検定（`org_sim.py --hetero`）は heterogeneity 便益が出ず、しかも「正しさ=self-test
通過率」がモデル依存で交絡（強モデルほど厳しいテストを書き自滅）と判明した（PAPER §9-6）。ここでは
交絡を外して再検定する:

- 正しさを **モデル非依存の外部正解スイート（gold tests）** で測る。モデルは *実装だけ* 書き、テストは
  こちらの固定 gold で採点する（self-test の交絡を除去）。
- **難度勾配のあるタスク**（roman / merge_intervals / wildcard match ── 弱モデルが*客観的*に落ちる
  余地のある古典問題）を使う。
- 検証ルーティング型エスカレーション市場（haiku→sonnet→opus・gold 正しさ<1.0 の間だけ上位へ・配分は
  自己申告でなく*外部検証*）が、単一モデル flat の (コスト, 正しさ) 前線を支配するかを測る。

予測: 難タスクで haiku が落ち opus が通れば、market は opus 並みの正しさを opus 未満コストで出す
（heterogeneity 便益が顕在）。出なければ「市場は難度勾配があっても勝たない」も有効な所見。
コスト = ティア重み（~1:3:15 = 定価比の代理）× impl コール数（各試行1コール）。free 枠経由。
run: python3 -m experiments.market_external --agent claude:real
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from experiments.org_sim import _PYTEST_SHIM, _UNSHARE, _agent, _extract_code, _mock  # noqa: E402


# Tasks with a model-INDEPENDENT gold suite (objective truth, not self-tests).
# Difficulty gradient: a weak model can plausibly pass the easy cases yet fail edges.
EXT_TASKS = [
    {"id": "roman", "names": ["int_to_roman", "roman_to_int"],
     "spec": ("int_to_roman(n) for 1<=n<=3999 -> standard uppercase Roman numeral with subtractive "
              "notation (4=IV, 9=IX, 40=XL, 90=XC, 400=CD, 900=CM). roman_to_int(s) -> int, the inverse."),
     "gold": (
         'def gold_r1(): assert int_to_roman(1) == "I"\n'
         'def gold_r2(): assert int_to_roman(4) == "IV"\n'
         'def gold_r3(): assert int_to_roman(9) == "IX"\n'
         'def gold_r4(): assert int_to_roman(58) == "LVIII"\n'
         'def gold_r5(): assert int_to_roman(1994) == "MCMXCIV"\n'
         'def gold_r6(): assert int_to_roman(3888) == "MMMDCCCLXXXVIII"\n'
         'def gold_r7(): assert roman_to_int("III") == 3\n'
         'def gold_r8(): assert roman_to_int("IV") == 4\n'
         'def gold_r9(): assert roman_to_int("MCMXCIV") == 1994\n'
         'def gold_r10(): assert all(roman_to_int(int_to_roman(k)) == k for k in (1,4,9,40,90,400,900,3549,3999))\n'
     )},
    {"id": "intervals", "names": ["merge_intervals"],
     "spec": ("merge_intervals(intervals): intervals is a list of [start,end] (end>=start, ints). Return the "
              "list of merged, non-overlapping intervals sorted by start. Touching intervals merge "
              "([1,3],[3,5]->[1,5]); input may be unsorted; [] -> []."),
     "gold": (
         'def _N(r): return [list(x) for x in r]\n'  # accept tuples or lists
         'def gold_m1(): assert _N(merge_intervals([[1,3],[2,6],[8,10],[15,18]])) == [[1,6],[8,10],[15,18]]\n'
         'def gold_m2(): assert _N(merge_intervals([[1,4],[4,5]])) == [[1,5]]\n'
         'def gold_m3(): assert _N(merge_intervals([])) == []\n'
         'def gold_m4(): assert _N(merge_intervals([[1,4]])) == [[1,4]]\n'
         'def gold_m5(): assert _N(merge_intervals([[1,4],[2,3]])) == [[1,4]]\n'
         'def gold_m6(): assert _N(merge_intervals([[8,10],[1,3],[2,6],[15,18]])) == [[1,6],[8,10],[15,18]]\n'
         'def gold_m7(): assert _N(merge_intervals([[1,4],[5,6]])) == [[1,4],[5,6]]\n'
     )},
    {"id": "wildcard", "names": ["is_match"],
     "spec": ("is_match(s, p): whether pattern p matches the ENTIRE string s, where '?' matches any single "
              "character and '*' matches any sequence of characters (including empty). No other special chars."),
     "gold": (
         'def gold_w1(): assert is_match("aa","a") == False\n'
         'def gold_w2(): assert is_match("aa","*") == True\n'
         'def gold_w3(): assert is_match("cb","?a") == False\n'
         'def gold_w4(): assert is_match("adceb","*a*b") == True\n'
         'def gold_w5(): assert is_match("acdcb","a*c?b") == False\n'
         'def gold_w6(): assert is_match("","") == True\n'
         'def gold_w7(): assert is_match("","*") == True\n'
         'def gold_w8(): assert is_match("abc","a?c") == True\n'
         'def gold_w9(): assert is_match("abefcdgiescdfimde","ab*cd?i*de") == True\n'
         'def gold_w10(): assert is_match("mississippi","m*issi*p*i") == False\n'
     )},
]

_TIERS = (("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0))
_CALL = _agent  # swapped to _mock for tests / --agent mock

# Runs ONLY gold_* functions -> the model's own test_* (if any leaked in) are ignored.
_GOLD_HARNESS = (
    '\n\nif True:\n'
    '    _g = dict(globals())\n'
    '    _fns = [v for k, v in _g.items() if k.startswith("gold_") and callable(v) and not isinstance(v, type)]\n'
    '    _p = _n = 0\n'
    '    for _f in _fns:\n'
    '        _n += 1\n'
    '        try:\n'
    '            _f(); _p += 1\n'
    '        except Exception:\n'
    '            pass\n'
    '    print("CORRECT", _p, _n)\n'
)


def gen_impl(model: str, task: dict) -> str:
    names = ", ".join(task["names"])
    return _CALL(model, f"Implement these Python functions to satisfy the spec EXACTLY, handling ALL edge "
                        f"cases. Spec: {task['spec']}\nRequired functions: {names}.\n"
                        f"Output ONLY runnable Python code — no tests, no explanation, no prose.")


def grade(impl: str, task: dict, timeout: int = 12) -> dict:
    """Run the model's impl against the GOLD suite in a no-net/no-pid sandbox. A non-running
    impl scores 0.0 (a crash IS a failure against external truth, unlike self-test grading)."""
    import resource
    import tempfile
    code = _PYTEST_SHIM + _extract_code(impl) + "\n" + task["gold"] + _GOLD_HARNESS
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name

    def _limits():
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)

    base = ["python3", path]
    cmd = (["unshare", "--user", "--net", "--pid", "--fork", "--mount-proc"] + base) if _UNSHARE else base
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 4, preexec_fn=_limits)
        m = re.search(r"CORRECT (\d+) (\d+)", proc.stdout)
        if m:
            p, n = int(m.group(1)), int(m.group(2))
            return {"passed": p, "total": n, "correctness": round(p / n, 3) if n else 0.0, "ran": True}
        return {"passed": 0, "total": 0, "correctness": 0.0, "ran": False,
                "err": ((proc.stderr or proc.stdout) or "")[:160]}
    except Exception as e:
        return {"passed": 0, "total": 0, "correctness": 0.0, "ran": False, "err": str(e)[:160]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run_ext(tasks=EXT_TASKS, tiers=_TIERS, cache_path: str | None = None) -> dict:
    # one impl per (model, task), cached & resumable; baselines + escalation market derived from it.
    grid, arts = {}, {}
    if cache_path and os.path.exists(cache_path):
        arts = json.load(open(cache_path, encoding="utf-8"))
    for model, _w in tiers:
        for t in tasks:
            key = f"{t['id']}|{model}"
            if arts.get(key) and "def " in arts[key]:
                impl = arts[key]
            else:
                impl = gen_impl(model, t)
                arts[key] = impl
                if cache_path:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(arts, f, ensure_ascii=False, indent=2, sort_keys=True)
            g = grade(impl, t)
            grid[(model, t["id"])] = {"corr": g["correctness"], "passed": g["passed"], "total": g["total"]}

    def _avg(rows, k):
        return round(sum(r[k] for r in rows) / len(rows), 3)

    baselines = {}
    for model, w in tiers:
        rows = [{"task": t["id"], "cost": w, "correctness": grid[(model, t["id"])]["corr"],
                 "tests": f"{grid[(model, t['id'])]['passed']}/{grid[(model, t['id'])]['total']}"} for t in tasks]
        baselines[model] = {"rows": rows, "avg_cost": _avg(rows, "cost"), "avg_correctness": _avg(rows, "correctness")}

    mkt = []
    for t in tasks:
        cost, best, ladder = 0.0, 0.0, []
        for model, w in tiers:
            g = grid[(model, t["id"])]
            cost += w                                    # one impl call at this tier
            ladder.append([model, round(g["corr"], 3)])
            best = max(best, g["corr"])
            if g["corr"] >= 1.0:                         # external verification satisfied -> stop paying
                break
        mkt.append({"task": t["id"], "cost": round(cost, 1), "correctness": round(best, 3), "ladder": ladder})
    market = {"rows": mkt, "avg_cost": _avg(mkt, "cost"), "avg_correctness": _avg(mkt, "correctness")}
    return {"tiers": [[m, w] for m, w in tiers], "n_tasks": len(tasks),
            "baselines": baselines, "market": market, "artifacts": arts}


def _md(r: dict) -> str:
    b, m = r["baselines"], r["market"]
    L = ["# 実証: 外部正解スイートでの heterogeneity 再検定",
         "",
         "self-test 交絡（強モデルほど厳しいテストを書き自滅）を外し、**モデル非依存の固定 gold テスト**で "
         "正しさを採点。モデルは実装だけ書く。難度勾配のあるタスク（roman / merge_intervals / wildcard）で "
         "**検証ルーティング型エスカレーション市場**（gold 正しさ<1.0 の間だけ上位ティアへ）が単一モデル flat の "
         f"(コスト, 正しさ) 前線を支配するかを測る。タスク {r['n_tasks']} 件。生数値 "
         "[`market_external_results.json`](market_external_results.json)。",
         "",
         "## (コスト, 正しさ) — 低コスト×高正しさが良い",
         "| 戦略 | 平均コスト（ティア重み×コール） | 平均正しさ(gold) |",
         "|---|---|---|"]
    for model, _w in r["tiers"]:
        L.append(f"| flat-{model}（均質） | {b[model]['avg_cost']} | {b[model]['avg_correctness']} |")
    L.append(f"| **market（異種・エスカレーション）** | **{m['avg_cost']}** | **{m['avg_correctness']}** |")
    L += ["",
          "## 読み",
          "- market が flat-opus 並みの正しさを**より低いコスト**で出せば → **heterogeneity 便益が顕在**（外部正解で確認＝self-test 交絡なし）。",
          "- 弱モデルが難タスクで落ち、上位だけが gold を通せば、エスカレーションは「必要な所だけ高価な能力を買う」＝市場の本領。",
          "- それでも market が単一モデルに勝てなければ「難度勾配があっても市場配分は単一モデルを上回らない」＝有効な否定的所見。",
          "",
          "## タスク別 gold 正しさ（model:正しさ）と市場の梯子",
          "| task | flat-haiku | flat-sonnet | flat-opus | market 梯子 | market (cost, 正しさ) |",
          "|---|---|---|---|---|---|"]
    for i, t in enumerate(r.get("_task_ids", [row["task"] for row in m["rows"]])):
        h = b["haiku"]["rows"][i]["correctness"]
        s = b["sonnet"]["rows"][i]["correctness"]
        o = b["opus"]["rows"][i]["correctness"]
        mr = m["rows"][i]
        ladder = " → ".join(f"{mm}:{cc}" for mm, cc in mr["ladder"])
        L.append(f"| {t} | {h} | {s} | {o} | {ladder} | ({mr['cost']}, {mr['correctness']}) |")
    L += ["",
          "## 妥当性",
          "- gold は固定の外部正解（モデル非依存）。各試行は impl 1コール（設計/テスト工程なし＝モデル能力を分離）。"
          "コストはティア重み（定価比の代理）×コール。難タスク3件・trials=1（少標本）。sandbox 実行（unshare 隔離）。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="heterogeneity re-test on an external gold suite")
    ap.add_argument("--agent", default="mock", help="'mock' or claude:<anything> (tiers are fixed haiku/sonnet/opus)")
    ap.add_argument("--tasks", type=int, default=len(EXT_TASKS))
    args = ap.parse_args(argv)
    _CALL = _mock if args.agent == "mock" else _agent
    out_dir = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(out_dir, "market_external_artifacts.json")
    r = run_ext(EXT_TASKS[:max(1, args.tasks)], cache_path=cache)
    arts = r.pop("artifacts", {})
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "market_external_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "MARKET_EXTERNAL.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print("baselines (cost, correctness):",
          {k: (v["avg_cost"], v["avg_correctness"]) for k, v in r["baselines"].items()})
    print("market   (cost, correctness):", (r["market"]["avg_cost"], r["market"]["avg_correctness"]))
    for row in r["market"]["rows"]:
        print(f"  {row['task']:<10} ladder={row['ladder']} -> cost={row['cost']} correct={row['correctness']}")
    print("\nwrote market_external_results.json and MARKET_EXTERNAL.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
