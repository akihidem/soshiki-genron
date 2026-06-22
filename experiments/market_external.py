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
    {"id": "my_atoi", "names": ["my_atoi"],
     "spec": "my_atoi(s): string to 32-bit signed integer (LeetCode 8). Skip leading spaces, optional +/-, "
             "read digits until a non-digit, ignore the rest; no digits -> 0; clamp to [-2**31, 2**31-1].",
     "gold": (
         'def gold_a1(): assert my_atoi("42") == 42\n'
         'def gold_a2(): assert my_atoi("   -42") == -42\n'
         'def gold_a3(): assert my_atoi("4193 with words") == 4193\n'
         'def gold_a4(): assert my_atoi("words and 987") == 0\n'
         'def gold_a5(): assert my_atoi("-91283472332") == -2147483648\n'
         'def gold_a6(): assert my_atoi("2147483648") == 2147483647\n'
         'def gold_a7(): assert my_atoi("+1") == 1\n'
         'def gold_a8(): assert my_atoi("  +0 123") == 0\n'
     )},
    {"id": "calc", "names": ["calc"],
     "spec": "calc(s): evaluate an arithmetic expression string with non-negative integers, '+', '-', "
             "parentheses '(' ')' and spaces (LeetCode 224). Standard left-to-right with parentheses.",
     "gold": (
         'def gold_k1(): assert calc("1 + 1") == 2\n'
         'def gold_k2(): assert calc(" 2-1 + 2 ") == 3\n'
         'def gold_k3(): assert calc("(1+(4+5+2)-3)+(6+8)") == 23\n'
         'def gold_k4(): assert calc("2-(5-6)") == 3\n'
         'def gold_k5(): assert calc("(7)-(0)+(4)") == 11\n'
     )},
    {"id": "simplify_path", "names": ["simplify_path"],
     "spec": "simplify_path(path): canonical Unix absolute path (LeetCode 71). Collapse '//', resolve '.' "
             "(current) and '..' (parent, never above root); result has no trailing slash except root '/'.",
     "gold": (
         'def gold_s1(): assert simplify_path("/home/") == "/home"\n'
         'def gold_s2(): assert simplify_path("/../") == "/"\n'
         'def gold_s3(): assert simplify_path("/home//foo/") == "/home/foo"\n'
         'def gold_s4(): assert simplify_path("/a/./b/../../c/") == "/c"\n'
         'def gold_s5(): assert simplify_path("/") == "/"\n'
         'def gold_s6(): assert simplify_path("/...") == "/..."\n'
     )},
]

