"""mmlu_pro_bench — 未飽和の選択式QAで escalation を測る。市場系がコード生成(古典アルゴ)で
gemma/haiku を p≈1.0 飽和させた穴を埋める土俵。docs/industry-benchmarks.md §6 の処方。

MMLU-Pro (TIGER-Lab/MMLU-Pro, public) を datasets-server で取得し、
gemma->haiku->sonnet->opus の verification-routed escalation に載せる。
grade = 答えレター一致（外部 gold・自己申告でない）。real のモデル呼び出しは
market_external._route を再利用（gemma->ollama, claude->runner=サブスク枠）。

run:
  python3 -m experiments.mmlu_pro_bench --category physics --n 20         # fetch のみ(offline)
  python3 -m experiments.mmlu_pro_bench --real --category physics --n 20  # gemma..opus で測定
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

DATASET = "TIGER-Lab/MMLU-Pro"
TIERS = (("gemma", "gemma4:e2b", 0.2), ("haiku", "haiku", 1.0),
         ("sonnet", "sonnet", 3.0), ("opus", "opus", 15.0))
HARD_CATEGORIES = ("physics", "chemistry", "math", "engineering")
_LETTERS = "ABCDEFGHIJ"


def fetch(category: str = "physics", n: int = 20, offset: int = 0, split: str = "test") -> list:
    """MMLU-Pro rows for one category via the datasets-server filter API (public, no token)."""
    where = urllib.parse.quote(f"\"category\"='{category}'")
    url = (f"https://datasets-server.huggingface.co/filter?dataset={DATASET}"
           f"&config=default&split={split}&where={where}&offset={offset}&length={n}")
    req = urllib.request.Request(url, headers={"User-Agent": "soshiki-genron"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    out = []
    for row in d["rows"]:
        r = row["row"]
        out.append({"id": f"mmlu_{r['question_id']}", "question": r["question"],
                    "options": list(r["options"]), "answer": r["answer"],
                    "category": r["category"]})
    return out


def make_prompt(task: dict) -> str:
    # CoT-allowed: forbidding reasoning ("ONLY the single letter") cratered opus on math
    # (0.25 vs haiku 0.80) and manufactured a fake decorrelation. Letting the model think
    # then emit 'Answer: <letter>' makes the measurement fair; extract_choice grabs the tail.
    opts = "\n".join(f"{_LETTERS[i]}. {o}" for i, o in enumerate(task["options"]))
    return (f"{task['question']}\n\n{opts}\n\n"
            "Work through it step by step, then end with a line exactly: 'Answer: <letter>'.")


def extract_choice(text: str, n_opts: int) -> str | None:
    """Last standalone in-range letter wins — tolerant of 'Answer: C', '(C)', 'C.', prose."""
    valid = set(_LETTERS[:n_opts])
    cands = re.findall(r"\b([A-J])\b", (text or "").upper())
    for c in reversed(cands):
        if c in valid:
            return c
    return None


def grade(text: str, task: dict) -> float:
    """External gold: 1.0 iff the extracted letter equals the dataset answer."""
    return 1.0 if extract_choice(text, len(task["options"])) == task["answer"] else 0.0


def gen_answer(model: str, task: dict, call) -> str:
    return call(model, make_prompt(task))


def run_baselines(tasks: list, tiers, call) -> dict:
    """Per-model solve rate p (the quantity market.py's p*=w/s needs)."""
    out = {}
    for name, model, w in tiers:
        cs = [grade(gen_answer(model, t, call), t) for t in tasks]
        out[name] = {"p": round(sum(cs) / len(cs), 3), "cost": w}
    return out


def run_escalation(tasks: list, tiers, call) -> dict:
    """Verification-routed escalation: cheap->expensive, stop when external grade passes."""
    rows = []
    for t in tasks:
        cost, ladder, solved_by = 0.0, [], None
        for name, model, w in tiers:
            s = grade(gen_answer(model, t, call), t)
            cost += w
            ladder.append([name, s])
            if s >= 1.0:
                solved_by = name
                break
        rows.append({"id": t["id"], "category": t["category"], "cost": round(cost, 3),
                     "solved_by": solved_by, "ladder": ladder})
    n = len(rows)
    return {"rows": rows, "avg_cost": round(sum(r["cost"] for r in rows) / n, 3),
            "solve_rate": round(sum(1 for r in rows if r["solved_by"]) / n, 3),
            "escalated_rate": round(sum(1 for r in rows if len(r["ladder"]) > 1) / n, 3)}


def main(argv=None) -> int:
    import os
    import sys
    av = argv if argv is not None else sys.argv[1:]

    def opt(flag, default):
        return av[av.index(flag) + 1] if flag in av else default

    category = opt("--category", "physics")
    n = int(opt("--n", "20"))
    tasks = fetch(category, n)
    if "--real" not in av:
        print(f"fetched {len(tasks)} '{category}' tasks (offline). Add --real to run models.")
        for t in tasks[:3]:
            print(f"  {t['id']} ({len(t['options'])} opts) gold={t['answer']}: {t['question'][:70]}")
        return 0
    from experiments.market_external import _route as call
    base = run_baselines(tasks, TIERS, call)
    esc = run_escalation(tasks, TIERS, call)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "mmlu_pro_results.json"), "w", encoding="utf-8") as f:
        json.dump({"category": category, "n": len(tasks), "baselines": base, "escalation": esc},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"MMLU-Pro [{category}] n={len(tasks)} — per-model solve rate p:")
    for name, _, _ in TIERS:
        print(f"  {name:<7} p={base[name]['p']:.3f}  (cost {base[name]['cost']})")
    print(f"\nescalation: avg_cost={esc['avg_cost']}  solve_rate={esc['solve_rate']}  "
          f"escalated_rate={esc['escalated_rate']}")
    print("wrote mmlu_pro_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
