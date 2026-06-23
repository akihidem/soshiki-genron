"""config_mesh — lever ② の実証: *config 散らし*は mutual 相補を「作る」か。

問い（[`../docs/trinity-vs-soshiki.md`](../docs/trinity-vs-soshiki.md) の next を一段具体化）:
soshiki は whole-problem の frontier mesh ≈0 を実測した（解集合が*入れ子/asymmetric*）。
cost度外視で精度を上げる鍵は「並列の数」でなく「**外し方をバラけさせる(mutual 相補を作る)**」
＋「実行検証で拾う」だと論じた。その第一の lever ＝ **同じモデルに*違う構成(framing)*を与えると、
*同じ構成を繰り返す*より union が広がるか** を、計算量を揃えて測る。

設計（matched-budget A/B・外部 gold 採点）:
  Arm A  "同 config 反復": 既定 framing を K 回（seed 違い）→ union
  Arm B  "config 散らし":  K 種の framing を 1 回ずつ（seed 違い）→ union
  両者とも K 試行＝同予算。差 (B_union − A_union) ＝ *config 多様性が「ただの再試行」を超えて
  足す coverage*。これが >0 なら「外し方は構成でバラけさせられる」＝frontier rescue の核が生きる。
  ≈0 なら lever ② は死（hard core は framing では割れない）。

正直なスコープ: ここは**ローカルモデル（弱い縁）**での*機構*テスト。frontier 本番（claude/codex runner）は
metered で別。trials は config あたり 1（seed 1 本）＝少標本。採点は sandbox gold（自己申告でなく外部）。

run: python3 -m experiments.config_mesh        （全モデル×全タスク）
     CM_MODELS=qwen2.5-coder:7b CM_TASKS=edit_distance,calc python3 -m experiments.config_mesh  （絞り）
"""
from __future__ import annotations

import json
import os
import urllib.request

import experiments.market_external as MX

_HOST = "http://localhost:11434"

# K=4 の framing。すべて「コードブロックのみ」を要求（grade は python block を抽出するため）。
# C1 は market_external.gen_impl と同型の素の指示＝Arm A の反復対象。
_CONFIGS = {
    "direct":    "There is NO existing file or prior code — write from scratch. Implement these Python "
                 "functions to satisfy the spec EXACTLY, handling ALL edge cases.",
    "decompose": "Silently break the problem into sub-steps and solve each, then implement. Write from "
                 "scratch and satisfy the spec EXACTLY.",
    "edgefirst": "Focus FIRST on the tricky edge cases (empty input, negatives, zero, overflow, boundary "
                 "indices, malformed input), then implement from scratch to satisfy the spec EXACTLY.",
    "algorithmic": "Recall the standard/classic algorithm for this problem and implement it carefully from "
                   "scratch, satisfying the spec EXACTLY and handling all edge cases.",
}
_DEFAULT_CONFIG = "direct"
K = 4


def _prompt(task: dict, framing: str) -> str:
    names = ", ".join(task["names"])
    return (f"{framing}\nSpec: {task['spec']}\nRequired functions: {names}.\n"
            f"Respond with ONLY a single python code block — no tests, no prose, no preamble.")


# Mac Studio MLX servers via SSH tunnel (OpenAI-compatible /v1/chat/completions).
_MLX = {"devstral": (8080, "mlx-community/Devstral-Small-2-24B-Instruct-2512-4bit", 1800),
        "mac-qwen": (8082, "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", 1800),
        "qwen122": (8081, "mlx-community/Qwen3.5-122B-A10B-4bit", 8192)}  # reasoning -> high max_tokens