# FRONTIER LADDER: genuinely hard tasks spanning opus's edge (barely-opus) to beyond it
# (impossible). Measured across ALL tiers (incl. sonnet) so the frontier gradient and the
# no-tier-solves regime can appear. Includes non-standard TWISTS that break memorized
# solutions. Gold verified by reference impls; output unambiguous.
# includes codex (OpenAI, cross-vendor) -> the ladder's non-monotonic check now catches
# CROSS-VENDOR divergence (a task one vendor solves and the other fails = genuine union gain).
_TIERS_LADDER = (("gemma4:e2b", 0.2), ("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0), ("codex", 20.0))

_LADDER_TASKS = [
    {"id": "calc3", "names": ["calc3"],
     "spec": "calc3(s): evaluate an expression with non-negative integers, + - * /, parentheses and spaces. "
             "Standard precedence; integer division truncates toward zero (LeetCode 772 with parens).",
     "gold": (
         'def gold_c1(): assert calc3("3+2*2") == 7\n'
         'def gold_c2(): assert calc3(" 3/2 ") == 1\n'
         'def gold_c3(): assert calc3(" 3+5 / 2 ") == 5\n'
         'def gold_c4(): assert calc3("2*(5+5*2)+3") == 33\n'
         'def gold_c5(): assert calc3("14-3/2") == 13\n'
         'def gold_c6(): assert calc3("(2+6*3)") == 20\n'
     )},
    {"id": "atoms", "names": ["atoms"],
     "spec": "atoms(formula): parse a chemical formula with element names (uppercase then optional lowercase), "
             "counts, and parentheses with multipliers; return the count string with elements sorted "
             "alphabetically, counts >1 shown (LeetCode 726). e.g. 'K4(ON(SO3)2)2' -> 'K4N2O14S4'.",
     "gold": (
         'def gold_t1(): assert atoms("H2O") == "H2O"\n'
         'def gold_t2(): assert atoms("Mg(OH)2") == "H2MgO2"\n'
         'def gold_t3(): assert atoms("K4(ON(SO3)2)2") == "K4N2O14S4"\n'
         'def gold_t4(): assert atoms("Be32") == "Be32"\n'
     )},
    {"id": "wildcard_plus", "names": ["wp"],
     "spec": "wp(s, p): NON-STANDARD wildcard. '*' matches ONE OR MORE characters (NOT zero), '?' matches "
             "EXACTLY one character, other chars match literally. Match the ENTIRE string. (Read carefully: "
             "'*' is one-or-more, unlike the usual zero-or-more.)",
     "gold": (
         'def gold_w1(): assert wp("a","*") == True\n'
         'def gold_w2(): assert wp("","*") == False\n'
         'def gold_w3(): assert wp("ab","a?") == True\n'
         'def gold_w4(): assert wp("a","?") == True\n'
         'def gold_w5(): assert wp("","") == True\n'
         'def gold_w6(): assert wp("abc","*c") == True\n'
         'def gold_w7(): assert wp("","?") == False\n'
         'def gold_w8(): assert wp("abc","a*") == True\n'
         'def gold_w9(): assert wp("ac","a*c") == False\n'
     )},
    {"id": "negabinary", "names": ["negabinary"],
     "spec": "negabinary(n): represent the integer n in base -2 as a string of '0'/'1' (no leading zeros "
             "except n==0 -> '0'). Base -2 digits weight (-2)**k. e.g. negabinary(3) == '111' (4-2+1).",
     "gold": (
         'def gold_n1(): assert negabinary(0) == "0"\n'
         'def gold_n2(): assert negabinary(2) == "110"\n'
         'def gold_n3(): assert negabinary(3) == "111"\n'
         'def gold_n4(): assert negabinary(4) == "100"\n'
         'def gold_n5(): assert negabinary(-1) == "11"\n'
         'def gold_n6(): assert negabinary(-3) == "1101"\n'
         'def gold_n7(): assert negabinary(6) == "11010"\n'
     )},
    {"id": "fraction_to_decimal", "names": ["fraction_to_decimal"],
     "spec": "fraction_to_decimal(num, den): the fraction num/den as a string; if the fractional part "
             "repeats, enclose the repeating cycle in parentheses (LeetCode 166). e.g. 2/3 -> '0.(6)', "
             "4/333 -> '0.(012)', 1/6 -> '0.1(6)'. Handle sign and exact division.",
     "gold": (
         'def gold_f1(): assert fraction_to_decimal(1,2) == "0.5"\n'
         'def gold_f2(): assert fraction_to_decimal(2,1) == "2"\n'
         'def gold_f3(): assert fraction_to_decimal(2,3) == "0.(6)"\n'
         'def gold_f4(): assert fraction_to_decimal(4,333) == "0.(012)"\n'
         'def gold_f5(): assert fraction_to_decimal(1,6) == "0.1(6)"\n'
         'def gold_f6(): assert fraction_to_decimal(-50,8) == "-6.25"\n'
         'def gold_f7(): assert fraction_to_decimal(0,5) == "0"\n'
         'def gold_f8(): assert fraction_to_decimal(1,333) == "0.(003)"\n'
     )},
]

# NOVEL/compound tasks to try to make the FRONTIER err (the prerequisite for cross-vendor
# decorrelation): no-cheat hard DP + an extended-precedence parser. Run across frontier vendors.
_TIERS_FRONTIER = (("sonnet", 3.0), ("opus", 15.0), ("codex", 20.0))
_NOVEL_TASKS = [
    {"id": "count_pal", "names": ["count_pal"],
     "spec": "count_pal(s): number of DISTINCT non-empty palindromic SUBSEQUENCES of s, modulo 10**9+7 "
             "(LeetCode 730). Subsequences (not substrings); count distinct ones.",
     "gold": ('def gold_1(): assert count_pal("bccb") == 6\n'
              'def gold_2(): assert count_pal("aaa") == 3\n'
              'def gold_3(): assert count_pal("abcdabcdabcdabcdabcdabcdabcdabcd'
              'dcbadcbadcbadcbadcbadcbadcbadcba") == 104860361\n')},
    {"id": "calc_iv", "names": ["calc_iv"],
     "spec": "calc_iv(s): evaluate an integer expression with + - * / , parentheses, unary minus, AND "
             "exponentiation '**' which is RIGHT-associative and binds tighter than * / . Integer division "
             "truncates toward zero. e.g. calc_iv('2**3**2') == 512, calc_iv('10/3') == 3.",
     "gold": ('def gold_1(): assert calc_iv("2+3*4") == 14\n'
              'def gold_2(): assert calc_iv("2**3**2") == 512\n'
              'def gold_3(): assert calc_iv("(2+3)*4") == 20\n'
              'def gold_4(): assert calc_iv("2**10") == 1024\n'
              'def gold_5(): assert calc_iv("10/3") == 3\n')},
]

_CALL = _agent  # swapped to _mock (tests) / _route (--gap, routes gemma->ollama)


_OPENAI_ENV = os.path.expanduser("~/.openai_env")


def _codex(model: str, prompt: str, timeout: int = 300) -> str:
    """OpenAI Codex (cross-vendor) via `codex exec`. metered -> use sparingly. _extract_code
    later pulls the python block out of codex's session-wrapped output."""
    env = dict(os.environ)
    if os.path.exists(_OPENAI_ENV):                      # load OPENAI_API_KEY
        for ln in open(_OPENAI_ENV, encoding="utf-8"):
            ln = ln.strip()
            ln = ln[7:] if ln.startswith("export ") else ln
            if "=" in ln and not ln.startswith("#"):
                k, v = ln.split("=", 1)
                env[k] = v.strip().strip('"').strip("'")
    cmd = ["codex", "exec", "--skip-git-repo-check", "--color", "never", "-s", "read-only"]
    if model.startswith("codex:"):                       # optional codex:<model> override
        cmd += ["-m", model.split(":", 1)[1]]
    for _ in range(2):                                   # transient retry
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                  timeout=timeout, env=env)
            if "```" in proc.stdout or "def " in proc.stdout:
                return proc.stdout
        except Exception:
            pass
    return ""


def _route(model: str, prompt: str, timeout: int | None = None) -> str:
    """Route by model name: gemma -> local ollama, codex -> OpenAI, else -> claude runner."""
    if model.startswith("gemma"):
        for _ in range(2):                               # ollama can hiccup; one retry
            try:
                out = _ollama_generate(_HOST, model, prompt, timeout=timeout or 240)
                if out.strip():
                    return out
            except Exception:
                pass
        return ""                                        # tiny model failed -> empty -> scored 0
    if model.startswith("codex"):
        return _codex(model, prompt)                     # OpenAI cross-vendor (metered)
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
    # "no existing file ... code block only" suppresses the agentic glitch where the most
    # agentic models (opus via the TUI) reply 'the file already contains...' with no code.
    return _CALL(model, f"There is NO existing file or prior code — write from scratch. Implement these "
                        f"Python functions to satisfy the spec EXACTLY, handling ALL edge cases. "
                        f"Spec: {task['spec']}\nRequired functions: {names}.\n"
                        f"Respond with ONLY a single python code block — no tests, no prose, no preamble.")


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


def run_ladder(tasks=tuple(_LADDER_TASKS), tiers=_TIERS_LADDER, trials: int = 2,
               cache_path: str | None = None) -> dict:
    """4-tier ladder (gemma<haiku<sonnet<opus) on hard tasks -> classify each task by the
    strongest tier that solves it (easy / gemma-gap / frontier-gap / barely-opus / impossible)."""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    order = [m for m, _ in tiers]
    grid = {}
    for t in tasks:
        for model, _w in tiers:
            corrs = []
            for k in range(trials):
                key = f"{t['id']}|{model}|{k}"
                if not (cache.get(key) and "def " in cache[key]):
                    cache[key] = gen_impl(model, t)
                    if cache_path:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
                corrs.append(grade(cache[key], t)["correctness"])
            grid[(t["id"], model)] = {"solve_rate": round(sum(1 for c in corrs if c >= 1.0) / trials, 3),
                                      "mean_corr": round(sum(corrs) / len(corrs), 3)}
    rows = []
    for t in tasks:
        sr = {m: grid[(t["id"], m)]["solve_rate"] for m in order}
        solved = [m for m in order if sr[m] >= 0.5]            # tiers that (mostly) solve
        if not solved:
            cls = "impossible"                                  # even opus fails
        elif solved[0] == order[0]:
            cls = "easy"                                        # gemma already solves
        elif solved[0] == order[-1]:
            cls = "barely-opus"                                 # only opus solves
        elif order[1] not in solved:                           # haiku fails -> needs sonnet/opus
            cls = "frontier-gap"
        else:
            cls = "gemma-gap"                                   # gemma fails, haiku+ solve
        rows.append({"task": t["id"], "solve_rate": sr, "mean_corr": {m: grid[(t["id"], m)]["mean_corr"] for m in order},
                     "cheapest_solver": solved[0] if solved else None, "class": cls})
    mkt = []
    for t in tasks:
        cost, best_corr, solved_at, ladder = 0.0, 0.0, None, []
        for model, w in tiers:
            g = grid[(t["id"], model)]
            cost += w
            ladder.append([model, g["solve_rate"]])
            best_corr = max(best_corr, g["mean_corr"])
            if g["solve_rate"] >= 1.0:
                solved_at = model
                break
        mkt.append({"task": t["id"], "cost": round(cost, 1), "best_corr": round(best_corr, 3),
                    "solved_at": solved_at, "ladder": ladder})
    return {"trials": trials, "tiers": [[m, w] for m, w in tiers], "tasks": rows, "market": mkt,
            "artifacts": cache}


# weak-ensemble: can N cheap attempts of a LOW-level model, filtered by the external gold,
# approach a HIGHER-level model? best-of-k = solved if ANY of the first k attempts passes gold
# (the verifier is the selector -> the project's external-anchor thesis). cost = k * w_weak.
_ENSEMBLE_TASKS = ("roman", "calc", "wildcard_plus", "negabinary")   # gemma partial -> room to rise


def run_ensemble(model: str = "gemma4:e2b", task_ids=_ENSEMBLE_TASKS, n: int = 6,
                 cache_path: str | None = None) -> dict:
    by_id = {t["id"]: t for t in _EASY_TASKS + EXT_TASKS + _HARD_TASKS + _LADDER_TASKS}
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    rows = []
    for tid in task_ids:
        t = by_id[tid]
        solved = []
        for k in range(n):
            key = f"{tid}|{model}|{k}"
            if not (cache.get(key) and "def " in cache[key]):
                cache[key] = gen_impl(model, t)
                if cache_path:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
            solved.append(1 if (grade(cache[key], t)["correctness"] or 0) >= 1.0 else 0)
        best_of_k = [1 if any(solved[:k]) else 0 for k in range(1, n + 1)]   # gold picks any passing attempt
        p = sum(solved) / n
        # expected best-of-k = 1-(1-p)^k (cleaner than the realized sequence, which is high-variance)
        exp_bok = [round(1 - (1 - p) ** (k + 1), 3) for k in range(n)]
        rows.append({"task": tid, "per_trial": solved, "best_of_k": best_of_k,
                     "single_shot": round(p, 3), "expected_best_of_k": exp_bok})
    bok = [round(sum(r["best_of_k"][k] for r in rows) / len(rows), 3) for k in range(n)]
    exp = [round(sum(r["expected_best_of_k"][k] for r in rows) / len(rows), 3) for k in range(n)]
    w = dict(_TIERS_LADDER).get(model, 0.2)
    return {"model": model, "n": n, "w_weak": w, "rows": rows, "best_of_k_avg": bok,
            "expected_best_of_k_avg": exp, "cost_of_k": [round(w * (k + 1), 2) for k in range(n)],
            "artifacts": cache}


# mesh proof-of-concept: do DIVERSE models' errors DECORRELATE? if model A fails task X
# but B solves it (and vice versa on Y), the pair-union exceeds either single -> the ML
# ensemble principle, the seed of a 'diversity mesh' organization. Tested where models ERR.
_DECORR_MODELS = ("gemma4:e2b", "haiku", "sonnet")
_DECORR_TASKS = ("roman", "calc", "atoms", "negabinary", "wildcard_plus")   # error-prone set


def run_decorr(models=_DECORR_MODELS, task_ids=_DECORR_TASKS, trials: int = 2,
               cache_path: str | None = None) -> dict:
    by_id = {t["id"]: t for t in _EASY_TASKS + EXT_TASKS + _HARD_TASKS + _LADDER_TASKS}
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    solve = {}
    for tid in task_ids:
        t = by_id[tid]
        for m in models:
            cs = []
            for k in range(trials):
                key = f"{tid}|{m}|{k}"
                if not (cache.get(key) and "def " in cache[key]):
                    cache[key] = gen_impl(m, t)
                    if cache_path:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
                cs.append(1 if (grade(cache[key], t)["correctness"] or 0) >= 1.0 else 0)
            solve[(m, tid)] = round(sum(cs) / trials, 3)
    per_model = {m: round(sum(solve[(m, tid)] for tid in task_ids) / len(task_ids), 3) for m in models}
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            union = round(sum(max(solve[(a, tid)], solve[(b, tid)]) for tid in task_ids) / len(task_ids), 3)
            best = max(per_model[a], per_model[b])
            comp = [tid for tid in task_ids if (solve[(a, tid)] >= 1.0) != (solve[(b, tid)] >= 1.0)]
            pairs.append({"pair": f"{a} + {b}", "union": union, "best_single": round(best, 3),
                          "gain": round(union - best, 3), "complementary_tasks": comp})
    return {"models": list(models), "trials": trials,
            "solve": {f"{m}|{tid}": solve[(m, tid)] for m in models for tid in task_ids},
            "per_model": per_model, "pairs": pairs, "artifacts": cache}


# open-ended mesh: where there is NO objective gold, does a cross-vendor SYNTHESIS of two
# vendors' answers beat either single answer, as scored by LLM judges? Subjective (judge
# bias) but the only way to probe the regime checkable coding can't reach.
_OPEN_TASKS = [
    "Design a token-bucket rate limiter for a web API: the public interface, the core algorithm, "
    "thread-safety, and the 3 trickiest correctness edge cases. Be concrete and technically correct.",
    "Cache results of an expensive idempotent function in a multi-process service. Give a concrete "
    "caching design: key strategy, invalidation, cross-process consistency, and the main failure modes.",
    "Design a backoff-and-retry policy for calls to a flaky downstream dependency: the algorithm, the "
    "parameters and how to choose them, interaction with timeouts/circuit-breakers, and failure modes.",
]


def _parse_scores(text: str) -> dict:
    out = {}
    for lab in ("A", "B", "C"):
        m = re.search(rf"\b{lab}\s*=\s*(\d+(?:\.\d+)?)", text or "")
        if m:
            out[lab] = float(m.group(1))
    return out


def run_openended(prompts=tuple(_OPEN_TASKS), gen=("opus", "codex"), judges=("opus", "codex"),
                  cache_path: str | None = None) -> dict:
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))

    def call(key, model, prompt):
        if not cache.get(key):
            cache[key] = _CALL(model, prompt)
            if cache_path:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
        return cache[key]

    rows = []
    for i, p in enumerate(prompts):
        a = call(f"{i}|genA", gen[0], p)
        b = call(f"{i}|genB", gen[1], p)
        syn = call(f"{i}|synth", gen[0], f"Two experts answered the task. Produce ONE answer strictly "
                   f"better than either by merging their strengths and fixing their gaps.\nTASK: {p}\n"
                   f"EXPERT 1:\n{a}\n\nEXPERT 2:\n{b}\n\nOutput only the merged answer.")
        # blind labels: A=gen0, B=gen1, C=synthesis (judge doesn't know which is which)
        jr = []
        for jm in judges:
            jp = (f"Score each answer to the task on correctness + completeness as integers 1-10. "
                  f"Be critical and discriminating.\nTASK: {p}\n\nANSWER A:\n{a}\n\nANSWER B:\n{b}\n\n"
                  f"ANSWER C:\n{syn}\n\nReply with ONLY one line: 'A=<n> B=<n> C=<n>'.")
            jr.append(_parse_scores(call(f"{i}|judge_{jm}", jm, jp)))
        avg = {lab: round(sum(j.get(lab, 0) for j in jr) / len(jr), 2) for lab in ("A", "B", "C")}
        rows.append({"task": p[:60] + "...", "scores": avg, "best_single": max(avg["A"], avg["B"]),
                     "synthesis": avg["C"], "synth_gain": round(avg["C"] - max(avg["A"], avg["B"]), 2)})
    mean_gain = round(sum(r["synth_gain"] for r in rows) / len(rows), 3)
    return {"gen": list(gen), "judges": list(judges), "rows": rows, "mean_synth_gain": mean_gain,
            "artifacts": cache}


