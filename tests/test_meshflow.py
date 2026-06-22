"""Tests for meshflow — the prescribed org chart (PAPER S6.5) as a runnable executor."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.meshflow import NEEDS_HUMAN, Task, Tier, execute, _toposort  # noqa: E402


def _tiers():
    # cheap solves diff<=0, mid <=1, strong <=2
    def agent_of(cap):
        return lambda t, bb: (f"SOLN:{t.id}" if t.spec_diff <= cap else f"PARTIAL@{cap}")
    return [Tier("cheap", 0.2, agent_of(0)), Tier("mid", 1.0, agent_of(1)), Tier("strong", 5.0, agent_of(2))]


def _task(tid, diff, **kw):
    t = Task(tid, kw.pop("spec", "x"), lambda art, bb: 1.0 if art == f"SOLN:{tid}" else 0.0, **kw)
    object.__setattr__(t, "spec_diff", diff)     # attach difficulty for the mock agents
    return t


class MeshflowTests(unittest.TestCase):
    def test_cheap_tier_solves_flat_no_escalation(self):
        r = execute([_task("e", 0)], _tiers())
        row = r["rows"][0]
        self.assertEqual(row["resolved_by"], "cheap")
        self.assertEqual(row["cost"], 0.2)        # paid only the cheapest tier

    def test_verification_routed_escalation(self):
        r = execute([_task("m", 1)], _tiers())
        row = r["rows"][0]
        self.assertEqual(row["resolved_by"], "mid")
        self.assertEqual(row["cost"], 1.2)        # cheap(0.2) failed verify -> escalate to mid(1.0)

    def test_external_verification_gates(self):
        # a tier's output is only accepted when verify hits 1.0 (not self-reported)
        r = execute([_task("h", 2)], _tiers())
        self.assertEqual(r["rows"][0]["resolved_by"], "strong")
        self.assertEqual([a["score"] for a in r["rows"][0]["attempts"]], [0.0, 0.0, 1.0])

    def test_mesh_combines_at_the_edge(self):
        # no single tier solves; each contributes a distinct line; the mesh union verifies
        def agent_part(part):
            return lambda t, bb: part
        tiers = [Tier("a", 1, agent_part("A")), Tier("b", 1, agent_part("B")), Tier("c", 1, agent_part("C"))]
        edge = Task("edge", "x", lambda art, bb: 1.0 if art == "A\nB\nC" else 0.0)
        r = execute([edge], tiers)
        self.assertEqual(r["rows"][0]["resolved_by"], "mesh")
        self.assertEqual(r["rows"][0]["score"], 1.0)

    def test_mesh_off_does_not_combine(self):
        def agent_part(part):
            return lambda t, bb: part
        tiers = [Tier("a", 1, agent_part("A")), Tier("b", 1, agent_part("B"))]
        edge = Task("edge", "x", lambda art, bb: 1.0 if art == "A\nB" else 0.0, stakes=0.9)
        r = execute([edge], tiers, mesh=False)
        self.assertTrue(r["rows"][0]["human"])    # no mesh -> unresolved -> human gate (high stakes)

    def test_human_membrane_on_high_stakes_unresolved(self):
        r = execute([_task("crit", 99, stakes=0.9)], _tiers())
        self.assertTrue(r["rows"][0]["human"])
        self.assertEqual(r["blackboard"]["crit"], NEEDS_HUMAN)

    def test_low_stakes_unresolved_ships_best_effort(self):
        r = execute([_task("lc", 99, stakes=0.1)], _tiers())
        self.assertFalse(r["rows"][0]["human"])   # low stakes -> ship best-effort, no human gate
        self.assertEqual(r["rows"][0]["resolved_by"], "best-effort")

    def test_dataflow_deps_topologically_ordered(self):
        order = [t.id for t in _toposort([_task("b", 0, deps=("a",)), _task("a", 0)])]
        self.assertEqual(order, ["a", "b"])       # dependency runs before dependent

    def test_dependency_cycle_raises(self):
        with self.assertRaises(ValueError):
            _toposort([_task("a", 0, deps=("b",)), _task("b", 0, deps=("a",))])

    def test_artifact_flows_onto_shared_blackboard(self):
        r = execute([_task("a", 0), _task("b", 0, deps=("a",))], _tiers())
        self.assertEqual(r["blackboard"]["a"], "SOLN:a")   # upstream artifact available downstream

    def test_metrics_and_determinism(self):
        tasks = [_task("e", 0), _task("m", 1), _task("crit", 99, stakes=0.9)]
        r = execute(tasks, _tiers())
        self.assertAlmostEqual(r["verified_rate"], 2 / 3, places=3)
        self.assertAlmostEqual(r["human_gate_rate"], 1 / 3, places=3)
        self.assertEqual(execute(tasks, _tiers()), r)      # deterministic


if __name__ == "__main__":
    unittest.main()
