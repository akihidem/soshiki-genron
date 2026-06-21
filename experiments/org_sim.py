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


STRUCTURES = {"flat": run_flat, "hierarchy": run_hierarchy}


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


def run(model: str, tasks: list[dict], structures=tuple(STRUCTURES)) -> dict:
    rows = []
    for t in tasks:
        for s in structures:
            artifact, calls = STRUCTURES[s](model, t)
            q = quality(t, artifact)
            rows.append({"task": t["id"], "structure": s, "calls": calls,
                         "quality": q["quality"], "impl_cov": q["impl_coverage"],
                         "test_cov": q["test_coverage"], "chars": len(artifact)})
    agg = {}
    for s in structures:
        sr = [r for r in rows if r["structure"] == s]
        agg[s] = {"avg_calls": round(sum(r["calls"] for r in sr) / len(sr), 2),
                  "avg_quality": round(sum(r["quality"] for r in sr) / len(sr), 3),
                  "total_calls": sum(r["calls"] for r in sr)}
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
         "| 構造 | 平均コール（コスト） | 平均品質 | 総コール |",
         "|---|---|---|---|"]
    for s in ("flat", "hierarchy"):
        if s in a:
            L.append(f"| {s} | {a[s]['avg_calls']} | {a[s]['avg_quality']} | {a[s]['total_calls']} |")
    L += ["",
          "## 読み",
          "- hierarchy のコール数 ＞ flat（管理者OH）。**品質が同等以下なら → flat が安い（解析 F3・tehai A/B を実エージェントで支持）**。",
          "- hierarchy の品質が*明確に高い*なら、管理者の統合がOHを正当化（構造の価値）。",
          "",
          "## タスク別",
          "| task | 構造 | calls | quality | impl_cov | test_cov |",
          "|---|---|---|---|---|---|"]
    for row in r["rows"]:
        L.append(f"| {row['task']} | {row['structure']} | {row['calls']} | {row['quality']} | "
                 f"{row['impl_cov']} | {row['test_cov']} |")
    L += ["",
          "## 妥当性",
          "- 少標本・品質は静的検査（実行せず＝coverage/consistency の代理・正しさ自体は未検証）。"
          "構造の実装は最小（flat=共有黒板の逐次・hierarchy=管理者2コール）。コストはコール数の代理。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="agent organization simulator (flat vs hierarchy)")
    ap.add_argument("--agent", default="mock", help="'mock' or claude:<model>")
    ap.add_argument("--tasks", type=int, default=2)
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