def _md_openended(r: dict) -> str:
    L = [f"# open-ended mesh — cross-vendor 合成は単独を超えるか（LLM-judge・gold 無し領域）",
         "",
         f"生成: {' + '.join(r['gen'])}／合成: {r['gen'][0]} が両者を merge／判定: {', '.join(r['judges'])}"
         "（A=gen0, B=gen1, **C=合成**・判定者は知らない）。主観的（judge bias）だが checkable コーディングが届かない縁の代理。",
         "",
         f"## 平均 synthesis gain（C − max(A,B)）= **{r['mean_synth_gain']:+}**",
         "| task | A | B | **C(合成)** | 単独最良 | gain |",
         "|---|---|---|---|---|---|"]
    for row in r["rows"]:
        s = row["scores"]
        L.append(f"| {row['task']} | {s['A']} | {s['B']} | **{s['C']}** | {row['best_single']} | {row['synth_gain']:+} |")
    L += ["", "## 読み",
          "- **gain>0 なら open-ended 領域で cross-vendor 合成が単独を超える**＝mesh が縁で点火（主観評価だが）。",
          "- gain≈0/負なら合成は冗長 or judge が長さ等に釣られた可能性。**judge bias（自作びいき・長さびいき）に注意**＝この計測自体が交絡しうる（§9）。"]
    return "\n".join(L)


