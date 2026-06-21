"""実証: エージェント組織シミュレータ — 構造（flat vs hierarchy）を実エージェントで測る。

これまで実証は F8（監督）と race だけ。F3（通信コスト→構造）は解析のままだった。ここでは
実 LLM エージェントに**相互依存タスク**（設計→実装→テスト）を、2つの組織構造で実際に
*組織*させ、**コスト（モデルコール数）と品質（静的検査）**を測る:

- flat:      共有黒板。各 worker が直前までの全成果を見て次の subtask をやる。管理者なし（3 コール）。
- hierarchy: 管理者が分解・割当（1）→ workers（3・割当のみ見る）→ 管理者が統合・修正（1）。＝5 コール。

予測（coordination.py / tehai A/B）: hierarchy は管理者OHで**コスト高**、品質は同等か ── flat が安い。
品質は静的検査（必要関数を impl が def し test が参照するか）＝実行不要で安全。free 枠（claude-cli-run.py）。

run: python3 -m experiments.org_sim --agent claude:sonnet --tasks 2
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

from experiments.oversight.overseer import _CLAUDE_MODEL_ALIAS, _CLAUDE_RUNNER  # noqa: E402


# Each task: interdependent (design -> impl -> test) with a checkable spec.
TASKS = [
    {"id": "textutil", "names": ["slugify", "truncate_middle", "word_count"],
     "spec": "slugify(s)->lowercase-hyphen slug; truncate_middle(s,n)->keep ends with '…' if len>n; word_count(s)->int words."},
    {"id": "numutil", "names": ["clamp", "is_prime", "running_mean"],
     "spec": "clamp(x,lo,hi)->bounded; is_prime(n)->bool (1 and below are not prime); running_mean(xs)->list of cumulative means."},
    {"id": "timeutil", "names": ["parse_hms", "humanize_secs", "is_leap"],
     "spec": "parse_hms('H:M:S')->seconds; humanize_secs(n)->'Xh Ym Zs'; is_leap(year)->bool."},
]


# --------------------------------------------------------------------------- #
# agent caller (free quota) + deterministic mock
# --------------------------------------------------------------------------- #
def _agent(model: str, prompt: str, timeout: int = 360) -> str:
    m = _CLAUDE_MODEL_ALIAS.get(model, model)
    cmd = (["python3", _CLAUDE_RUNNER, "--model", m, "--no-sentinel"]
           if _CLAUDE_RUNNER and os.path.exists(_CLAUDE_RUNNER)
           else ["claude", "--print", "--model", m])
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"agent failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _mock(model: str, prompt: str, timeout: int = 0) -> str:
    # deterministic stand-in: emits defs/tests for whatever names are in the prompt
    names = re.findall(r"\b([a-z_][a-z0-9_]+)\(", prompt)
    uniq = [n for n in dict.fromkeys(names) if n not in ("def", "len", "range", "print")][:3]
    body = "\n".join(f"def {n}(*a):\n    return None" for n in uniq)
    tests = "\n".join(f"def test_{n}():\n    {n}()" for n in uniq)
    return body + "\n" + tests


_CALL = _agent  # swapped to _mock by --agent mock


# --------------------------------------------------------------------------- #
# structures (return (final_artifact_text, n_calls))
# --------------------------------------------------------------------------- #
def run_flat(model: str, task: dict) -> tuple[str, int]:
    spec, names = task["spec"], ", ".join(task["names"])
    design = _CALL(model, f"Design Python signatures (def lines + 1-line docstrings) for: {spec}\n"
                          f"Required functions: {names}. Output ONLY the signatures.")
    impl = _CALL(model, f"Implement these Python functions FULLY. Spec: {spec}\nSignatures:\n{design}\n"
                        f"Output ONLY runnable code.")
    tests = _CALL(model, f"Write one unittest-style test function per function. Implementation:\n{impl}\n"
                         f"Output ONLY test code that calls each function.")
    return impl + "\n\n" + tests, 3


def run_hierarchy(model: str, task: dict) -> tuple[str, int]:
    spec, names = task["spec"], ", ".join(task["names"])
    plan = _CALL(model, f"You are an engineering MANAGER. Break this module into subtasks (design, "
                        f"implement, test) and write a brief assignment plan. Module: {spec}\n"
                        f"Required functions: {names}. Output a short plan only.")
    design = _CALL(model, f"You are the DESIGN worker. Your manager's plan:\n{plan}\nDesign Python "
                          f"signatures for the module. Output ONLY signatures.")
    impl = _CALL(model, f"You are the IMPLEMENT worker. Manager's plan:\n{plan}\nSignatures:\n{design}\n"
                        f"Implement the functions fully. Output ONLY runnable code.")
    tests = _CALL(model, f"You are the TEST worker. Manager's plan:\n{plan}\nImplementation:\n{impl}\n"
                         f"Write one test per function. Output ONLY test code.")
    final = _CALL(model, f"You are the MANAGER. Integrate and FIX your team's outputs into one consistent "
                         f"module (code + tests), correcting any mismatch. Implementation:\n{impl}\n"
                         f"Tests:\n{tests}\nOutput ONLY the final integrated code + tests.")
    return final, 5


def run_market(model: str, task: dict) -> tuple[str, int]:
    spec, names = task["spec"], ", ".join(task["names"])
    auction = _CALL(model, f"You run a MARKET of independent agents bidding for subtasks (design, implement, "
                           f"test) of this module: {spec} (functions: {names}). Allocate by bid and note any "
                           f"specialization. Output a short allocation.")
    design = _CALL(model, f"You WON the design bid. Allocation:\n{auction}\nDesign Python signatures. "
                          f"Output ONLY signatures.")
    impl = _CALL(model, f"You WON the implement bid. Signatures (purchased):\n{design}\nImplement the "
                        f"functions fully. Output ONLY runnable code.")
    tests = _CALL(model, f"You WON the test bid. Implementation (purchased):\n{impl}\nWrite one test per "
                         f"function. Output ONLY test code.")
    return impl + "\n\n" + tests, 4


STRUCTURES = {"flat": run_flat, "hierarchy": run_hierarchy, "market": run_market}


# --------------------------------------------------------------------------- #
# static quality check (no execution): coverage + consistency
# --------------------------------------------------------------------------- #
def quality(task: dict, artifact: str) -> dict:
    a = artifact or ""
    defined = [n for n in task["names"] if re.search(rf"\bdef\s+{re.escape(n)}\s*\(", a)]
    tested = [n for n in task["names"] if re.search(rf"\b{re.escape(n)}\s*\(", a)
              and (f"test" in a.lower())]
    impl_cov = len(defined) / len(task["names"])
    test_cov = len([n for n in task["names"]
                    if re.search(rf"\bdef\s+test\w*\b", a) and re.search(rf"\b{re.escape(n)}\s*\(", a)]) \
        / len(task["names"])
    score = round((impl_cov + test_cov) / 2, 3)
    return {"impl_coverage": round(impl_cov, 3), "test_coverage": round(test_cov, 3),
            "quality": score, "defined": defined}


# --------------------------------------------------------------------------- #
# correctness: actually RUN the generated tests in an isolated sandbox (no net/pid)
# --------------------------------------------------------------------------- #
import shutil  # noqa: E402

_UNSHARE = shutil.which("unshare") is not None
_HARNESS = (
    '\n\nif True:\n'
    '    import sys as _sys, unittest as _ut\n'
    '    _g = dict(globals())\n'
    '    _fns = [v for k, v in _g.items() if k.startswith("test") and callable(v) and not isinstance(v, type)]\n'
    '    _p = _n = 0\n'
    '    for _f in _fns:\n'
    '        _n += 1\n'
    '        try:\n'
    '            _f(); _p += 1\n'
    '        except Exception:\n'
    '            pass\n'
    '    try:\n'
    '        _r = _ut.TestResult(); _ut.TestLoader().loadTestsFromModule(_sys.modules["__main__"]).run(_r)\n'
    '        _n += _r.testsRun; _p += _r.testsRun - len(_r.failures) - len(_r.errors)\n'
    '    except Exception:\n'
    '        pass\n'
    '    print("CORRECT", _p, _n)\n'
)


# Minimal in-process pytest shim so model-emitted pytest tests (import pytest,
# @pytest.mark.parametrize, pytest.raises/approx) RUN in the no-net sandbox where
# real pytest may be absent. Without this, correctness measures "did the model use
# my test format", not correctness — a confound. A parametrized test = 1 unit that
# runs every case (raises on first failing case).
_PYTEST_SHIM = (
    'import sys as _s, types as _t\n'
    '_pt = _t.ModuleType("pytest")\n'
    'class _Mark:\n'
    '    def parametrize(self, argnames, argvalues, *a, **k):\n'
    '        names = [x.strip() for x in argnames.split(",")] if isinstance(argnames, str) else list(argnames)\n'
    '        def deco(fn):\n'
    '            def wrapped(*args, **kw):\n'
    '                if args or kw: return fn(*args, **kw)\n'
    '                for case in argvalues:\n'
    '                    vals = list(case) if (isinstance(case, (tuple, list)) and len(names) > 1) else [case]\n'
    '                    fn(*vals)\n'
    '            wrapped.__name__ = getattr(fn, "__name__", "test")\n'
    '            return wrapped\n'
    '        return deco\n'
    '    def __getattr__(self, name):\n'
    '        def deco(*a, **k):\n'
    '            if len(a) == 1 and callable(a[0]) and not k: return a[0]\n'
    '            return lambda fn: fn\n'
    '        return deco\n'
    '_pt.mark = _Mark()\n'
    'class _Raises:\n'
    '    def __init__(self, exc): self.exc = exc\n'
    '    def __enter__(self): return self\n'
    '    def __exit__(self, et, ev, tb):\n'
    '        if et is None: raise AssertionError("did not raise")\n'
    '        return issubclass(et, self.exc if isinstance(self.exc, tuple) else (self.exc,))\n'
    '_pt.raises = lambda exc, *a, **k: _Raises(exc)\n'
    'class _Approx:\n'
    '    def __init__(self, x, rel=1e-6, abs=1e-9): self.x, self.rel, self.abs = x, rel, abs\n'
    '    def __eq__(self, o):\n'
    '        try: return abs(o - self.x) <= max(self.rel * max(abs(o), abs(self.x)), self.abs)\n'
    '        except Exception: return False\n'
    '_pt.approx = lambda x, rel=1e-6, abs=1e-9: _Approx(x, rel, abs)\n'
    '_pt.fixture = lambda *a, **k: (a[0] if (len(a) == 1 and callable(a[0])) else (lambda fn: fn))\n'
    'def _skip(*a, **k): raise _Skip()\n'
    'class _Skip(Exception): pass\n'
    '_pt.skip = _skip\n'
    '_s.modules["pytest"] = _pt\n\n'
)


def _extract_code(text: str) -> str:
    t = text or ""
    blocks = re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", t, re.DOTALL)
    code = "\n".join(blocks) if blocks else t
    return "\n".join(ln for ln in code.splitlines() if "unittest.main(" not in ln)


def correctness(artifact: str, timeout: int = 12) -> dict:
    import resource
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(_PYTEST_SHIM + _extract_code(artifact) + _HARNESS)
        path = f.name

    def _limits():  # CPU + memory caps in the child (belt-and-suspenders with the wall timeout)
        resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)

    base = ["python3", path]
    cmd = (["unshare", "--user", "--net", "--pid", "--fork", "--mount-proc"] + base) if _UNSHARE else base
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 4, preexec_fn=_limits)
        m = re.search(r"CORRECT (\d+) (\d+)", proc.stdout)
        if m:
            p, n = int(m.group(1)), int(m.group(2))
            return {"passed": p, "total": n, "correctness": round(p / n, 3) if n else None, "ran": True}
        return {"passed": 0, "total": 0, "correctness": None, "ran": False,
                "err": ((proc.stderr or proc.stdout) or "")[:160]}
    except Exception as e:
        return {"passed": 0, "total": 0, "correctness": None, "ran": False, "err": str(e)[:160]}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def run(model: str, tasks: list[dict], structures=tuple(STRUCTURES),
        measure_correctness: bool = True) -> dict:
    rows = []
    for t in tasks:
        for s in structures:
            artifact, calls = STRUCTURES[s](model, t)
            q = quality(t, artifact)
            row = {"task": t["id"], "structure": s, "calls": calls,
                   "quality": q["quality"], "impl_cov": q["impl_coverage"],
                   "test_cov": q["test_coverage"], "chars": len(artifact)}
            if measure_correctness:
                c = correctness(artifact)
                row.update(correctness=c["correctness"],
                           tests_passed=f"{c['passed']}/{c['total']}", ran=c["ran"])
            rows.append(row)
    agg = {}
    for s in structures:
        sr = [r for r in rows if r["structure"] == s]
        a = {"avg_calls": round(sum(r["calls"] for r in sr) / len(sr), 2),
             "avg_quality": round(sum(r["quality"] for r in sr) / len(sr), 3),
             "total_calls": sum(r["calls"] for r in sr)}
        if measure_correctness:
            cs = [r["correctness"] for r in sr if r.get("correctness") is not None]
            a["avg_correctness"] = round(sum(cs) / len(cs), 3) if cs else None
        agg[s] = a
    return {"model": model, "n_tasks": len(tasks), "rows": rows, "aggregate": agg}


def _md(r: dict) -> str:
    a = r["aggregate"]
    L = ["# 実証: エージェント組織シミュレータ — flat vs hierarchy（F3 接地）",
         "",
         f"実 LLM エージェント（{r['model']}）に相互依存タスク（設計→実装→テスト）を 2 構造で組織させ、"
         f"コスト（コール数）と品質（静的検査）を測った。タスク {r['n_tasks']} 件。"
         "生数値 [`org_sim_results.json`](org_sim_results.json)。",
         "",
         "## 集計",
         "| 構造 | 平均コール（コスト） | 平均品質(静的) | 平均正しさ(実行) | 総コール |",
         "|---|---|---|---|---|"]
    for s in ("flat", "hierarchy", "market"):
        if s in a:
            L.append(f"| {s} | {a[s]['avg_calls']} | {a[s]['avg_quality']} | "
                     f"{a[s].get('avg_correctness')} | {a[s]['total_calls']} |")
    L += ["",
          "## 読み",
          "- hierarchy/market のコール数 ＞ flat（調整OH）。**品質・正しさが同等以下なら → flat が安い**（解析 F3・tehai A/B を実エージェントで支持）。",
          "- market は均質な組織では bidding OH のみで heterogeneity の便益が無い → flat に劣るはず（解析の予測）。",
          "- 正しさ（実行＝tests が通る割合）は静的 coverage より厳しい本物の品質。",
          "",
          "## タスク別",
          "| task | 構造 | calls | quality(静的) | 正しさ(実行) | tests |",
          "|---|---|---|---|---|---|"]
    for row in r["rows"]:
        L.append(f"| {row['task']} | {row['structure']} | {row['calls']} | {row['quality']} | "
                 f"{row.get('correctness')} | {row.get('tests_passed', '-')} |")
    L += ["",
          "## 妥当性",
          "- 品質は静的 coverage ＋ **正しさは sandbox 実行**（unshare で no-net/no-pid 隔離・generated code を実行）。"
          "構造の実装は最小（flat=共有黒板逐次・hierarchy=管理者2コール・market=bidding 1コール）。コストはコール数の代理。少標本。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="agent organization simulator (flat vs hierarchy)")
    ap.add_argument("--agent", default="mock", help="'mock' or claude:<model>")
    ap.add_argument("--tasks", type=int, default=3)
    args = ap.parse_args(argv)
    if args.agent == "mock":
        _CALL = _mock
        model = "mock"
    else:
        vendor, _, model = args.agent.partition(":")
        if vendor != "claude":
            raise SystemExit("use --agent mock or claude:<model>")
    r = run(model, TASKS[:max(1, args.tasks)])
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "org_sim_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "ORG_SIM.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print("aggregate:", r["aggregate"])
    for row in r["rows"]:
        print(f"  {row['task']:<10} {row['structure']:<10} calls={row['calls']} quality={row['quality']}")
    print(f"\nwrote org_sim_results.json and ORG_SIM.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
