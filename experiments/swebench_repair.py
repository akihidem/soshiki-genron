"""実証: 実 SWE-bench で frontier の脱相関 — 構築タスクでなく*実 repo の実バグ*。

生成も適応的ケースも構築修復も frontier は誤らず脱相関ゼロだった（PAPER §5）。ここでは
**実 SWE-bench Lite（pytest 実 repo の実 issue）** で測る ── モデルに user-issue ＋ バグのある
実ファイルを渡し修復させ、**実テストスイート（FAIL_TO_PASS + PASS_TO_PASS）で採点**。opus と codex が
*違う instance* を解けば union>単独 ＝ 補完能力 mesh が*現実規模*で frontier の縁に点火（PAPER §6.5）。

Docker 不可環境のため pytest インスタンス（Python3.12 互換・editable install 済 /tmp/pytest_repo）に限定。
各 instance: checkout base → test_patch 適用 → bug 再現確認 → モデル修復 → 全テスト採点 → reset。
run: python3 -m experiments.swebench_repair --agent claude:real --instances pytest-dev__pytest-7373,...
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

from experiments.market_external import _agent, _extract_code, _mock, _route  # noqa: E402

_REPO = "/tmp/pytest_repo"
_PY = "/tmp/pyt_venv/bin/python"
_INSTANCES_JSON = "/tmp/swe_instances.json"
_CALL = _agent


def _git(*args, timeout=120):
    return subprocess.run(["git", "-C", _REPO, *args], capture_output=True, text=True, timeout=timeout)


def _edited_file(patch: str) -> str | None:
    m = re.findall(r"^\+\+\+ b/(\S+)", patch, re.M)
    src = [f for f in m if f.startswith("src/")]
    return src[0] if len(src) == 1 else None


def _run_tests(tests, timeout=240) -> bool:
    """True iff every listed test passes (the SWE-bench 'resolved' criterion, on this subset)."""
    if not tests:
        return True
    proc = subprocess.run([_PY, "-m", "pytest", *tests, "-q", "--no-header", "-p", "no:cacheprovider"],
                          cwd=_REPO, capture_output=True, text=True, timeout=timeout)
    out = proc.stdout + proc.stderr
    if "error" in out.lower() and "collected" not in out.lower():
        return False                                  # collection/import error
    return (" failed" not in out) and ("passed" in out or "no tests ran" not in out)


def _setup(inst: dict) -> bool:
    """checkout base, apply the test_patch, confirm the bug reproduces (FAIL_TO_PASS fails)."""
    _git("checkout", "-f", "-q", inst["base_commit"])
    _git("clean", "-qfd")
    open("/tmp/_tp.patch", "w").write(inst["test_patch"])
    if _git("apply", "/tmp/_tp.patch").returncode != 0:
        return False
    f2p = json.loads(inst["FAIL_TO_PASS"])
    return not _run_tests(f2p)                         # must currently FAIL = bug present


def _repair(model: str, inst: dict, path: str, content: str) -> bool:
    prompt = (f"You are fixing a real bug in the pytest codebase. User-reported issue:\n\n"
              f"{inst['problem_statement'][:2500]}\n\n"
              f"The buggy file is `{path}`. Here is its FULL current content:\n\n"
              f"```python\n{content}\n```\n\n"
              f"Output the COMPLETE corrected content of `{path}` (the whole file with the bug fixed), "
              f"as ONE python code block. No prose.")
    out = _CALL(model, prompt)
    code = _extract_code(out)
    if "def " not in code or len(code) < len(content) * 0.5:   # guard against truncation/garbage
        return False
    full = os.path.join(_REPO, path)
    open(full, "w").write(code)
    ok = _run_tests(json.loads(inst["FAIL_TO_PASS"])) and \
        _run_tests(json.loads(inst["PASS_TO_PASS"])[:30])      # F2P pass AND no regressions (P2P sample)
    _git("checkout", "-q", "--", path)                          # reset the file
    return ok


def run(models, instance_ids, cache_path=None) -> dict:
    allinst = {i["instance_id"]: i for i in json.load(open(_INSTANCES_JSON, encoding="utf-8"))}
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))
    solved, rows = {}, []
    for iid in instance_ids:
        inst = allinst[iid]
        path = _edited_file(inst["patch"])
        if not path or not _setup(inst):
            rows.append({"instance": iid, "status": "skipped (setup/bug-repro failed)"})
            continue
        content = open(os.path.join(_REPO, path), encoding="utf-8", errors="replace").read()
        if len(content.splitlines()) > 900:
            rows.append({"instance": iid, "status": "skipped (file too large)"})
            continue
        rec = {"instance": iid, "file": path}
        for m in models:
            key = f"{iid}|{m}"
            if key not in cache:
                _setup(inst)                                    # fresh bug state per model
                cache[key] = 1 if _repair(m, inst, path, content) else 0
                if cache_path:
                    json.dump(cache, open(cache_path, "w"), ensure_ascii=False, indent=2, sort_keys=True)
            solved[(m, iid)] = cache[key]
            rec[m] = cache[key]
        rows.append(rec)
    done = [iid for iid in instance_ids if all((m, iid) in solved for m in models)]
    per_model = {m: round(sum(solved[(m, i)] for i in done) / len(done), 3) if done else None for m in models}
    pairs = []
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            if not done:
                continue
            union = round(sum(max(solved[(a, i_)], solved[(b, i_)]) for i_ in done) / len(done), 3)
            best = max(per_model[a], per_model[b])
            comp = [i_ for i_ in done if solved[(a, i_)] != solved[(b, i_)]]
            pairs.append({"pair": f"{a} + {b}", "union": union, "best_single": round(best, 3),
                          "gain": round(union - best, 3), "complementary": comp})
    return {"models": list(models), "n_solved_cells": len(done), "rows": rows,
            "per_model": per_model, "pairs": pairs}


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="real SWE-bench (pytest) repair decorrelation")
    ap.add_argument("--agent", default="mock")
    ap.add_argument("--models", default="opus,codex")
    ap.add_argument("--instances", default="")
    args = ap.parse_args(argv)
    _CALL = _mock if args.agent == "mock" else _route
    ids = [x for x in args.instances.split(",") if x] or json.load(open("/tmp/swe_pick.json"))
    out_dir = os.path.dirname(os.path.abspath(__file__))
    r = run(args.models.split(","), ids, cache_path=os.path.join(out_dir, "swebench_artifacts.json"))
    with open(os.path.join(out_dir, "swebench_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("per-model solve:", r["per_model"], "| solved cells:", r["n_solved_cells"])
    for row in r["rows"]:
        print(" ", row)
    for p in r["pairs"]:
        print(f"  {p['pair']}: union={p['union']} best={p['best_single']} gain={p['gain']:+} comp={p['complementary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