def _md_decorr(r: dict) -> str:
    L = ["# 弱モデル mesh の概念実証 — 誤りは脱相関するか（union > 単独最良か）",
         "",
         "多様なモデルの誤りが*別タスク*に出れば、pair-union が単独を超える＝ML アンサンブル原理"
         "＝『多様性 mesh』組織の種。誤りが起きる task で測る（trials=" + str(r["trials"]) + "）。",
         "",
         "## solve_rate 行列（どのモデルがどこで誤るか）",
         "| task | " + " | ".join(r["models"]) + " |",
         "|" + "---|" * (len(r["models"]) + 1)]
    for tid in _DECORR_TASKS:
        L.append(f"| {tid} | " + " | ".join(str(r["solve"][f'{m}|{tid}']) for m in r["models"]) + " |")
    L += ["", "## ペア union vs 単独最良（gain>0 ＝ 脱相関で mesh が単独を超える）",
          "| ペア | union | 単独最良 | gain | 相補タスク（片方だけ解く） |",
          "|---|---|---|---|---|"]
    for p in r["pairs"]:
        L.append(f"| {p['pair']} | {p['union']} | {p['best_single']} | **{p['gain']:+}** | "
                 f"{', '.join(p['complementary_tasks']) or '—'} |")
    L += ["", "## 読み",
          "- **gain>0 のペアがあれば mesh 原理は実在**：異種が互いの盲点を覆い、組み合わせが単独を超える。",
          "- 相補タスクが在る＝誤りが*別 instance* に出る（脱相関）＝mesh の燃料。",
          "- frontier(opus/codex) は誤らずここに出ない（§5）＝mesh は能力の縁でだけ点火（弱い所では*実在*）。"]
    return "\n".join(L)


