"""実証: バグ修復の脱相関 — frontier の「縁」を*修復*タスクで探す（SWE-bench の本質）。

生成タスクでは frontier(opus/codex)は誤らず脱相関ゼロだった（PAPER §5・145 意地悪ケースでも0失敗）。
だが *修復*（既存コードの微妙なバグを見つけて直す）は生成より難しく、ベンダで*違うバグ*を捕まえうる
（＝脱相関）。各タスクに微妙なバグ（挿入演算欠落・符号欠落・int除算・first条件欠落…）を仕込み、
opus/codex/sonnet に「直せ」と投げ、外部 gold で採点。**異なるモデルが異なるタスクを直せば union>単独**
＝補完能力 mesh が frontier の縁で点火する直接証拠（PAPER §6.5 の「縁の組織形態」を frontier で）。

バグ版が gold を落とすことは参照検算済み。free 枠＋codex（メーター）。
run: python3 -m experiments.repair --agent claude:real
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from experiments.market_external import _agent, _mock, _route, grade  # noqa: E402

_CALL = _agent

# Each: a SUBTLE bug (fails 1-2 gold cases, not obviously broken) + the correct-behaviour gold.
_BUGGY = [
    {"id": "edit_distance", "spec": "Levenshtein edit distance between two strings",
     "gold": ('def gold_1(): assert edit_distance("","") == 0\n'
              'def gold_2(): assert edit_distance("kitten","sitting") == 3\n'
              'def gold_3(): assert edit_distance("","abc") == 3\n'
              'def gold_4(): assert edit_distance("horse","ros") == 3\n'),
     "buggy": ("def edit_distance(a, b):\n    m, n = len(a), len(b)\n"
               "    dp = [[0]*(n+1) for _ in range(m+1)]\n"
               "    for i in range(m+1): dp[i][0] = i\n    for j in range(n+1): dp[0][j] = j\n"
               "    for i in range(1, m+1):\n        for j in range(1, n+1):\n"
               "            if a[i-1] == b[j-1]: dp[i][j] = dp[i-1][j-1]\n"
               "            else: dp[i][j] = 1 + min(dp[i-1][j-1], dp[i-1][j])\n"
               "    return dp[m][n]\n")},
    {"id": "re_match", "spec": "regex match where '.' is any char and '*' is zero-or-more of the preceding",
     "gold": ('def gold_1(): assert re_match("aa","a") == False\n'
              'def gold_2(): assert re_match("aa","a*") == True\n'
              'def gold_3(): assert re_match("ab",".*") == True\n'
              'def gold_4(): assert re_match("mississippi","mis*is*p*.") == False\n'),
     "buggy": ("def re_match(s, p):\n    from functools import lru_cache\n    @lru_cache(None)\n"
               "    def dp(i, j):\n        if j == len(p): return i == len(s)\n"
               "        first = i < len(s) and p[j] in (s[i], '.')\n"
               "        if j+1 < len(p) and p[j+1] == '*':\n            return dp(i, j+2) or dp(i+1, j)\n"
               "        return first and dp(i+1, j+1)\n    return dp(0, 0)\n")},
    {"id": "fraction", "spec": "num/den as a decimal string, repeating part in parentheses; handle sign",
     "gold": ('def gold_1(): assert fraction_to_decimal(1,2) == "0.5"\n'
              'def gold_2(): assert fraction_to_decimal(-50,8) == "-6.25"\n'
              'def gold_3(): assert fraction_to_decimal(2,3) == "0.(6)"\n'),
     "names": ["fraction_to_decimal"],
     "buggy": ("def fraction_to_decimal(num, den):\n    if num == 0: return '0'\n"
               "    res = str(num//den); rem = num % den\n    if rem == 0: return res\n"
               "    res += '.'; seen = {}; f = ''\n    while rem:\n"
               "        if rem in seen: i = seen[rem]; return res + f[:i] + '(' + f[i:] + ')'\n"
               "        seen[rem] = len(f); rem *= 10; f += str(rem//den); rem %= den\n    return res + f\n")},
    {"id": "calc3", "spec": "evaluate + - * / with parens; integer division truncates TOWARD ZERO",
     "gold": ('def gold_1(): assert calc3("14-3/2") == 13\n'
              'def gold_2(): assert calc3("3+2*2") == 7\n'
              'def gold_3(): assert calc3("2*(5+5*2)+3") == 33\n'),
     "buggy": ("def calc3(s):\n    s = s.replace(' ', '')\n    def ap(st, sg, nm):\n"
               "        if sg=='+': st.append(nm)\n        elif sg=='-': st.append(-nm)\n"
               "        elif sg=='*': st.append(st.pop()*nm)\n        elif sg=='/': st.append(st.pop()//nm)\n"
               "    def h(i):\n        st=[]; nm=0; sg='+'\n        while i < len(s):\n            c=s[i]\n"
               "            if c.isdigit(): nm=nm*10+int(c); i+=1\n"
               "            elif c=='(': nm,i=h(i+1)\n            else:\n                ap(st,sg,nm); nm=0\n"
               "                if c==')': return sum(st), i+1\n                sg=c; i+=1\n"
               "        ap(st,sg,nm); return sum(st), i\n    return h(0)[0]\n")},
]


def _repair(model: str, task: dict) -> str:
    names = ", ".join(task.get("names", [task["id"]]))
    return _CALL(model, f"The following Python code is intended to compute {names} ({task['spec']}) but "
                        f"contains a BUG that makes some cases wrong. Find and fix the bug.\n\n"
                        f"```python\n{task['buggy']}```\n\nOutput ONLY the corrected, runnable code — no prose.")


def run_repair(models=("opus", "codex", "sonnet"), tasks=tuple(_BUGGY), cache_path: str | None = None) -> dict:
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    fixed = {}                                            # (model, task) -> 1 if the fix passes full gold
    for t in tasks:
        for m in models:
            key = f"{t['id']}|{m}"
            if not (cache.get(key) and "def " in cache[key]):
                cache[key] = _repair(m, t)
                if cache_path:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
            fixed[(m, t["id"])] = 1 if (grade(cache[key], t)["correctness"] or 0) >= 1.0 else 0
    per_model = {m: round(sum(fixed[(m, t["id"])] for t in tasks) / len(tasks), 3) for m in models}
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            union = round(sum(max(fixed[(a, t["id"])], fixed[(b, t["id"])]) for t in tasks) / len(tasks), 3)
            best = max(per_model[a], per_model[b])
            comp = [t["id"] for t in tasks if fixed[(a, t["id"])] != fixed[(b, t["id"])]]
            pairs.append({"pair": f"{a} + {b}", "union": union, "best_single": round(best, 3),
                          "gain": round(union - best, 3), "complementary": comp})
    return {"models": list(models), "fixed": {f"{m}|{t['id']}": fixed[(m, t["id"])] for m in models for t in tasks},
            "per_model": per_model, "pairs": pairs, "artifacts": cache}


def _md(r: dict) -> str:
    L = ["# 実証: バグ修復の脱相関 — frontier の縁を*修復*で探す",
         "",
         "生成では frontier 0 失敗・脱相関ゼロ。*修復*（微妙なバグを見つけ直す）は難しく、ベンダで違うバグを"
         "捕まえうる。union>単独 なら **補完能力 mesh が frontier の縁で点火**（PAPER §6.5）。",
         "",
         "## 修復成功（1=全gold通過）",
         "| task | " + " | ".join(r["models"]) + " |",
         "|" + "---|" * (len(r["models"]) + 1)]
    for tid in [t["id"] for t in _BUGGY]:
        L.append(f"| {tid} | " + " | ".join(str(r["fixed"][f'{m}|{tid}']) for m in r["models"]) + " |")
    L += ["", f"per-model 修復率: {r['per_model']}", "",
          "## ペア union vs 単独最良（gain>0 ＝ frontier で mesh 点火）",
          "| ペア | union | 単独最良 | gain | 相補（片方だけ直す） |",
          "|---|---|---|---|---|"]
    for p in r["pairs"]:
        L.append(f"| {p['pair']} | {p['union']} | {p['best_single']} | **{p['gain']:+}** | "
                 f"{', '.join(p['complementary']) or '—'} |")
    L += ["", "## 読み",
          "- **gain>0 ＝ frontier 異種ベンダでも修復は脱相関**＝補完能力 mesh が*実タスク級*で点火（生成では出なかった創発）。",
          "- gain≈0 ＝ 修復でも frontier は同じ所を直す/直せない（相関）＝縁はさらに先。少標本・trials=1。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="bug-repair decorrelation across frontier vendors")
    ap.add_argument("--agent", default="mock", help="'mock' or claude:<anything>")
    args = ap.parse_args(argv)
    _CALL = _mock if args.agent == "mock" else _route
    out_dir = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(out_dir, "repair_artifacts.json")
    r = run_repair(cache_path=cache)
    with open(os.path.join(out_dir, "repair_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "REPAIR.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print("repair rate:", r["per_model"])
    for p in r["pairs"]:
        print(f"  {p['pair']:<18} union={p['union']} best={p['best_single']} gain={p['gain']:+} comp={p['complementary']}")
    print("\nwrote repair_results.json and REPAIR.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