def _mlx_chat(model: str, prompt: str, seed: int, temperature: float = 0.7, timeout: int = 600) -> str:
    port, mid, maxtok = _MLX[model]
    body = json.dumps({"model": mid, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": maxtok, "temperature": temperature, "seed": seed}).encode()
    req = urllib.request.Request(f"http://localhost:{port}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""


def _ollama(model: str, prompt: str, seed: int, temperature: float = 0.7, timeout: int = 150) -> str:
    if model in _MLX:                                  # route Mac Studio models through the tunnel
        return _mlx_chat(model, prompt, seed, temperature)
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": temperature, "seed": seed}}).encode()
    req = urllib.request.Request(f"{_HOST}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()).get("response", "") or ""
    except Exception:
        return ""


def _first_block(text: str) -> str:
    """最初の fenced python block だけ取る。冗長な chat モデル(Devstral 等)が複数ブロックを
    出すと MX._extract_code が連結して SyntaxError になる罠を回避。fence 無しは MX に委譲。"""
    import re as _r
    m = _r.search(r"```(?:python)?\s*\n?(.*?)```", text, _r.DOTALL)
    return m.group(1) if m else MX._extract_code(text)


def _attempt(model: str, task: dict, framing: str, seed: int) -> dict:
    out = _ollama(model, _prompt(task, _CONFIGS[framing]), seed)
    g = MX.grade(out, task)
    return {"framing": framing, "seed": seed, "correctness": g["correctness"], "ran": g["ran"]}


def _union(attempts: list) -> float:
    return max((a["correctness"] for a in attempts), default=0.0)


# --------------------------------------------------------------------------- #
# Arm C: feedback loop（/goal+/loop の機構＝目標条件まで実行検証で自己改善）。
# blind な A/B と違い *前の失敗を見て直す*。Goodhart 回避: feedback は p/n と crash trace
# のみ・期待出力は見せない（gold I/O を渡さない）。matched budget = N 反復。
# --------------------------------------------------------------------------- #
def _repair_prompt(task: dict, prev_code: str, g: dict) -> str:
    names = ", ".join(task["names"])
    if not g.get("ran"):
        fb = f"Your previous code FAILED TO RUN. Error:\n{g.get('err', '')[:200]}\nFix the error."
    else:
        fb = (f"Your previous code RAN but passed only {g.get('passed', 0)}/{g.get('total', 0)} hidden "
              f"correctness tests — some inputs give WRONG output. Re-examine edge cases (empty, negative, "
              f"zero, boundaries, large/odd inputs, malformed input) and FIX the logic.")
    return (f"You are improving a Python solution. Spec: {task['spec']}\nRequired functions: {names}.\n{fb}\n"
            f"Your previous code:\n```python\n{prev_code}\n```\n"
            f"Respond with ONLY a single corrected python code block — no tests, no prose.")


def _loop_attempt(model: str, task: dict, n_iter: int) -> dict:
    """目標(gold=1.0)に達するまで feedback で自己改善・最大 n_iter 反復。"""
    iters, prev_code, g = [], "", {}
    for it in range(n_iter):
        prompt = _prompt(task, _CONFIGS[_DEFAULT_CONFIG]) if it == 0 else _repair_prompt(task, prev_code, g)
        out = _ollama(model, prompt, seed=it)
        g = MX.grade(out, task)
        prev_code = MX._extract_code(out)
        iters.append({"iter": it, "correctness": g["correctness"], "ran": g["ran"]})
        if g["correctness"] >= 1.0:
            break
    return {"iters": iters, "C_final": iters[-1]["correctness"],
            "C_best": max(a["correctness"] for a in iters),
            "resolved_iter": next((a["iter"] for a in iters if a["correctness"] >= 1.0), None)}


def run_loop(models: list, tasks: list, n_iter: int, out_path: str) -> dict:
    rows, artifacts = [], []
    for model in models:
        for task in tasks:
            c = _loop_attempt(model, task, n_iter)
            rows.append({"model": model, "task": task["id"], "C_final": c["C_final"],
                         "C_best": c["C_best"], "resolved_iter": c["resolved_iter"],
                         "trajectory": [a["correctness"] for a in c["iters"]]})
            artifacts.append({"model": model, "task": task["id"], **c})
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"rows": rows, "n_iter": n_iter}, f, ensure_ascii=False, indent=2)
            r = rows[-1]
            print(f"  {model:<18} {task['id']:<16} traj={r['trajectory']}  resolved@{r['resolved_iter']}")
    with open(out_path.replace("_results", "_artifacts"), "w", encoding="utf-8") as f:
        json.dump(artifacts, f, ensure_ascii=False, indent=2)
    solved = sum(1 for r in rows if r["C_best"] >= 1.0)
    return {"rows": rows, "loop_solve_rate": round(solved / len(rows), 3) if rows else 0.0}


def run(models: list, tasks: list, out_path: str) -> dict:
    rows, artifacts = [], []
    for model in models:
        for task in tasks:
            # Arm A: 同 config(direct) を K 回・seed 0..K-1
            a_att = [_attempt(model, task, _DEFAULT_CONFIG, s) for s in range(K)]
            # Arm B: K 種 framing を 1 回ずつ・seed 0..K-1（A と同じ seed 列＝サンプリング分散を相殺、差は構成だけ）
            b_att = [_attempt(model, task, f, s) for s, f in enumerate(_CONFIGS.keys())]
            a_u, b_u = _union(a_att), _union(b_att)
            single = a_att[0]["correctness"]                       # direct 単発（C1 seed0）
            b_solvers = [a["framing"] for a in b_att if a["correctness"] >= 1.0]
            a_solved = a_u >= 1.0
            b_solved = b_u >= 1.0
            # config 多様性 *固有* の解: B が 1.0 かつ それを default 以外の framing だけが達成
            b_only_nondefault = (b_solved and not any(
                a["framing"] == _DEFAULT_CONFIG and a["correctness"] >= 1.0 for a in b_att))
            rows.append({"model": model, "task": task["id"], "single": single,
                         "A_union": a_u, "B_union": b_u, "A_solved": a_solved, "B_solved": b_solved,
                         "B_solvers": b_solvers, "B_solved_only_by_nondefault": b_only_nondefault})
            artifacts.append({"model": model, "task": task["id"], "A": a_att, "B": b_att})
            with open(out_path, "w", encoding="utf-8") as f:  # incremental: partial readable if interrupted
                json.dump({"rows": rows, "summary": _summary(rows)}, f, ensure_ascii=False, indent=2)
            r = rows[-1]
            print(f"  {model:<18} {task['id']:<16} single={single}  A_un={a_u}  B_un={b_u}  "
                  f"B_solvers={b_solvers}")
    with open(out_path.replace("_results", "_artifacts"), "w", encoding="utf-8") as f:
        json.dump(artifacts, f, ensure_ascii=False, indent=2)
    return {"rows": rows, "summary": _summary(rows)}


def _rate(rows, key):
    return round(sum(1 for r in rows if r[key]) / len(rows), 3) if rows else 0.0


def _summary(rows: list) -> dict:
    n = len(rows)
    single_rate = round(sum(1 for r in rows if r["single"] >= 1.0) / n, 3) if n else 0.0
    a_rate, b_rate = _rate(rows, "A_solved"), _rate(rows, "B_solved")
    only_b = sum(1 for r in rows if r["B_solved"] and not r["A_solved"])   # B 解く・A 解けず
    only_a = sum(1 for r in rows if r["A_solved"] and not r["B_solved"])   # A 解く・B 解けず（逆方向）
    div_exclusive = sum(1 for r in rows if r["B_solved_only_by_nondefault"])
    return {"n": n,
            "single_shot_rate": single_rate,
            "A_union_rate (同config反復)": a_rate,
            "B_union_rate (config散らし)": b_rate,
            "gain_diversity (B-A)": round(b_rate - a_rate, 3),
            "tasks_solved_only_by_B": only_b,
            "tasks_solved_only_by_A": only_a,
            "tasks_where_nondefault_framing_was_decisive": div_exclusive}


# --------------------------------------------------------------------------- #
# Arm D: rich-feedback loop + held-out 採点（Goodhart を測る）。
# gold を 可視(feedback)/held-out(真の採点) に分割。feedback は失敗した可視ケースの
# assert 行（入力==期待）を返す＝濃い。loop は*可視*が 1.0 で停止（モデルの目標）→ held-out を測る。
# 可視1.0 なのに held-out<1.0 ＝ Goodhart（可視をハードコード）。
# --------------------------------------------------------------------------- #
import re as _re
import subprocess as _sp
import tempfile as _tf


def _parse_gold(gold: str) -> dict:
    return dict(_re.findall(r"def (gold_\w+)\(\):\s*(.+)", gold))


def _split_gold(task: dict, frac_visible: float = 0.6):
    names = list(_parse_gold(task["gold"]).keys())
    nv = max(1, min(len(names) - 1, round(frac_visible * len(names))))
    return names[:nv], names[nv:]


def _run_subset(code: str, task: dict, fn_names: list, count_only: bool) -> dict:
    import resource
    if count_only:
        runner = (f"\nif True:\n _N={fn_names!r}; _g=dict(globals()); _p=_n=0\n"
                  " for _k in _N:\n  _n+=1\n  try:\n   _g[_k]()\n   _p+=1\n  except Exception: pass\n"
                  " print('CORRECT',_p,_n)\n")
    else:
        runner = (f"\nif True:\n _N={fn_names!r}; _g=dict(globals())\n"
                  " for _k in _N:\n  try:\n   _g[_k](); print('VPASS',_k)\n  except Exception: print('VFAIL',_k)\n")
    full = MX._PYTEST_SHIM + _first_block(code) + "\n" + task["gold"] + runner
    with _tf.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(full); path = f.name

    def _lim():
        resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    base = ["python3", path]
    cmd = (["unshare", "--user", "--net", "--pid", "--fork", "--mount-proc"] + base) if MX._UNSHARE else base
    try:
        proc = _sp.run(cmd, capture_output=True, text=True, timeout=16, preexec_fn=_lim)
        out = proc.stdout
    except Exception:
        out = ""
    finally:
        try: os.unlink(path)
        except OSError: pass
    if count_only:
        m = _re.search(r"CORRECT (\d+) (\d+)", out)
        p, n = (int(m.group(1)), int(m.group(2))) if m else (0, len(fn_names))
        return {"correctness": round(p / n, 3) if n else 0.0}
    failing = [k for k in fn_names if f"VPASS {k}" not in out]      # no VPASS line => failed/crashed
    npass = len(fn_names) - len(failing)
    return {"correctness": round(npass / len(fn_names), 3) if fn_names else 0.0, "failing": failing}


def _rich_repair_prompt(task: dict, prev_code: str, fail_lines: list) -> str:
    names = ", ".join(task["names"])
    cases = "\n".join(fail_lines)
    return (f"You are fixing a Python solution. Spec: {task['spec']}\nRequired functions: {names}.\n"
            f"Your previous code FAILS these specific cases (the line shows input and the REQUIRED result):\n"
            f"{cases}\nYour previous code:\n```python\n{prev_code}\n```\n"
            f"Fix the logic so ALL these cases pass AND general inputs stay correct. "
            f"Respond with ONLY a single corrected python code block — no tests, no prose.")


def _richloop_one(model: str, task: dict, n_iter: int, seed_base: int) -> dict:
    """1 試行の rich-loop。seed_base で試行間の seed 系列をずらす。"""
    vis, held = _split_gold(task)
    srcmap = _parse_gold(task["gold"])
    prev_code, iters = "", []
    for it in range(n_iter):
        if it == 0:
            out = _ollama(model, _prompt(task, _CONFIGS[_DEFAULT_CONFIG]), seed=seed_base)
        else:
            fail_lines = [srcmap[k] for k in iters[-1]["failing_vis"]]
            out = _ollama(model, _rich_repair_prompt(task, prev_code, fail_lines), seed=seed_base + it)
        prev_code = _first_block(out)
        v = _run_subset(out, task, vis, count_only=False)
        h = _run_subset(out, task, held, count_only=True)
        iters.append({"iter": it, "visible": v["correctness"], "heldout": h["correctness"],
                      "failing_vis": v["failing"]})
        if v["correctness"] >= 1.0:
            break
    final = iters[-1]
    vis_solved_at = next((a["iter"] for a in iters if a["visible"] >= 1.0), None)
    return {"vis_traj": [a["visible"] for a in iters], "held_traj": [a["heldout"] for a in iters],
            "vis_solved_at": vis_solved_at, "heldout_final": final["heldout"],
            "goodhart_gap": round(final["visible"] - final["heldout"], 3),
            # true Goodhart event = visible 達成したのに held-out 落ち
            "goodhart_event": vis_solved_at is not None and final["heldout"] < 1.0}


def run_richloop(models: list, tasks: list, n_iter: int, out_path: str, trials: int = 1) -> dict:
    rows, artifacts = [], []
    for model in models:
        for task in tasks:
            runs = [_richloop_one(model, task, n_iter, seed_base=t * 100) for t in range(trials)]
            held_rate = round(sum(1 for r in runs if r["heldout_final"] >= 1.0) / trials, 3)
            vis_rate = round(sum(1 for r in runs if r["vis_solved_at"] is not None) / trials, 3)
            gh_events = sum(1 for r in runs if r["goodhart_event"])
            rows.append({"model": model, "task": task["id"], "trials": trials,
                         "heldout_solve_rate": held_rate, "visible_solve_rate": vis_rate,
                         "goodhart_events": gh_events,
                         "mean_goodhart_gap": round(sum(r["goodhart_gap"] for r in runs) / trials, 3),
                         "held_finals": [r["heldout_final"] for r in runs]})
            artifacts.append({"model": model, "task": task["id"], "runs": runs})
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"rows": rows, "n_iter": n_iter, "trials": trials}, f, ensure_ascii=False, indent=2)
            r = rows[-1]
            print(f"  {model:<10} {r['task']:<14} held_rate={held_rate} (of {trials}) "
                  f"vis_rate={vis_rate} goodhart_events={gh_events} held_finals={r['held_finals']}")
    with open(out_path.replace("_results", "_artifacts"), "w", encoding="utf-8") as f:
        json.dump(artifacts, f, ensure_ascii=False, indent=2)
    n = len(rows)
    return {"rows": rows,
            "mean_heldout_solve_rate": round(sum(r["heldout_solve_rate"] for r in rows) / n, 3) if n else 0,
            "total_goodhart_events": sum(r["goodhart_events"] for r in rows),
            "total_cells": n * trials}