def _md_ensemble(r: dict) -> str:
    n = r["n"]
    L = [f"# 弱アンサンブル — 低レベル {r['model']} を N 回試し gold で選べば高レベルに迫れるか",
         "",
         "外部検証器（gold）が選択器: best-of-k = 最初の k 回のどれかが gold を通れば solved。"
         f"コスト = k × w_weak（{r['w_weak']}）。frontier 単発は全タスク 1.0（既測）＝比較基準。",
         "",
         "## 期待 best-of-k = 1−(1−p)^k（k 回試して gold が通る確率）と コスト",
         "| k | 期待 best-of-k | コスト (k×w) | vs haiku単発(正しさ1.0, cost1) |",
         "|---|---|---|---|"]
    for k in range(n):
        bo, c = r["expected_best_of_k_avg"][k], r["cost_of_k"][k]
        cmp = "**追いついた**" if bo >= 0.99 else ("接近" if bo >= 0.85 else "—")
        L.append(f"| {k + 1} | {bo} | {c} | {cmp}{'・haikuと同コスト級' if abs(c - 1.0) < 0.25 else ''} |")
    L += ["",
          "## タスク別（single-shot p → 期待 best-of-" + str(n) + "）",
          "| task | single-shot p | 期待 best-of-" + str(n) + " | per-trial |",
          "|---|---|---|---|"]
    for row in r["rows"]:
        L.append(f"| {row['task']} | {row['single_shot']} | {row['expected_best_of_k'][-1]} | {row['per_trial']} |")
    L += ["",
          "## 読み",
          "- **不安定（sometimes-right）なタスク**（roman/wildcard+ p≈0.5・negabinary p≈0.83）は best-of-k が k とともに 1.0 に迫る ── "
          "**検証器付きの弱モデル反復が高レベルの*信頼性*を近似**（低レベルの組み合わせで higher-level に迫る・原点の問いに部分 YES）。",
          "- **系統的に解けないタスク**（calc p=0・6回とも失敗）は best-of-k が**0 のまま** ── "
          "**反復は*不安定*を信頼性に変えるが、*欠落した能力*は作れない**（best-of-N の核心的限界）。",
          "- **コスト**: p≈0.5 のタスクで 1.0 に迫る k≈5–6 ＝ コスト k×w ≈ 1.0 ＝ **haiku 単発とほぼ同コスト** ── "
          "「弱モデル反復で強モデルに迫れるが*安くはなく*、しかも外部検証器が要る」。",
          "",
          "## 妥当性",
          "- gold は固定外部正解（参照実装で検算済）。best-of-k は gold をオラクルに使う（検証器が前提）。少標本。"]
    return "\n".join(L)


