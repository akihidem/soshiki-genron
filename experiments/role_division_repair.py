"""role_division_repair — 役割分業を *sub-ceiling 基盤*（実 SWE-bench 修復）で測る（H1 の本筋検証）。

Phase 1（`role_division.py` + `docs/role-division-phase1-results.md`）は MX のアルゴリズム gold で
役割分業を測ったが、**opus-solo が天井(1.0)** に達し H1（役割分業 > 単体最強）を公正に検証できなかった
（天井下では headroom が無く verify→repair が発火しない）。TRINITY が伸びた SWE-Bench Pro は frontier でも
73.7%＝headroom 大。ここでは `swebench_repair.py` の **実 pytest バグ修復**（one-shot は frontier でも floor
≈0＝sub-ceiling）を role_division の grade に差し込み、headroom のある regime で同じ 3 群を測る。

設計：role_division の pipeline（Thinker→Worker→Verifier＋verify→repair loop・de-confound）を**そのまま再利用**し、
prompt だけ repair 用 Substrate（SEARCH/REPLACE 差分）に差し替える。grade は per-instance closure＝
モデルの差分を元ファイルに当て、**実テストスイート（FAIL_TO_PASS 全 pass ＆ PASS_TO_PASS 新規 regression ゼロ）**で
0/1 採点（外部錨）。**Verifier には問題文＋差分のみ渡し、テスト ID も gold patch も渡さない**（H3 Goodhart 遮断）。

群：solo(opus単発=swebench one-shot 相当) / role_same(opus×3) / role_cross(opus/sonnet/haiku, verifier=haiku)。
判定：role_cross > solo→H1 点火（役割分業が実バグで単体超え＝TRINITY 再現）/ ≈solo→市場支配が sub-ceiling でも貫徹。

run: python3 -m experiments.role_division_repair --real
       RD_REPAIR_INSTANCES=pytest-dev__pytest-11148,... RD_TRIALS=1 RD_ITERS=2 で可変。
"""

from __future__ import annotations

import json
import os

import experiments.swebench_repair as SR
from experiments.role_division import (
    LGTM, Roles, Substrate, _TAGS, _cached_real_call, _deconfound, _mean,
    run_role_division, run_solo,
)

# --------------------------------------------------------------------------- #
# repair prompts — すべて role タグ付き。問題文＋元ファイルのみ（テスト ID / gold patch は渡さない）。
# inst には runner が _rd_path / _rd_content を付与済み（元バグファイルのパスと全文）。
# --------------------------------------------------------------------------- #
_FMT = ("Output the fix as one or more SEARCH/REPLACE blocks, EXACTLY this format:\n"
        "<<<<<<< SEARCH\n(lines copied verbatim from the file)\n=======\n(the corrected lines)\n"
        ">>>>>>> REPLACE\nThe SEARCH text must match the file's current lines EXACTLY, indentation "
        "included. Keep it minimal — only the lines that change.")


def _issue(inst: dict) -> str:
    return inst["problem_statement"][:2500]


def _r_thinker(inst: dict) -> str:
    return (f"{_TAGS['thinker']} You are the PLANNER fixing a real bug in the pytest codebase. "
            f"User-reported issue:\n{_issue(inst)}\n\nBuggy file `{inst['_rd_path']}`:\n"
            f"```python\n{inst['_rd_content']}\n```\n\n"
            "Produce a concise PLAN: the root cause and EXACTLY which lines to change and how. "
            "Do NOT write the diff yet — plan only.")


def _r_worker(inst: dict, plan: str, prev_code: str | None = None, critique: str | None = None) -> str:
    s = (f"{_TAGS['worker']} You are the IMPLEMENTER fixing a real bug in the pytest codebase. "
         f"User-reported issue:\n{_issue(inst)}\n\nThe buggy file `{inst['_rd_path']}` FULL content:\n"
         f"```python\n{inst['_rd_content']}\n```\n\nPLAN to follow:\n{plan}\n")
    if prev_code is not None:
        s += (f"\nYour previous fix did NOT resolve it:\n{prev_code}\n"
              f"A reviewer found these problems — address them:\n{critique}\n")
    return s + "\n" + _FMT + " No prose, no explanation."


def _r_verifier(inst: dict, code: str) -> str:
    return (f"{_TAGS['verifier']} You are the REVIEWER. A proposed SEARCH/REPLACE fix for this pytest "
            f"issue:\n{_issue(inst)}\n\nThe buggy file is `{inst['_rd_path']}`. Proposed fix:\n{code}\n\n"
            "Will this fix the root cause WITHOUT breaking other behavior? List concrete problems with "
            f"the SEARCH/REPLACE (wrong/non-matching lines, missed cases, likely regressions), or if it "
            f"is correct reply with EXACTLY: {LGTM}\n"
            "You have NO access to the test suite — judge from the issue and the code only.")


def _r_solo(inst: dict) -> str:
    return (f"{_TAGS['solo']} You are fixing a real bug in the pytest codebase. User-reported issue:\n"
            f"{_issue(inst)}\n\nThe buggy file `{inst['_rd_path']}` FULL content:\n"
            f"```python\n{inst['_rd_content']}\n```\n\n" + _FMT + " No prose, no explanation.")


_REPAIR_SUB = Substrate(_r_thinker, _r_worker, _r_verifier, _r_solo)


def _arms() -> dict:
    return {"solo": "opus",
            "role_same": Roles("opus", "opus", "opus"),
            "role_cross": Roles("opus", "sonnet", "haiku")}