def main() -> int:
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    models = os.environ.get("CM_MODELS", "qwen2.5-coder:7b,gemma4:latest").split(",")
    all_tasks = MX._HARD_TASKS + MX._LADDER_TASKS + MX.EXT_TASKS
    pick = os.environ.get("CM_TASKS")
    tasks = [t for t in all_tasks if t["id"] in pick.split(",")] if pick else all_tasks

    if "--loop" in sys.argv:                          # Arm C: feedback loop (別出力・blind と非衝突)
        n_iter = int(os.environ.get("CM_ITERS", K))   # matched budget = K
        out = os.path.join(here, "config_mesh_loop_results.json")
        print(f"config_mesh --loop: models={models} tasks={[t['id'] for t in tasks]} n_iter={n_iter}")
        res = run_loop(models, tasks, n_iter, out)
        print(f"\n=== LOOP SUMMARY ===\n  loop_solve_rate (C_best>=1.0): {res['loop_solve_rate']}")
        print(f"wrote {out}")
        return 0

    if "--richloop" in sys.argv:                       # Arm D: rich feedback + held-out (Goodhart 計測)
        n_iter = int(os.environ.get("CM_ITERS", 6))
        trials = int(os.environ.get("CM_TRIALS", 1))
        tag = os.environ.get("CM_TAG", "")
        out = os.path.join(here, f"config_mesh_rich{('_' + tag) if tag else ''}_results.json")
        print(f"config_mesh --richloop: models={models} tasks={[t['id'] for t in tasks]} "
              f"n_iter={n_iter} trials={trials}")
        res = run_richloop(models, tasks, n_iter, out, trials)
        print(f"\n=== RICH-LOOP SUMMARY (trials={trials}) ===")
        print(f"  mean_heldout_solve_rate: {res['mean_heldout_solve_rate']}")
        print(f"  total_goodhart_events:   {res['total_goodhart_events']} / {res['total_cells']} cells")
        print(f"wrote {out}")
        return 0

    out = os.path.join(here, "config_mesh_results.json")
    print(f"config_mesh: models={models} tasks={[t['id'] for t in tasks]} K={K} (matched-budget A/B)")
    res = run(models, tasks, out)
    print("\n=== SUMMARY ===")
    for k, v in res["summary"].items():
        print(f"  {k}: {v}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