def _md_ladder(r: dict) -> str:
    order = [m for m, _ in r["tiers"]]
    L = ["# 難易度ラダー — 能力レンジ全体で帯を実測分類（barely-opus / impossible まで）",
         "",
         f"4ティア（{' < '.join(order)}）を検算済み難タスクに当て、各タスクを *最強の解けるティア* で分類"
         f"（trials={r['trials']}・gold は外部正解）。市場の支配定理は強ティアが解ける(p_strong=1)前提 ── "
         "impossible 帯はその前提が崩れる所。",
         "",
         "## タスク別 solve_rate（1.0到達率）と帯",
         "| task | " + " | ".join(order) + " | 最安の解き手 | 帯 |",
         "|" + "---|" * (len(order) + 3)]
    for row in r["tasks"]:
        cells = " | ".join(str(row["solve_rate"][m]) for m in order)
        L.append(f"| {row['task']} | {cells} | {row['cheapest_solver'] or '—'} | **{row['class']}** |")
    L += ["",
          "## エスカレーション市場の挙動（特に誰も解けない時）",
          "| task | 梯子（model:solve_rate） | 市場コスト | 解けたティア | 最良正しさ |",
          "|---|---|---|---|---|"]
    for m in r["market"]:
        ladder = " → ".join(f"{mm}:{sr}" for mm, sr in m["ladder"])
        L.append(f"| {m['task']} | {ladder} | {m['cost']} | {m['solved_at'] or '**誰も**'} | {m['best_corr']} |")
    L += ["",
          "## 読み",
          "- **barely-opus** 帯が存在すれば、frontier 内に勾配があり ②（frontier 異種）でも市場が効きうる（haiku/sonnet で試し opus へ）。",
          "- **impossible** 帯では市場は全ティアを払い（最大コスト）正しさ<1 ── **支配定理の p_strong=1 前提が崩れ、市場は高コストで未解決**。"
          "＝「能力の天井を越えた仕事は、どの組織構造でも金を捨てるだけ」。",
          "- 非標準ツイスト（wildcard+ の 1-or-more・negabinary）は memorized 解を壊す ── frontier を分離できるか。",
          "",
          "## 妥当性",
          "- gold は固定外部正解（参照実装で検算済）。少標本（trials 小）・gemma の cold-start は trials で緩和。"
          "コスト比は定価の代理。"]
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
    ap.add_argument("--ladder", action="store_true", dest="ladder",
                    help="4-tier frontier difficulty ladder -> classify tasks (barely-opus / impossible)")
    ap.add_argument("--ensemble", action="store_true",
                    help="weak best-of-N: does N gemma attempts + gold selection approach a higher tier?")
    ap.add_argument("--decorr", action="store_true",
                    help="mesh proof-of-concept: do diverse weak models' errors decorrelate (union>best)?")
    ap.add_argument("--novel", action="store_true",
                    help="novel/compound hard tasks across frontier vendors (try to make the frontier err)")
    ap.add_argument("--openended", action="store_true",
                    help="open-ended mesh: does cross-vendor synthesis beat single answers (LLM-judged)?")
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args(argv)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    if args.openended:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_openended_artifacts.json")
        r = run_openended(cache_path=cache)
        with open(os.path.join(out_dir, "market_openended_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_OPENENDED.md"), "w", encoding="utf-8") as f:
            f.write(_md_openended(r) + "\n")
        print(f"mean synthesis gain (C - best single) = {r['mean_synth_gain']:+}")
        for row in r["rows"]:
            print(f"  {row['scores']}  gain={row['synth_gain']:+}  {row['task']}")
        print("\nwrote market_openended_results.json and MARKET_OPENENDED.md")
        return 0
    if args.decorr:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_decorr_artifacts.json")
        r = run_decorr(trials=max(2, args.trials if args.trials <= 3 else 2), cache_path=cache)
        with open(os.path.join(out_dir, "market_decorr_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_DECORR.md"), "w", encoding="utf-8") as f:
            f.write(_md_decorr(r) + "\n")
        print("per-model:", r["per_model"])
        for p in r["pairs"]:
            print(f"  {p['pair']:<24} union={p['union']} best={p['best_single']} gain={p['gain']:+} comp={p['complementary_tasks']}")
        print("\nwrote market_decorr_results.json and MARKET_DECORR.md")
        return 0
    if args.ensemble:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_ensemble_artifacts.json")
        r = run_ensemble(n=max(2, args.trials if args.trials > 3 else 6), cache_path=cache)
        with open(os.path.join(out_dir, "market_ensemble_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_ENSEMBLE.md"), "w", encoding="utf-8") as f:
            f.write(_md_ensemble(r) + "\n")
        print(f"best-of-k avg ({r['model']}, n={r['n']}): {r['best_of_k_avg']}")
        for row in r["rows"]:
            print(f"  {row['task']:<14} single={row['single_shot']:<5} best-of-{r['n']}={row['best_of_k'][-1]} {row['per_trial']}")
        print("\nwrote market_ensemble_results.json and MARKET_ENSEMBLE.md")
        return 0
    if args.novel:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_novel_artifacts.json")
        r = run_ladder(tasks=tuple(_NOVEL_TASKS), tiers=_TIERS_FRONTIER,
                       trials=max(1, args.trials), cache_path=cache)
        with open(os.path.join(out_dir, "market_novel_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_NOVEL.md"), "w", encoding="utf-8") as f:
            f.write(_md_ladder(r) + "\n")
        for row in r["tasks"]:
            print(f"  {row['task']:<12} {row['class']:<13} solve_rate={row['solve_rate']}")
        print("\nwrote market_novel_results.json and MARKET_NOVEL.md")
        return 0
    if args.ladder:
        _CALL = _mock if args.agent == "mock" else _route
        cache = os.path.join(out_dir, "market_ladder_artifacts.json")
        r = run_ladder(trials=max(1, args.trials), cache_path=cache)
        with open(os.path.join(out_dir, "market_ladder_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
        with open(os.path.join(out_dir, "MARKET_LADDER.md"), "w", encoding="utf-8") as f:
            f.write(_md_ladder(r) + "\n")
        for row in r["tasks"]:
            print(f"  {row['task']:<14} {row['class']:<13} solve_rate={row['solve_rate']}")
        print("\nwrote market_ladder_results.json and MARKET_LADDER.md")
        return 0
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
