"""role_division — 役割分業 coordinator は冗長 mesh と違い単体最強を超えるか（PAPER §6.5 の盲点を測る）。

2026-06-23 で「**冗長並列 mesh**（同タスクを独立に解いた union/synthesis）」は5角度で不点火＝
*市場支配*（単一最強が最適）を確認した（`docs/industry-benchmarks.md` §1–9）。だが Sakana の
**TRINITY / Fugu**（ICLR 2026）は「**役割分業**（Thinker/Worker/Verifier）＋検証」で単体超えを実証＝
*別メカニズム*。soshiki-genron は §6.5 で役割分業を処方しながら冗長 mesh しか潰していなかった＝盲点
（`docs/role-division-research-plan.md`）。本モジュールはその処方を*動く実行系*にして外部 gold で測る。

パイプライン（3 role＋verify→repair loop・外部検証が背骨）:
  THINKER(spec)               -> plan（アルゴリズム＋edge case の段取り・コードは書かない）
  WORKER(spec, plan[, critique]) -> code（plan に沿って実装／critique で修正）
  VERIFIER(spec, code)        -> critique（具体的バグ/抜けを列挙、無ければ LGTM）
  loop: 外部 gold が 1.0 で停止 or Verifier が LGTM or n_iter 到達。**gold は採点/停止ゲートのみ**、
        Verifier には非開示（spec+code だけ渡す＝Goodhart 遮断・H3）。

群（model 割当）と de-confound:
  solo       … opus 単発 monolithic（role 分離なし・repair なし）＝単一最強 baseline
  role_same  … Thinker/Worker/Verifier すべて opus（分業だが単一モデル＝*反復効果*の対照）
  role_cross … Thinker=opus / Worker=sonnet / Verifier=haiku（§8 で haiku が良い検証者）
  structure_gain = role_same − solo（役割分業*構造*の利得）
  diversity_gain = role_cross − role_same（*役割別モデル配置*の純利得＝H2 の核）

エージェントは `call(model, prompt, seed) -> str` の関数（mock で決定的・LLM 差し替えは seam のみ）。
最終スコアは `grade(code, task) -> float`（mock or 外部 sandbox gold = MX.grade）。

run: python3 -m experiments.role_division           （決定的 mock デモ：null/positive 両世界）
     python3 -m experiments.role_division --real     （実LLM：opus/sonnet/haiku・外部 gold・metered）
       RD_TASKS=calc3,negabinary RD_TRIALS=3 RD_ITERS=2 で可変。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LGTM = "LGTM"

# tier-weighted cost（price proxy・meshflow.llm_demo と同じ重み）。未知モデルは 1.0。
WEIGHTS = {"opus": 15.0, "sonnet": 3.0, "haiku": 1.0, "gemma": 0.2, "gemma4:e2b": 0.2}

# 各 prompt 先頭に置く role タグ（実 LLM には無害な指示・mock はこれで role を識別する）。
_TAGS = {"thinker": "[ROLE:THINKER]", "worker": "[ROLE:WORKER]",
         "verifier": "[ROLE:VERIFIER]", "solo": "[ROLE:SOLO]"}


def _w(model: str) -> float:
    return WEIGHTS.get(model, 1.0)


@dataclass(frozen=True)
class Roles:
    thinker: str
    worker: str
    verifier: str


# --------------------------------------------------------------------------- #
# prompts — role ごとの指示。VERIFIER には task["gold"] を一切渡さない（gold-leak 遮断）。
# --------------------------------------------------------------------------- #
def _thinker_prompt(task: dict) -> str:
    names = ", ".join(task["names"])
    return (f"{_TAGS['thinker']} You are the PLANNER. Produce a concise step-by-step PLAN to implement "
            f"these Python functions: {names}.\nSpec: {task['spec']}\n"
            "State the algorithm and the tricky edge cases (empty / negative / zero / boundary / overflow "
            "/ malformed). Do NOT write code — plan only.")


def _worker_prompt(task: dict, plan: str, prev_code: str | None = None, critique: str | None = None) -> str:
    names = ", ".join(task["names"])
    s = (f"{_TAGS['worker']} You are the IMPLEMENTER. There is NO existing file — write from scratch. "
         f"Implement these Python functions to satisfy the spec EXACTLY, handling ALL edge cases.\n"
         f"Spec: {task['spec']}\nRequired functions: {names}.\nPLAN to follow:\n{plan}\n")
    if prev_code is not None:
        s += (f"Your previous code:\n```python\n{prev_code}\n```\n"
              f"A reviewer found these issues — fix them so all cases pass:\n{critique}\n")
    return s + "Respond with ONLY a single python code block — no tests, no prose, no preamble."


def _verifier_prompt(task: dict, code: str) -> str:
    names = ", ".join(task["names"])
    return (f"{_TAGS['verifier']} You are the REVIEWER. Review this code against the spec for correctness. "
            "List concrete bugs and missing edge cases (empty / negative / zero / boundary / overflow / "
            f"malformed). If it is fully correct, reply with EXACTLY: {LGTM}\n"
            f"Spec: {task['spec']}\nRequired functions: {names}.\n"
            f"Code under review:\n```python\n{code}\n```\n"
            "Do NOT rewrite the solution — point out problems only. You have NO access to hidden tests.")


def _solo_prompt(task: dict) -> str:
    names = ", ".join(task["names"])
    return (f"{_TAGS['solo']} There is NO existing file — write from scratch. Plan internally, then "
            f"implement these Python functions to satisfy the spec EXACTLY, handling ALL edge cases.\n"
            f"Spec: {task['spec']}\nRequired functions: {names}.\n"
            "Respond with ONLY a single python code block — no tests, no prose, no preamble.")


def _is_lgtm(critique: str) -> bool:
    return LGTM in (critique or "").upper()


# --------------------------------------------------------------------------- #
# substrate — prompt 群を差し替え可能にする seam。default は上の codegen（実装課題）。
# 別 substrate（例: 実バグ修復 swebench）は同じ pipeline を再利用しつつ prompt だけ替える。
# grade は呼び出し側が渡す（基盤ごとに外部 gold が違うため）。挙動は default で Phase 1 と不変。
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Substrate:
    thinker_prompt: "callable"     # (task) -> str
    worker_prompt: "callable"      # (task, plan, prev_code=None, critique=None) -> str
    verifier_prompt: "callable"    # (task, code) -> str
    solo_prompt: "callable"        # (task) -> str


_CODEGEN_SUB = Substrate(_thinker_prompt, _worker_prompt, _verifier_prompt, _solo_prompt)


# --------------------------------------------------------------------------- #
# pipeline — 1 群 × 1 タスク × 1 試行を回す。外部 gold が背骨（採点＋停止ゲート）。
# --------------------------------------------------------------------------- #
def run_solo(model: str, task: dict, call, grade, seed: int = 0, sub: Substrate = _CODEGEN_SUB) -> dict:
    """単一最強 baseline：1 呼びで plan+implement（role 分離も repair も無し）。"""
    code = call(model, sub.solo_prompt(task), seed)
    score = grade(code, task)
    return {"group": "solo", "score": score, "cost": round(_w(model), 3),
            "iters": [{"iter": 0, "stage": "solo", "score": score}], "code": code,
            "calls": [("worker", model)]}


def run_role_division(roles: Roles, task: dict, call, grade, n_iter: int, group: str, seed: int = 0,
                      sub: Substrate = _CODEGEN_SUB) -> dict:
    """Thinker→Worker→(Verifier→Worker)* の分業パイプライン。各 code 版を gold で1回だけ採点。"""
    calls = []
    plan = call(roles.thinker, sub.thinker_prompt(task), seed); calls.append(("thinker", roles.thinker))
    code = call(roles.worker, sub.worker_prompt(task, plan), seed); calls.append(("worker", roles.worker))
    cost = _w(roles.thinker) + _w(roles.worker)
    score = grade(code, task)
    iters = [{"iter": 0, "stage": "initial", "score": score}]
    it = 0
    while score < 1.0 and it < n_iter:                       # verify→repair ループ
        critique = call(roles.verifier, sub.verifier_prompt(task, code), seed)
        calls.append(("verifier", roles.verifier))
        cost += _w(roles.verifier)
        if _is_lgtm(critique):                               # Verifier が「直す所なし」→ 停止
            iters.append({"iter": it + 1, "stage": "lgtm", "score": score})
            break
        code = call(roles.worker, sub.worker_prompt(task, plan, code, critique), seed)
        calls.append(("worker", roles.worker))
        cost += _w(roles.worker)
        score = grade(code, task)
        it += 1
        iters.append({"iter": it, "stage": "repair", "score": score})
    return {"group": group, "score": score, "cost": round(cost, 3),
            "iters": iters, "code": code, "calls": calls, "plan": plan}


def _run_one(group: str, spec, task: dict, call, grade, n_iter: int, seed: int,
             sub: Substrate = _CODEGEN_SUB) -> dict:
    if group == "solo":
        return run_solo(spec, task, call, grade, seed, sub)       # spec = model str
    return run_role_division(spec, task, call, grade, n_iter, group, seed, sub)  # spec = Roles


def _tid(task: dict) -> str:
    return task.get("id") or task.get("instance_id")             # codegen は id / repair は instance_id


def _mean(xs: list) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def run_groups(tasks: list, arms: dict, call, grade, n_iter: int = 2, trials: int = 1,
               sub: Substrate = _CODEGEN_SUB) -> dict:
    """全 (task × group × trial) を回し、群ごとの平均スコア/コストと de-confound を返す。"""
    cells = []
    for task in tasks:
        for group, spec in arms.items():
            runs = [_run_one(group, spec, task, call, grade, n_iter, seed=t, sub=sub) for t in range(trials)]
            cells.append({"task": _tid(task), "group": group,
                          "mean_score": _mean([r["score"] for r in runs]),
                          "mean_cost": _mean([r["cost"] for r in runs]),
                          "scores": [r["score"] for r in runs]})
    return {"cells": cells, "summary": _deconfound(cells), "n_iter": n_iter, "trials": trials}


def _deconfound(cells: list) -> dict:
    groups = {}
    for c in cells:
        groups.setdefault(c["group"], {"s": [], "c": []})
        groups[c["group"]]["s"].append(c["mean_score"])
        groups[c["group"]]["c"].append(c["mean_cost"])
    g = {grp: _mean(v["s"]) for grp, v in groups.items()}
    cost = {grp: _mean(v["c"]) for grp, v in groups.items()}
    out = {"group_score": g, "group_cost": cost}
    if "solo" in g and "role_same" in g:
        out["structure_gain (role_same - solo)"] = round(g["role_same"] - g["solo"], 3)
    if "role_same" in g and "role_cross" in g:
        out["diversity_gain (role_cross - role_same)"] = round(g["role_cross"] - g["role_same"], 3)
    if "solo" in g and "role_cross" in g:
        out["total_gain (role_cross - solo)"] = round(g["role_cross"] - g["solo"], 3)
    return out


# --------------------------------------------------------------------------- #
# 決定的 mock の砦 — 科学的結論は出さない。harness（決定性/コスト/de-confound 算術）を検品する。
#
# mock world は「能力の符号化」: 各 model に capability、各 task に difficulty。worker の出力
# "CODE|cap=<eff>" を mock grade が復号し `1.0 iff eff >= difficulty`。eff は
#   worker_cap + plan_boost(thinker由来) + verify_power(critique由来)
# で決まる。plan は "PLAN|boost=K"、critique は "CRITIQUE|power=P" を worker prompt に埋め、
# worker call がそれを読んで eff に足す。これにより *役割別配置の利得* が「捏造でなく機構から」出る。
# --------------------------------------------------------------------------- #
def make_mock_call(world: dict):
    """world = {"cap": {model:int}, "plan_boost": {model:int}, "verify_power": {model:int}}."""
    def call(model: str, prompt: str, seed: int = 0) -> str:
        if prompt.startswith(_TAGS["thinker"]):
            return f"PLAN|boost={world.get('plan_boost', {}).get(model, 0)}"
        if prompt.startswith(_TAGS["verifier"]):
            p = world.get("verify_power", {}).get(model, 0)
            return LGTM if p < 0 else f"CRITIQUE|power={p}"   # power<0 で LGTM（無批判の対照）
        # worker / solo: 実効能力を符号化（plan/critique が prompt にあれば加算）
        eff = world.get("cap", {}).get(model, 0)
        if prompt.startswith(_TAGS["worker"]):
            mb = re.search(r"PLAN\|boost=(-?\d+)", prompt)
            mp = re.search(r"CRITIQUE\|power=(-?\d+)", prompt)
            eff += (int(mb.group(1)) if mb else 0) + (int(mp.group(1)) if mp else 0)
        return f"CODE|cap={eff}"
    return call


def make_mock_grade(world: dict):
    """world["diff"] = {task_id: difficulty}. eff>=diff で 1.0、未満は線形 partial。"""
    def grade(code: str, task: dict) -> float:
        m = re.search(r"cap=(-?\d+)", code or "")
        eff = int(m.group(1)) if m else 0
        diff = world["diff"][task["id"]]
        if diff <= 0:
            return 1.0
        return 1.0 if eff >= diff else round(max(0.0, eff / diff), 3)
    return grade


def _mock_arms() -> dict:
    return {"solo": "opus",
            "role_same": Roles("opus", "opus", "opus"),
            "role_cross": Roles("opus", "sonnet", "haiku")}


# null world: 何も寄与しない（caps 等しい・plan/verify 力ゼロ）→ 全群同点＝市場支配を再現。
_NULL_WORLD = {"diff": {"easy": 2, "hard": 3},
               "cap": {"opus": 2, "sonnet": 2, "haiku": 2},
               "plan_boost": {"opus": 0, "sonnet": 0, "haiku": 0},
               "verify_power": {"opus": 0, "sonnet": 0, "haiku": 0}}

# positive world: haiku だけが有効な検証者（§8 の写像）。plan 力は0に固定し diversity を単離。
# hard(diff=3): solo opus=2→0.667 / role_same(verifier=opus power0)→直らず0.667 /
#               role_cross(verifier=haiku power2)→repair で eff=2+2=4>=3→1.0。
_POSITIVE_WORLD = {"diff": {"easy": 2, "hard": 3},
                   "cap": {"opus": 2, "sonnet": 2, "haiku": 2},
                   "plan_boost": {"opus": 0, "sonnet": 0, "haiku": 0},
                   "verify_power": {"opus": 0, "sonnet": 1, "haiku": 2}}

_MOCK_TASKS = [{"id": "easy", "names": ["f"], "spec": "easy"},
               {"id": "hard", "names": ["g"], "spec": "hard"}]


# --------------------------------------------------------------------------- #
# 実LLM seam — call = MX._route（gemma→ollama / claude→runner）、grade = 外部 sandbox gold。
# call は (model, prompt, seed) でキャッシュ（再実行/中断で無駄打ちしない・metered 保護）。
# --------------------------------------------------------------------------- #
def _real_arms() -> dict:
    return {"solo": "opus",
            "role_same": Roles("opus", "opus", "opus"),
            "role_cross": Roles("opus", "sonnet", "haiku")}


def _cached_real_call(cache: dict, cache_path: str):
    import hashlib
    import json
    import experiments.market_external as MX

    def call(model: str, prompt: str, seed: int = 0) -> str:
        key = f"{model}|t{seed}|{hashlib.sha256(prompt.encode()).hexdigest()[:16]}"
        if key not in cache:
            cache[key] = MX._route(model, prompt)
            if cache_path:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
        return cache[key]
    return call


def _real_grade():
    import experiments.market_external as MX

    def grade(code: str, task: dict) -> float:
        return MX.grade(code, task).get("correctness") or 0.0
    return grade


def _run_mock_demo() -> dict:
    call_n, grade_n = make_mock_call(_NULL_WORLD), make_mock_grade(_NULL_WORLD)
    call_p, grade_p = make_mock_call(_POSITIVE_WORLD), make_mock_grade(_POSITIVE_WORLD)
    null = run_groups(_MOCK_TASKS, _mock_arms(), call_n, grade_n, n_iter=2, trials=1)
    pos = run_groups(_MOCK_TASKS, _mock_arms(), call_p, grade_p, n_iter=2, trials=1)
    return {"null_world": null, "positive_world": pos}


def _print_summary(title: str, res: dict) -> None:
    s = res["summary"]
    print(f"  [{title}] group_score={s['group_score']}  group_cost={s['group_cost']}")
    for k in ("structure_gain (role_same - solo)", "diversity_gain (role_cross - role_same)",
              "total_gain (role_cross - solo)"):
        if k in s:
            print(f"     {k}: {s[k]}")


def main(argv=None) -> int:
    import json
    import os
    import sys
    av = argv if argv is not None else sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))

    if "--real" in av:
        import experiments.market_external as MX
        MX._CALL = MX._route                                  # 実LLM routing（gen_impl 等の経路も合わせる）
        tasks_env = os.environ.get("RD_TASKS", "calc3,negabinary,fraction_to_decimal").split(",")
        trials = int(os.environ.get("RD_TRIALS", "2"))
        n_iter = int(os.environ.get("RD_ITERS", "2"))
        by_id = {t["id"]: t for t in (MX._HARD_TASKS + MX._LADDER_TASKS + MX.EXT_TASKS + MX._EASY_TASKS)}
        tasks = [by_id[t] for t in tasks_env if t in by_id]
        if not tasks:
            print(f"no valid RD_TASKS in {tasks_env}; available: {sorted(by_id)}")
            return 2
        cp = os.path.join(here, "role_division_real_artifacts.json")
        cache = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
        call = _cached_real_call(cache, cp)
        grade = _real_grade()
        print(f"role_division --real (metered Claude): tasks={[t['id'] for t in tasks]} "
              f"trials={trials} n_iter={n_iter}  arms=solo:opus / same:opus×3 / cross:opus/sonnet/haiku")
        res = run_groups(tasks, _real_arms(), call, grade, n_iter=n_iter, trials=trials)
        with open(os.path.join(here, "role_division_real.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("\n=== REAL (external sandbox gold) ===")
        for c in res["cells"]:
            print(f"  {c['task']:<20} {c['group']:<11} mean_score={c['mean_score']} "
                  f"mean_cost={c['mean_cost']} scores={c['scores']}")
        _print_summary("REAL", res)
        s = res["summary"]
        print("\nverdict: H1 (role_cross > solo) =", s.get("total_gain (role_cross - solo)", 0.0),
              "| H2 (cross > same) =", s.get("diversity_gain (role_cross - role_same)", 0.0))
        print("wrote role_division_real.json")
        return 0

    res = _run_mock_demo()
    with open(os.path.join(here, "role_division_demo.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("role_division mock demo (DETERMINISTIC — harness check, NOT a scientific result):")
    print(" null world (no role contributes) -> gains must be ~0 (reproduces market dominance):")
    _print_summary("null", res["null_world"])
    print(" positive world (haiku is the effective verifier) -> diversity_gain must be > 0:")
    _print_summary("positive", res["positive_world"])
    print("wrote role_division_demo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