# --------------------------------------------------------------------------- #
# grade closure — 外部錨。モデルの差分を *元ファイル* に当て、実テストで 0/1 採点し、ファイルを戻す。
# repo は事前に _setup(inst) で base+test_patch・ファイル=バグ状態に置かれている前提（呼び出し後も維持）。
# --------------------------------------------------------------------------- #
def make_repair_grade(inst: dict, path: str, content: str, base_p2p_fail: int):
    f2p = SR._to_pytest_args(inst, json.loads(inst["FAIL_TO_PASS"]))
    p2p = SR._to_pytest_args(inst, json.loads(inst["PASS_TO_PASS"])[:30])
    full = os.path.join(SR._REPO, path)

    def grade(code: str, task: dict) -> float:
        new = SR._apply_edits(content, code)                 # SEARCH/REPLACE を元ファイルへ適用
        if new is None:                                      # 差分が parse/match しない → 失敗
            return 0.0
        try:
            with open(full, "w", encoding="utf-8") as f:
                f.write(new)
            f2p_ok = SR._fail_count(f2p) == 0                # 報告バグが直った
            p2p_ok = SR._fail_count(p2p) <= base_p2p_fail    # 新規 regression なし
            return 1.0 if (f2p_ok and p2p_ok) else 0.0
        except Exception:
            return 0.0
        finally:
            SR._git("checkout", "-q", "--", path)            # 次の採点のためファイルをバグ状態へ戻す

    return grade


def run_repair(instance_ids: list, n_iter: int, trials: int, call, out_path: str | None = None) -> dict:
    """各 instance を _setup→gold 検証し、3 群を role_division の pipeline で回して de-confound。"""
    allinst = {i["instance_id"]: i for i in json.load(open(SR._INSTANCES_JSON, encoding="utf-8"))}
    cells, skipped = [], []
    arms = _arms()
    for iid in instance_ids:
        inst = allinst.get(iid)
        if inst is None:
            skipped.append({"instance": iid, "status": "unknown id"}); continue
        path = SR._edited_file(inst["patch"])
        if not path or not SR._setup(inst):                  # checkout base + test_patch + bug 再現確認
            skipped.append({"instance": iid, "status": "skipped (setup/bug-repro failed)"}); continue
        content = open(os.path.join(SR._REPO, path), encoding="utf-8", errors="replace").read()
        base_p2p_fail = SR._fail_count(SR._to_pytest_args(inst, json.loads(inst["PASS_TO_PASS"])[:30]))
        if not SR._gold_validates(inst, path, base_p2p_fail):   # 当環境で gold が通らない instance は skip
            skipped.append({"instance": iid, "status": "skipped (env-incompatible)"}); continue
        grade = make_repair_grade(inst, path, content, base_p2p_fail)
        task = {**inst, "id": iid, "_rd_path": path, "_rd_content": content}
        for group, spec in arms.items():
            runs = []
            for t in range(trials):
                if group == "solo":
                    r = run_solo(spec, task, call, grade, seed=t, sub=_REPAIR_SUB)
                else:
                    r = run_role_division(spec, task, call, grade, n_iter, group, seed=t, sub=_REPAIR_SUB)
                runs.append(r)
            cells.append({"task": iid, "group": group, "file": path,
                          "mean_score": _mean([r["score"] for r in runs]),
                          "mean_cost": _mean([r["cost"] for r in runs]),
                          "scores": [r["score"] for r in runs]})
            print(f"  {iid:<28} {group:<11} mean_score={cells[-1]['mean_score']} "
                  f"mean_cost={cells[-1]['mean_cost']} scores={cells[-1]['scores']}")
            if out_path:                                      # 中断しても部分結果が読める
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump({"cells": cells, "skipped": skipped, "summary": _deconfound(cells),
                               "n_iter": n_iter, "trials": trials}, f, ensure_ascii=False, indent=2)
    return {"cells": cells, "skipped": skipped, "summary": _deconfound(cells),
            "n_iter": n_iter, "trials": trials}


def main(argv=None) -> int:
    import sys
    av = argv if argv is not None else sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    if "--real" not in av:
        print("role_division_repair needs --real (runs real pytest + metered Claude). "
              "See docs/role-division-phase1-results.md for context.")
        return 2
    import experiments.market_external as MX
    MX._CALL = MX._route
    pick = os.environ.get("RD_REPAIR_INSTANCES")
    if pick:
        instance_ids = pick.split(",")
    elif os.path.exists("/tmp/swe_pick.json"):
        instance_ids = json.load(open("/tmp/swe_pick.json"))
    else:
        instance_ids = [i["instance_id"] for i in json.load(open(SR._INSTANCES_JSON, encoding="utf-8"))]
    trials = int(os.environ.get("RD_TRIALS", "1"))
    n_iter = int(os.environ.get("RD_ITERS", "2"))
    cp = os.path.join(here, "role_division_repair_artifacts.json")
    cache = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    call = _cached_real_call(cache, cp)
    out_path = os.path.join(here, "role_division_repair_real.json")
    print(f"role_division_repair --real (metered Claude + real pytest): instances={instance_ids} "
          f"trials={trials} n_iter={n_iter}  arms=solo:opus / same:opus×3 / cross:opus/sonnet/haiku")
    res = run_repair(instance_ids, n_iter, trials, call, out_path)
    s = res["summary"]
    print("\n=== REPAIR (real pytest gold, sub-ceiling) ===")
    print(f"  group_score={s.get('group_score')}  group_cost={s.get('group_cost')}")
    for k in ("structure_gain (role_same - solo)", "diversity_gain (role_cross - role_same)",
              "total_gain (role_cross - solo)"):
        if k in s:
            print(f"     {k}: {s[k]}")
    print(f"  skipped={[x['instance'] for x in res['skipped']]}")
    print("\nverdict: H1 (role_cross > solo) =", s.get("total_gain (role_cross - solo)", 0.0),
          "| H2 (cross > same) =", s.get("diversity_gain (role_cross - role_same)", 0.0))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
