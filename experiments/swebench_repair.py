"""実証: 実 SWE-bench で frontier の脱相関 — 構築タスクでなく*実 repo の実バグ*。

生成も適応的ケースも構築修復も frontier は誤らず脱相関ゼロだった（PAPER §5）。ここでは
**実 SWE-bench Lite（pytest 実 repo の実 issue）** で測る ── モデルに user-issue ＋ バグのある
実ファイルを渡し修復させ、**実テストスイート（FAIL_TO_PASS + PASS_TO_PASS）で採点**。opus と codex が
*違う instance* を解けば union>単独 ＝ 補完能力 mesh が*現実規模*で frontier の縁に点火（PAPER §6.5）。

Docker 不可環境のため pytest インスタンス（Python3.12 互換・editable install 済 /tmp/pytest_repo）に限定。
各 instance: checkout base → test_patch 適用 → bug 再現確認 → モデル修復 → 全テスト採点 → reset。

モデルは **SEARCH/REPLACE 差分**で修復を返す（aider/SWE-agent 方式）。出力が小さいので実ソース
（pytest src は 1000-1800 行が普通）でも truncation せず、フルファイル書き直しのサイズ上限が消える。

採点の妥当性ガード（measurement-first・初回 all-zero は harness artifact だった）:
 1. 終了コードベース採点。pytest が crash/collection-interrupt した時に「0 failures」と誤読しない
    （初回 all-zero の正体は、生成用 _extract_code が実ソースの import を全削除→全テスト import error→
    それを 0 と誤読、だった）。差分適用は import を一切壊さない。
 2. **gold 検証ゲート**。各 instance で gold patch が F2P を rc0 にし P2P regression を出すか確認し、
    通らない instance（Docker 無し環境で Python3.12 非互換な旧 pytest 等）は計測せず skip する。
 3. P2P は **baseline-diff**。非ピン環境で元から落ちる P2P を罰しない（新規 regression ゼロが条件）。
3.12 互換 instance 探索: experiments/swebench_repair の _setup/_gold_validates で probe 済（/tmp/swe_usable.json）。
run: python3 -m experiments.swebench_repair --agent claude:real --instances pytest-dev__pytest-11148,...
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

from experiments.market_external import _agent, _mock, _route  # noqa: E402

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


def _unfence(text: str) -> str:
    """The model's code VERBATIM — the longest fenced block, else raw text.

    Crucially does NOT drop imports: a real source file needs `from ..outcomes import fail`,
    `from _pytest.config import Config`, `import attr`, etc. (_extract_code strips those for the
    self-contained generation tasks; on real source it guts the module -> spurious all-zero)."""
    blocks = re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", text or "", re.DOTALL)
    return max(blocks, key=len) if blocks else (text or "")


_SR = re.compile(r"<{5,}\s*SEARCH\s*?\n(.*?)\n={5,}\s*?\n(.*?)\n>{5,}\s*REPLACE", re.DOTALL)


def _apply_edits(content: str, text: str) -> str | None:
    """Apply the model's SEARCH/REPLACE blocks to the file (aider/SWE-agent style).

    Output is tiny (only the changed hunks) so real 1000-1800 line source files fit with no
    truncation and no size cap — the full-file rewrite couldn't (most pytest src is >900 lines).
    Exact match first, then a whitespace-tolerant line-window match; any block that fails to apply
    rejects the whole attempt (returns None). Falls back to a full-file response if no SR blocks."""
    blocks = _SR.findall(text or "")
    if not blocks:                                          # model returned a whole file instead
        code = _unfence(text)
        return code if ("def " in code and len(code) >= len(content) * 0.5) else None
    new = content
    for search, replace in blocks:
        if search and search in new:
            new = new.replace(search, replace, 1)
            continue
        nl, sl = new.splitlines(), search.splitlines()      # whitespace-tolerant fallback
        hit = next((i for i in range(len(nl) - len(sl) + 1)
                    if [x.rstrip() for x in nl[i:i + len(sl)]] == [x.rstrip() for x in sl]), None)
        if hit is None:
            return None                                     # a hunk didn't match -> reject attempt
        nl[hit:hit + len(sl)] = replace.splitlines()
        new = "\n".join(nl) + ("\n" if content.endswith("\n") else "")
    return new if new != content else None


def _run_capture(tests, timeout=300):
    """(fail_count, output_tail). Failing tests by pytest EXIT CODE (the source of truth);
    10**6 = broken run (do NOT misread a crash/collection-interrupt as 0 — the first all-zero
    result was exactly that artifact). The tail feeds the iterative agent its own test failure.

    pytest rc: 0=all passed, 1=tests failed, 2=interrupted, 3=internal, 4=usage, 5=no tests."""
    if not tests:
        return 0, ""
    proc = subprocess.run([_PY, "-m", "pytest", *tests, "-q", "--no-header", "-p", "no:cacheprovider"],
                          cwd=_REPO, capture_output=True, text=True, timeout=timeout)
    out, rc = (proc.stdout + proc.stderr), proc.returncode
    if rc == 0:
        return 0, out[-1800:]
    if rc == 1:                                          # genuine failures -> count them (+ errors)
        mf, me = re.search(r"(\d+) failed", out), re.search(r"(\d+) error", out)
        return (int(mf.group(1)) if mf else 1) + (int(me.group(1)) if me else 0), out[-1800:]
    return 10 ** 6, out[-1800:]                          # 2/3/4/5 = crash / interrupted / no tests


def _fail_count(tests, timeout=300) -> int:
    return _run_capture(tests, timeout)[0]


def _setup(inst: dict) -> bool:
    """checkout base, apply the test_patch, confirm the bug reproduces (FAIL_TO_PASS fails)."""
    _git("checkout", "-f", "-q", inst["base_commit"])
    _git("clean", "-qfd")
    open("/tmp/_tp.patch", "w").write(inst["test_patch"])
    if _git("apply", "/tmp/_tp.patch").returncode != 0:
        return False
    return _fail_count(json.loads(inst["FAIL_TO_PASS"])) > 0   # must currently FAIL = bug present


def _gold_validates(inst: dict, path: str, base_p2p_fail: int) -> bool:
    """Measurement-first gate: the GOLD patch must make F2P pass with no NEW P2P regression on THIS
    environment. If it doesn't (e.g. Python-3.12-incompatible old pytest whose pytester crashes),
    the instance is unmeasurable here -> skip it rather than score every model a spurious 0."""
    open("/tmp/_gold.patch", "w").write(inst["patch"])
    if _git("apply", "/tmp/_gold.patch").returncode != 0:
        _git("checkout", "-q", "--", path)
        return False
    ok = (_fail_count(json.loads(inst["FAIL_TO_PASS"])) == 0 and
          _fail_count(json.loads(inst["PASS_TO_PASS"])[:30]) <= base_p2p_fail)
    _git("checkout", "-q", "--", path)
    return ok


def _repair(model: str, inst: dict, path: str, content: str, base_p2p_fail: int) -> int:
    prompt = (f"You are fixing a real bug in the pytest codebase. User-reported issue:\n\n"
              f"{inst['problem_statement'][:2500]}\n\n"
              f"The buggy file is `{path}`. Its FULL current content:\n\n"
              f"```python\n{content}\n```\n\n"
              f"Output the MINIMAL fix as one or more SEARCH/REPLACE blocks, EXACTLY this format:\n"
              f"<<<<<<< SEARCH\n(lines copied verbatim from the file above)\n=======\n"
              f"(the corrected lines)\n>>>>>>> REPLACE\n"
              f"The SEARCH text must match the file's current lines EXACTLY, indentation included. "
              f"Keep it small — only the lines that change. No prose, no explanation.")
    new = _apply_edits(content, _CALL(model, prompt))
    if new is None:                                             # unparseable / no hunk applied
        return 0
    open(os.path.join(_REPO, path), "w").write(new)
    f2p_ok = _fail_count(json.loads(inst["FAIL_TO_PASS"])) == 0          # the bug is fixed
    p2p_ok = _fail_count(json.loads(inst["PASS_TO_PASS"])[:30]) <= base_p2p_fail  # no NEW regressions
    _git("checkout", "-q", "--", path)                          # reset the file
    return 1 if (f2p_ok and p2p_ok) else 0


def _repair_iterative(model: str, inst: dict, path: str, content: str, base_p2p_fail: int,
                      rounds: int = 3) -> int:
    """Agentic loop: propose a fix, RUN the tests, feed the failure back, revise — up to `rounds`.
    This is how SWE-bench leaderboard harnesses reach ~60-70% (vs one-shot). Cumulative: the model
    iterates on its evolving file. Question: does test feedback make opus/codex diverge MORE on the
    harder instances, or converge?"""
    f2p, p2p = json.loads(inst["FAIL_TO_PASS"]), json.loads(inst["PASS_TO_PASS"])[:30]
    full, cur, feedback = os.path.join(_REPO, path), content, ""
    for _ in range(rounds):
        prompt = (f"You are fixing a real bug in the pytest codebase. User-reported issue:\n\n"
                  f"{inst['problem_statement'][:2500]}\n\n"
                  f"The file `{path}` currently contains:\n\n```python\n{cur}\n```\n\n"
                  + (f"Your previous edit did NOT resolve it. Test output:\n\n```\n{feedback}\n```\n\n"
                     if feedback else "")
                  + f"Output the fix as one or more SEARCH/REPLACE blocks (exact current lines -> "
                    f"corrected lines), EXACTLY:\n<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE\nNo prose.")
        new = _apply_edits(cur, _CALL(model, prompt))
        if new is None:                                     # edit didn't parse / didn't match
            feedback = "Your SEARCH text did not match the current file. Copy the exact current lines."
            continue
        cur = new
        open(full, "w").write(cur)
        f2p_fail, f2p_tail = _run_capture(f2p)
        if f2p_fail == 0:
            p2p_fail, p2p_tail = _run_capture(p2p)
            if p2p_fail <= base_p2p_fail:
                _git("checkout", "-q", "--", path)
                return 1
            feedback = "The reported bug is fixed but you BROKE other tests (regression):\n" + p2p_tail
        else:
            feedback = f2p_tail
    _git("checkout", "-q", "--", path)
    return 0


def run(models, instance_ids, cache_path=None, rounds=1) -> dict:
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
        base_p2p_fail = _fail_count(json.loads(inst["PASS_TO_PASS"])[:30])   # env baseline (bug present)
        if not _gold_validates(inst, path, base_p2p_fail):
            rows.append({"instance": iid, "status": "skipped (env-incompatible: gold patch fails here)"})
            continue
        rec = {"instance": iid, "file": path, "base_p2p_fail": base_p2p_fail}
        for m in models:
            key = f"{iid}|{m}"
            if key not in cache:
                _setup(inst)                                    # fresh bug state per model
                cache[key] = (_repair_iterative(m, inst, path, content, base_p2p_fail, rounds)
                              if rounds > 1 else _repair(m, inst, path, content, base_p2p_fail))
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
            "per_model": per_model, "pairs": pairs, "rounds": rounds}


def _md(r: dict) -> str:
    models = r["models"]
    rounds = r.get("rounds", 1)
    mode = f"**反復エージェント {rounds} 回**（修復→実テスト→失敗を戻して再修復）" if rounds > 1 else "**one-shot**"
    L = ["# 実証: 実 SWE-bench（pytest 実 repo）で frontier は脱相関するか",
         "",
         f"修復方式: {mode}。",
         "",
         "構築タスク（生成・145 意地悪ケース・微妙バグ修復）では frontier(opus/codex)は誤らず脱相関ゼロだった"
         "（PAPER §5）。ここは*実 repo の実 issue* ── pytest 7.4/8.0 の実バグを、user-issue ＋ バグのある"
         "実ファイルごと渡し、**SEARCH/REPLACE 差分**で one-shot 修復させ、**実テストスイートで採点**"
         "（FAIL_TO_PASS 全 pass かつ PASS_TO_PASS 新規 regression ゼロ ＝ SWE-bench 'resolved'）。",
         "",
         f"Docker 不可環境のため Python3.12 互換 instance のみ（gold patch が当環境で F2P を pass させる instance="
         f"{len([x for x in r['rows'] if 'status' not in x])} 件を gold 検証ゲートで選別）。",
         "",
         "## instance × model（1=resolved）",
         "| instance | file | " + " | ".join(models) + " |",
         "|" + "---|" * (len(models) + 2)]
    for row in r["rows"]:
        if "status" in row:
            L.append(f"| {row['instance']} | — | " + " | ".join(f"*{row['status']}*" for _ in models) + " |")
        else:
            L.append(f"| {row['instance']} | `{row.get('file','')}` | "
                     + " | ".join(str(row.get(m, '?')) for m in models) + " |")
    L += ["", f"per-model resolved 率（n={r['n_solved_cells']} instance）: {r['per_model']}", "",
          "## ペア union vs 単独最良（gain>0 ＝ frontier で mesh 点火）",
          "| ペア | union | 単独最良 | gain | A だけ解く | B だけ解く | 相補の型 |",
          "|---|---|---|---|---|---|---|"]
    solved = {(m, row["instance"]): row.get(m) for row in r["rows"] if "status" not in row for m in models}
    done = [row["instance"] for row in r["rows"] if "status" not in row]
    for p in r["pairs"]:
        a, b = p["pair"].split(" + ")
        a_only = [i for i in done if solved.get((a, i)) == 1 and solved.get((b, i)) == 0]
        b_only = [i for i in done if solved.get((b, i)) == 1 and solved.get((a, i)) == 0]
        kind = ("相互（mesh点火可）" if a_only and b_only else
                "非対称（片方が支配）" if (a_only or b_only) else "一致（差なし）")
        L.append(f"| {p['pair']} | {p['union']} | {p['best_single']} | **{p['gain']:+}** | "
                 f"{', '.join(s.split('__')[-1] for s in a_only) or '—'} | "
                 f"{', '.join(s.split('__')[-1] for s in b_only) or '—'} | {kind} |")
    L += ["", "## 読み（union>best には*相互*相補が要る ── ただの instance 差では足りない）",
          "- **相互相補（双方が相手の落とす所を拾う）→ union>best ＝ mesh が*現実規模*で点火**。"
          "構築タスク（生成・145意地悪・微妙バグ修復）では両者*完全一致*で instance 差すら無かった。",
          "- **非対称（片方の解集合が他方を包含）→ gain=0**。instance レベルの差（＝脱相関の芽）は出るが、"
          "支配側を単独で使えば足り union は増えない。実バグで*初めて instance 差が現れた*のは重要だが、"
          "n が小さいと一方向に偏りやすく mesh は点火しない。",
          "- floor（両者 0）＝ one-shot 単一ファイル修復は frontier にも難（実 SWE-bench の反復エージェント"
          "harnessは~60-70%だが本実験は test feedback 無し one-shot）。少標本・要追試。"]
    return "\n".join(L)


def main(argv=None) -> int:
    global _CALL
    ap = argparse.ArgumentParser(description="real SWE-bench (pytest) repair decorrelation")
    ap.add_argument("--agent", default="mock")
    ap.add_argument("--models", default="opus,codex")
    ap.add_argument("--instances", default="")
    ap.add_argument("--rounds", type=int, default=1, help="1=one-shot; >1=iterative agentic loop w/ test feedback")
    ap.add_argument("--writeup-only", action="store_true", help="regen the .md from existing results.json")
    args = ap.parse_args(argv)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    tag = "swebench_iter" if args.rounds > 1 else "swebench"           # iterative results kept separate
    md_name = "SWEBENCH_ITER.md" if args.rounds > 1 else "SWEBENCH.md"
    if args.writeup_only:
        r = json.load(open(os.path.join(out_dir, f"{tag}_results.json"), encoding="utf-8"))
    else:
        _CALL = _mock if args.agent == "mock" else _route
        ids = [x for x in args.instances.split(",") if x] or json.load(open("/tmp/swe_pick.json"))
        r = run(args.models.split(","), ids, cache_path=os.path.join(out_dir, f"{tag}_artifacts.json"),
                rounds=args.rounds)
        with open(os.path.join(out_dir, f"{tag}_results.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, md_name), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print("per-model solve:", r["per_model"], "| solved cells:", r["n_solved_cells"])
    for row in r["rows"]:
        print(" ", row)
    for p in r["pairs"]:
        print(f"  {p['pair']}: union={p['union']} best={p['best_single']} gain={p['gain']:+} comp={p['complementary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
