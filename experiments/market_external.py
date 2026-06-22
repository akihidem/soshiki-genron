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
from experiments.oversight.overseer import _ollama_generate  # noqa: E402


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
         'def gold_w10(): assert is_match("mississippi","m*issi*p*i") == True\n'
     )},
]

_TIERS = (("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0))

# --gap: LARGE capability gap. The frontier-only test found no gradient (all 1.0).
# Here a tiny local model (gemma ~2B) is the cheapest tier, with a difficulty SPREAD:
# easy tasks the tiny model can do (cheaply) + hard tasks only the frontier solves.
# Cost weights: gemma local ~0.2 (near-free) << haiku 1 << opus 15 (price-ratio proxy).
_TIERS_GAP = (("gemma4:e2b", 0.2), ("haiku", 1.0), ("opus", 15.0))
_HOST = "http://localhost:11434"

_EASY_TASKS = [
    {"id": "clamp", "names": ["clamp"],
     "spec": "clamp(x, lo, hi): return x bounded to the inclusive range [lo, hi] (lo <= hi).",
     "gold": (
         'def gold_c1(): assert clamp(5,0,10) == 5\n'
         'def gold_c2(): assert clamp(-3,0,10) == 0\n'
         'def gold_c3(): assert clamp(99,0,10) == 10\n'
         'def gold_c4(): assert clamp(0,0,10) == 0\n'
         'def gold_c5(): assert clamp(10,0,10) == 10\n'
     )},
    {"id": "leap", "names": ["is_leap"],
     "spec": "is_leap(year): Gregorian leap year — divisible by 4, except centuries unless divisible by 400.",
     "gold": (
         'def gold_l1(): assert is_leap(2000) == True\n'
         'def gold_l2(): assert is_leap(1900) == False\n'
         'def gold_l3(): assert is_leap(2024) == True\n'
         'def gold_l4(): assert is_leap(2023) == False\n'
         'def gold_l5(): assert is_leap(2100) == False\n'
     )},
    {"id": "revwords", "names": ["reverse_words"],
     "spec": ("reverse_words(s): reverse the order of single-space-separated words; output joined by single "
              "spaces, no leading/trailing space."),
     "gold": (
         'def gold_v1(): assert reverse_words("hello world") == "world hello"\n'
         'def gold_v2(): assert reverse_words("a b c") == "c b a"\n'
         'def gold_v3(): assert reverse_words("x") == "x"\n'
         'def gold_v4(): assert reverse_words("one two three four") == "four three two one"\n'
     )},
]

# HARD tasks to drive the weak model's p DOWN toward the gemma->haiku threshold (w/s=0.2),
# so the dominance boundary p*=w/s can be crossed empirically. Gold verified by reference impls.
_HARD_TASKS = [
    {"id": "edit_distance", "names": ["edit_distance"],
     "spec": "edit_distance(a, b): Levenshtein distance — min single-char insertions, deletions, "
             "or substitutions to turn a into b.",
     "gold": (
         'def gold_e1(): assert edit_distance("","") == 0\n'
         'def gold_e2(): assert edit_distance("abc","abc") == 0\n'
         'def gold_e3(): assert edit_distance("","abc") == 3\n'
         'def gold_e4(): assert edit_distance("kitten","sitting") == 3\n'
         'def gold_e5(): assert edit_distance("horse","ros") == 3\n'
         'def gold_e6(): assert edit_distance("sunday","saturday") == 3\n'
     )},
    {"id": "decode_ways", "names": ["decode_ways"],
     "spec": "decode_ways(s): number of ways to decode a digit string where '1'..'26' map to 'A'..'Z'. "
             "A leading zero or an invalid pair yields 0; empty string yields 0.",
     "gold": (
         'def gold_d1(): assert decode_ways("12") == 2\n'
         'def gold_d2(): assert decode_ways("226") == 3\n'
         'def gold_d3(): assert decode_ways("0") == 0\n'
         'def gold_d4(): assert decode_ways("06") == 0\n'
         'def gold_d5(): assert decode_ways("10") == 1\n'
         'def gold_d6(): assert decode_ways("100") == 0\n'
         'def gold_d7(): assert decode_ways("11106") == 2\n'
         'def gold_d8(): assert decode_ways("") == 0\n'
     )},
    {"id": "re_match", "names": ["re_match"],
     "spec": "re_match(s, p): whether pattern p matches the ENTIRE string s, where '.' matches any single "
             "character and '*' matches zero or more of the PRECEDING element (regex semantics, LeetCode 10).",
     "gold": (
         'def gold_x1(): assert re_match("aa","a") == False\n'
         'def gold_x2(): assert re_match("aa","a*") == True\n'
         'def gold_x3(): assert re_match("ab",".*") == True\n'
         'def gold_x4(): assert re_match("aab","c*a*b") == True\n'
         'def gold_x5(): assert re_match("mississippi","mis*is*p*.") == False\n'
         'def gold_x6(): assert re_match("","") == True\n'
         'def gold_x7(): assert re_match("","a*") == True\n'
     )},
]

_CALL = _agent  # swapped to _mock (tests) / _route (--gap, routes gemma->ollama)


def _route(model: str, prompt: str, timeout: int | None = None) -> str:
    """Route by model name: gemma -> local ollama, everything else -> claude runner."""
    if model.startswith("gemma"):
        for _ in range(2):                               # ollama can hiccup; one retry
            try:
                out = _ollama_generate(_HOST, model, prompt, timeout=timeout or 240)
                if out.strip():
                    return out
            except Exception:
                pass
        return ""                                        # tiny model failed -> empty -> scored 0
    return _agent(model, prompt)                         # claude (has its own retry/backoff)

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
         "生数値は同梱の results.json。",
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
          "## タスク別 gold 正しさと市場の梯子",
          "| task | " + " | ".join(f"flat-{mm}" for mm, _ in r["tiers"]) + " | market 梯子 | market (cost, 正しさ) |",
          "|" + "---|" * (len(r["tiers"]) + 3)]
    for i, mr in enumerate(m["rows"]):
        cells = " | ".join(str(b[mm]["rows"][i]["correctness"]) for mm, _ in r["tiers"])
        ladder = " → ".join(f"{mm}:{cc}" for mm, cc in mr["ladder"])
        L.append(f"| {mr['task']} | {cells} | {ladder} | ({mr['cost']}, {mr['correctness']}) |")
    L += ["",
          "## 妥当性",
          "- gold は固定の外部正解（モデル非依存）。各試行は impl 1コール（設計/テスト工程なし＝モデル能力を分離）。"
          "コストはティア重み（定価比の代理）×コール。難タスク3件・trials=1（少標本）。sandbox 実行（unshare 隔離）。"]
    return "\n".join(L)


# threshold calibration: the only quantity that was noisy (trials=1) is the WEAK
# model's full-solve rate p. Frontier tiers have p=1 (established) -> assume strong
# always solves and only re-measure the weak model with trials>1 (gemma only, no
# flaky claude path). Maps the weak->strong pairs onto the dominance plane p > w/s.
_STRONG_TIERS = (("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0))


def calibrate(weak_model: str, tasks=_EASY_TASKS + EXT_TASKS, strong=_STRONG_TIERS,
              trials: int = 3, w: float = 0.2, cache_path: str | None = None) -> dict:
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    per_task = []
    for t in tasks:
        corrs = []
        for k in range(trials):
            key = f"{t['id']}|{weak_model}|{k}"
            if cache.get(key) is not None and "def " in cache[key]:
                impl = cache[key]
            else:
                impl = gen_impl(weak_model, t)
                cache[key] = impl
                if cache_path:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
            corrs.append(grade(impl, t)["correctness"])
        per_task.append({"task": t["id"],
                         "solve_rate": round(sum(1 for c in corrs if c >= 1.0) / trials, 3),
                         "mean_correctness": round(sum(corrs) / len(corrs), 3),
                         "trials": [round(c, 3) for c in corrs]})
    p = round(sum(x["solve_rate"] for x in per_task) / len(per_task), 4)
    pairs = [{"strong": sm, "w": w, "s": s, "w_over_s": round(w / s, 4), "p_weak": p,
              "dominates": p > w / s, "market_cost": round(w + (1 - p) * s, 4), "flat_strong_cost": s}
             for sm, s in strong]
    return {"weak": weak_model, "trials": trials, "p_weak": p, "per_task": per_task, "pairs": pairs}


_MAP_MODELS = ("gemma4:e2b", "gemma4:latest", "gemma4-chat:latest")


def map_models(models=_MAP_MODELS, trials: int = 2, cache_path: str | None = None) -> dict:
    """Calibrate several local weak models -> a dominance map over the (p_weak, w/s) plane."""
    rows = []
    for mdl in models:
        c = calibrate(mdl, trials=trials, cache_path=cache_path)
        rows.append({"weak": mdl, "p_weak": c["p_weak"],
                     "per_task": {x["task"]: x["solve_rate"] for x in c["per_task"]},
                     "pairs": c["pairs"]})
    return {"trials": trials, "strong": [list(t) for t in _STRONG_TIERS], "models": rows}


def _md_map(r: dict) -> str:
    L = ["# 支配地図 — 複数ローカル弱モデルを (p_weak, w/s) 平面に置く",
         "",
         f"支配定理 p\\*=w/s（[`../model/MARKET.md`](../model/MARKET.md)）に対し、ローカル弱モデル群の "
         f"完全解率 p_weak を測り、各 weak→strong ペアが支配領域に入るかを地図化（trials={r['trials']}）。",
         "",
         "## p_weak と支配（✓ = market が flat-strong を Pareto 支配 ＝ p>w/s）",
         "| 弱モデル | p_weak | →haiku (w/s=0.2) | →sonnet (0.067) | →opus (0.013) |",
         "|---|---|---|---|---|"]
    for m in r["models"]:
        dom = {p["strong"]: p["dominates"] for p in m["pairs"]}
        L.append(f"| {m['weak']} | **{m['p_weak']}** | {'✓' if dom['haiku'] else '—'} | "
                 f"{'✓' if dom['sonnet'] else '—'} | {'✓' if dom['opus'] else '—'} |")
    tasks = list(r["models"][0]["per_task"].keys())
    L += ["",
          "## per-task solve_rate（1.0 到達率）— どのタスクで能力差が出るか",
          "| 弱モデル | " + " | ".join(tasks) + " |",
          "|" + "---|" * (len(tasks) + 1)]
    for m in r["models"]:
        L.append(f"| {m['weak']} | " + " | ".join(str(m["per_task"][t]) for t in tasks) + " |")
    L += ["",
          "## 読み",
          "- 弱モデルが p>w/s（特に最も厳しい →haiku の閾値 0.2）を超える限り、市場は単一モデルを支配。",
          "- ローカル小型モデルが全て高 p（≫0.2）に固まるなら → 支配は頑健・境界(p≈0.2)は更に難しいタスクでのみ。",
          "- per-task で 0/1 に割れるタスクが*構造的*な能力差の在処（市場が高ティアを呼ぶ理由）。"]
    return "\n".join(L)


def _md_calib(r: dict) -> str:
    L = ["# 閾値の実測較正 — 弱モデルの完全解率 p を trials>1 で固める",
         "",
         f"支配定理 p\\*=w/s（[`../model/MARKET.md`](../model/MARKET.md)）の唯一 noisy な量＝弱ティアの完全解率 "
         f"p を **{r['weak']} × trials={r['trials']}** で較正。frontier は p=1 既知なので strong は解析(コストのみ)。",
         "",
         f"## 較正された p_weak = **{r['p_weak']}**（タスク別 solve_rate の平均）",
         "| task | solve_rate (= 1.0 到達率) | 平均正しさ | trials |",
         "|---|---|---|---|"]
    for x in r["per_task"]:
        L.append(f"| {x['task']} | {x['solve_rate']} | {x['mean_correctness']} | {x['trials']} |")
    L += ["",
          "## 支配地図：弱→強ペアが p_weak > w/s に入るか",
          "| 強ティア | w/s | p_weak | 支配(p>w/s) | market コスト | flat-strong コスト |",
          "|---|---|---|---|---|---|"]
    for pr in r["pairs"]:
        L.append(f"| {pr['strong']} | {pr['w_over_s']} | {pr['p_weak']} | "
                 f"{'**支配**' if pr['dominates'] else '—'} | {pr['market_cost']} | {pr['flat_strong_cost']} |")
    L += ["",
          "## 読み",
          "- p_weak が安定して w/s を超えるペアでは、エスカレーション市場が単一モデルを Pareto 支配（解析と整合）。",
          "- trials で solve_rate が 0/1 に張り付くなら gemma の能力は*構造的*（タスク依存）・中間値ならノイズ。",
          "",
          "## 妥当性",
          f"- gemma は ollama サンプリング（温度>0）で trials 変動。strong は p=1 既知で解析。w={r['pairs'][0]['w']}・"
          "コスト比は定価の代理。少標本（trials 小）。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="heterogeneity re-test on an external gold suite")
    ap.add_argument("--agent", default="mock", help="'mock' or claude:<anything> (frontier tiers fixed)")
    ap.add_argument("--gap", action="store_true",
                    help="LARGE capability gap: tiny gemma tier + easy/hard spread (routes gemma->ollama)")
    ap.add_argument("--calibrate", action="store_true",
                    help="trials>1 calibration of the weak model's full-solve rate p (gemma only)")
    ap.add_argument("--map", action="store_true", dest="domap",
                    help="dominance map over several local weak models (gemma e2b/latest/chat)")
    ap.add_argument("--hard", action="store_true",
                    help="use the HARD task set (drives weak p down toward the boundary p*=w/s)")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args(argv)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    if args.domap:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_calib_artifacts.json")   # shares the calibrate cache
        r = map_models(trials=max(1, args.trials), cache_path=cache)
        with open(os.path.join(out_dir, "market_map_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_MAP.md"), "w", encoding="utf-8") as f:
            f.write(_md_map(r) + "\n")
        for m in r["models"]:
            dom = {p["strong"]: p["dominates"] for p in m["pairs"]}
            print(f"  {m['weak']:<20} p_weak={m['p_weak']:<7} dominates: "
                  f"haiku={dom['haiku']} sonnet={dom['sonnet']} opus={dom['opus']}")
        print("\nwrote market_map_results.json and MARKET_MAP.md")
        return 0
    if args.calibrate:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_calib_artifacts.json")
        r = calibrate("gemma4:e2b", trials=max(1, args.trials), cache_path=cache)
        with open(os.path.join(out_dir, "market_calib_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_CALIB.md"), "w", encoding="utf-8") as f:
            f.write(_md_calib(r) + "\n")
        print(f"calibrated p_weak({r['weak']}, trials={r['trials']}) = {r['p_weak']}")
        for pr in r["pairs"]:
            print(f"  vs {pr['strong']:<7} w/s={pr['w_over_s']:<7} dominates={pr['dominates']} "
                  f"market={pr['market_cost']}")
        print("\nwrote market_calib_results.json and MARKET_CALIB.md")
        return 0
    if args.gap:
        _CALL = _mock if args.agent == "mock" else _route
        if args.hard:                                   # boundary probe: hard tasks drop weak p
            tasks, tiers, stem = _HARD_TASKS, _TIERS_GAP, "market_gap_hard"
        else:
            tasks, tiers, stem = _EASY_TASKS + EXT_TASKS, _TIERS_GAP, "market_gap"
    else:
        _CALL = _mock if args.agent == "mock" else _agent
        tasks, tiers, stem = EXT_TASKS, _TIERS, "market_external"
    cache = os.path.join(out_dir, f"{stem}_artifacts.json")
    r = run_ext(tasks, tiers=tiers, cache_path=cache)
    arts = r.pop("artifacts", {})
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(arts, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, f"{stem}_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, f"{stem.upper()}.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print("baselines (cost, correctness):",
          {k: (v["avg_cost"], v["avg_correctness"]) for k, v in r["baselines"].items()})
    print("market   (cost, correctness):", (r["market"]["avg_cost"], r["market"]["avg_correctness"]))
    for row in r["market"]["rows"]:
        print(f"  {row['task']:<10} ladder={row['ladder']} -> cost={row['cost']} correct={row['correctness']}")
    print(f"\nwrote {stem}_results.json and {stem.upper()}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
