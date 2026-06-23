"""meshflow — PAPER §6.5「採用すべき組織図」を*動く*実行系に落としたもの。

処方された組織図を operational にする最小ランタイム（決定的・stdlib のみ・エージェントは差し替え可）:

  ① 薄い人間統治膜      … stakes が高く未解決なら human gate へ（黙って ship しない）
  ② 平らなデータフロー   … タスクは依存 DAG・共有黒板（blackboard）上を流れる・管理者エージェント無し
  ③ 検証ルーティング・エスカレーション … 安いティアで試し、外部検証 NG だけ上位へ昇格
  ④ 補完能力 mesh        … 全ティアが単独で通らない「縁」でだけ、複数ティアの試行を結合
  ⑤ 外部検証が背骨        … 合否は verify(artifact)->score（自己申告でなく外部チェック）

人間組織（チーム・役割・管理者・階層）は採らない。配分は能力ティア×外部検証、組織は flat な dataflow。
エージェントは (spec, blackboard)->artifact の関数（mock で決定的・LLM 差し替えは seam のみ）。
run: python3 -m experiments.meshflow  （デモ＋メトリクス）
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

NEEDS_HUMAN = "<<NEEDS_HUMAN>>"


@dataclass(frozen=True)
class Tier:
    name: str
    cost: float                                  # tier-weighted cost (price proxy)
    agent: "callable"                            # (task, blackboard) -> artifact (str)


@dataclass(frozen=True)
class Task:
    id: str
    spec: str
    verify: "callable"                           # (artifact, blackboard) -> score in [0,1]; 1.0 = passes
    deps: tuple = ()                             # upstream task ids whose artifacts this needs
    stakes: float = 0.0                          # 0..1; high stakes -> human gate when unresolved


def _toposort(tasks: list) -> list:
    by_id = {t.id: t for t in tasks}
    seen, order = set(), []

    def visit(tid, stack):
        if tid in seen:
            return
        if tid in stack:
            raise ValueError(f"dependency cycle at {tid}")
        for d in by_id[tid].deps:
            visit(d, stack | {tid})
        seen.add(tid)
        order.append(by_id[tid])

    for t in tasks:
        visit(t.id, set())
    return order


def _resolve(task: Task, tiers: list, bb: dict, mesh: bool, stakes_threshold: float) -> dict:
    """Verification-routed escalation -> mesh at the edge -> human membrane. External verify gates all."""
    attempts, cost = [], 0.0
    for tier in tiers:                           # cheap -> expensive
        art = tier.agent(task, bb)
        cost += tier.cost
        score = task.verify(art, bb)
        attempts.append({"tier": tier.name, "score": round(score, 3)})
        if score >= 1.0:                         # external verification satisfied -> stop escalating
            return {"artifact": art, "cost": round(cost, 3), "resolved_by": tier.name,
                    "score": 1.0, "attempts": attempts, "human": False}
        bb[f"_attempt:{task.id}:{tier.name}"] = art   # keep partial drafts for the mesh

    # ④ edge: no single tier passed. mesh = combine all tier attempts (complementary capability).
    if mesh:
        drafts = [bb[f"_attempt:{task.id}:{t.name}"] for t in tiers]
        merged = _mesh_combine(task, drafts, bb)
        cost += _MESH_COST
        ms = task.verify(merged, bb)
        attempts.append({"tier": "mesh", "score": round(ms, 3)})
        if ms >= 1.0:
            return {"artifact": merged, "cost": round(cost, 3), "resolved_by": "mesh",
                    "score": 1.0, "attempts": attempts, "human": False}

    # ① membrane: still unresolved. high stakes -> human gate; else ship best-effort (flagged).
    best = max(attempts, key=lambda a: a["score"])
    if task.stakes >= stakes_threshold:
        return {"artifact": NEEDS_HUMAN, "cost": round(cost, 3), "resolved_by": None,
                "score": best["score"], "attempts": attempts, "human": True}
    return {"artifact": bb.get(f"_attempt:{task.id}:{tiers[-1].name}"), "cost": round(cost, 3),
            "resolved_by": "best-effort", "score": best["score"], "attempts": attempts, "human": False}


_MESH_COST = 0.5


def _mesh_combine(task: Task, drafts: list, bb: dict) -> str:
    """Deterministic mesh: union of distinct draft lines (a stand-in for cross-checking diverse agents).
    Real deployments swap this for a synthesizer agent; the value comes from COMPLEMENTARY errors."""
    seen, out = set(), []
    for d in drafts:
        for ln in (d or "").splitlines():
            k = ln.strip()
            if k and k not in seen:
                seen.add(k)
                out.append(ln)
    return "\n".join(out)


def execute(tasks: list, tiers: list, mesh: bool = True, stakes_threshold: float = 0.7) -> dict:
    """Run the flat verification-routed dataflow. tiers cheap->expensive. Returns artifacts + metrics."""
    bb: dict = {}
    rows = []
    for task in _toposort(tasks):
        r = _resolve(task, tiers, bb, mesh, stakes_threshold)
        bb[task.id] = r["artifact"]              # artifact flows onto the shared blackboard
        rows.append({"task": task.id, **{k: r[k] for k in ("resolved_by", "cost", "score", "human", "attempts")}})
    total_cost = round(sum(r["cost"] for r in rows), 3)
    verified = sum(1 for r in rows if r["score"] >= 1.0)
    return {"rows": rows, "total_cost": total_cost,
            "verified_rate": round(verified / len(rows), 3),
            "human_gate_rate": round(sum(1 for r in rows if r["human"]) / len(rows), 3),
            "blackboard": {k: v for k, v in bb.items() if not k.startswith("_attempt:")}}


# --------------------------------------------------------------------------- #
# demo: mock tiers of increasing capability + external verifiers
# --------------------------------------------------------------------------- #
def _demo():
    # A mock 'agent' of capability c solves a task iff its difficulty <= c. Cheap<strong.
    def agent_of(capability):
        def agent(task, bb):
            diff = _DIFF[task.id]
            if isinstance(diff, tuple):          # 'edge' task: each tier only gets PART right (mesh territory)
                got = diff[capability] if capability < len(diff) else diff[-1]
                return got
            return f"SOLN:{task.id}" if diff <= capability else f"PARTIAL:{task.id}@{capability}"
        return agent

    tiers = [Tier("cheap", 0.2, agent_of(0)), Tier("mid", 1.0, agent_of(1)), Tier("strong", 5.0, agent_of(2))]

    def needs(answer):
        return lambda art, bb: 1.0 if art == answer else (0.5 if art and "PARTIAL" not in art else 0.0)

    tasks = [
        Task("easy", "trivial", needs("SOLN:easy")),                                  # cheap solves
        Task("mid1", "moderate", needs("SOLN:mid1"), deps=("easy",)),                 # escalate to mid
        Task("hard", "hard", needs("SOLN:hard")),                                     # escalate to strong
        Task("edge", "no single tier solves -> mesh", needs("A\nB\nC")),              # mesh combines parts
        Task("crit", "unsolvable + high stakes", needs("SOLN:crit"), stakes=0.9),     # human gate
    ]
    return tasks, tiers


_DIFF = {"easy": 0, "mid1": 1, "hard": 2, "edge": ("A", "B", "C"), "crit": 99}
_DIFF["edge"] = ("A", "B", "C")   # cheap->"A", mid->"B", strong->"C"; union "A\nB\nC" verifies


# --------------------------------------------------------------------------- #
# real LLM seam: tiers = gemma<haiku<sonnet<opus, external verify = sandbox gold.
# The same executor, now driven by actual models. Escalation fires when a cheaper
# model fails the external check. (mesh on code = a synthesizer agent, left as a seam;
# here the frontier solves everything so escalation suffices -> consistent with PAPER S5.)
# --------------------------------------------------------------------------- #
def _llm_agent(model, cache, cache_path):
    import json
    import experiments.market_external as MX

    def agent(task, bb):
        key = f"{task.id}|{model}"
        if not (cache.get(key) and "def " in cache[key]):
            cache[key] = MX.gen_impl(model, task._mx)
            if cache_path:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
        return cache[key]

    return agent


def llm_demo(cache, cache_path, chosen=None):
    import experiments.market_external as MX
    by_id = {t["id"]: t for t in MX._EASY_TASKS + MX.EXT_TASKS + MX._HARD_TASKS + MX._LADDER_TASKS}
    if chosen is None:
        chosen = ["clamp", "roman", "atoms", "calc"]     # gemma solves clamp; fails roman/atoms/calc -> escalate
    tiers = [Tier(m, w, _llm_agent(mm, cache, cache_path))
             for m, mm, w in (("gemma", "gemma4:e2b", 0.2), ("haiku", "haiku", 1.0),
                              ("sonnet", "sonnet", 3.0), ("opus", "opus", 15.0))]
    tasks = []
    for tid in chosen:
        mx = by_id[tid]
        t = Task(tid, mx["spec"], lambda art, bb, _mx=mx: MX.grade(art, _mx)["correctness"] or 0.0)
        object.__setattr__(t, "_mx", mx)
        tasks.append(t)
    return tasks, tiers


def main(argv=None) -> int:
    import json
    import os
    import sys
    if "--real" in (argv if argv is not None else sys.argv[1:]):
        import experiments.market_external as MX
        MX._CALL = MX._route                          # real LLM routing (gemma->ollama, claude->runner)
        out_dir = os.path.dirname(os.path.abspath(__file__))
        cp = os.path.join(out_dir, "meshflow_real_artifacts.json")
        cache = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
        _av = argv if argv is not None else sys.argv[1:]
        _chosen = _av[_av.index("--tasks") + 1].split(",") if "--tasks" in _av else None
        tasks, tiers = llm_demo(cache, cp, _chosen)
        r = execute(tasks, tiers, mesh=False)         # mesh on code = synthesizer agent (seam); escalation here
        with open(os.path.join(out_dir, "meshflow_real.json"), "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in r.items() if k != "blackboard"}, f, ensure_ascii=False, indent=2, sort_keys=True)
        print("PRESCRIBED ORG CHART on REAL models (external verify = sandbox gold):")
        for row in r["rows"]:
            ladder = " -> ".join(f"{a['tier']}:{a['score']}" for a in row["attempts"])
            print(f"  {row['task']:<8} {ladder}  => resolved_by={row['resolved_by']} cost={row['cost']}")
        print(f"\ntotal_cost={r['total_cost']}  verified_rate={r['verified_rate']}  human_gate_rate={r['human_gate_rate']}")
        print("wrote meshflow_real.json")
        return 0
    tasks, tiers = _demo()
    r = execute(tasks, tiers)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "meshflow_demo.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("prescribed org chart, running (mock agents):")
    for row in r["rows"]:
        print(f"  {row['task']:<6} resolved_by={str(row['resolved_by']):<12} cost={row['cost']:<5} "
              f"score={row['score']} human={row['human']}")
    print(f"\ntotal_cost={r['total_cost']}  verified_rate={r['verified_rate']}  "
          f"human_gate_rate={r['human_gate_rate']}")
    print("wrote meshflow_demo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
