"""mmlu_pro_bench の決定的部分（採点・抽出・escalation ルーティング）を mock で検品。
ネットワーク(fetch)と real LLM は対象外（外部依存）。

**この 10 件は 2026-07-15 まで正典コマンドで一度も走っていなかった。** 素の pytest 関数
（module 直下の `def test_*`）で書かれており、`unittest` の loader は TestCase 派生しか
拾わないので、README が正典として案内する `python3 -m unittest discover -s tests -t .` では
**0 件実行**（pytest なら 10 件）。「全 green」がこの 10 件を含まないまま主張されていた。
TestCase に載せて実際に床として効かせる（アサーションは一字も変えていない・構造だけの変換）。
再発は tests/test_suite_integrity.py が機械で止める。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import experiments.mmlu_pro_bench as MP  # noqa: E402


def _task(answer="C", n=4):
    return {"id": "t1", "question": "Q?", "options": [f"opt{i}" for i in range(n)],
            "answer": answer, "category": "physics"}


class MmluProBenchTests(unittest.TestCase):

    def test_extract_choice_plain(self):
        assert MP.extract_choice("C", 4) == "C"

    def test_extract_choice_prose_and_parens(self):
        assert MP.extract_choice("I think the answer is C.", 4) == "C"
        assert MP.extract_choice("Answer: (D)", 4) == "D"

    def test_extract_choice_last_wins(self):
        assert MP.extract_choice("Between A and B... actually the answer is D", 4) == "D"

    def test_extract_choice_out_of_range_or_empty_is_none(self):
        assert MP.extract_choice("J", 4) is None      # only A-D valid for a 4-option task
        assert MP.extract_choice("", 4) is None
        assert MP.extract_choice(None, 4) is None

    def test_grade_letter_match(self):
        t = _task("C")
        assert MP.grade("C", t) == 1.0
        assert MP.grade("A", t) == 0.0

    def test_make_prompt_enumerates_letters(self):
        p = MP.make_prompt(_task("C", 4))
        assert "A. opt0" in p and "D. opt3" in p and "Answer:" in p

    def test_run_baselines_p(self):
        tasks = [_task("C"), _task("A")]

        def call(model, prompt):            # strong tiers answer 'C', weak tiers 'B'
            return "C" if model in ("sonnet", "opus") else "B"

        base = MP.run_baselines(tasks, MP.TIERS, call)
        assert base["opus"]["p"] == 0.5     # solves the 'C' task, misses the 'A' task
        assert base["gemma"]["p"] == 0.0
        assert base["gemma"]["cost"] == 0.2

    def test_run_escalation_routes_to_capable_tier(self):
        tasks = [_task("C")]

        def call(model, prompt):            # gemma/haiku wrong, sonnet right -> stop before opus
            return "C" if model in ("sonnet", "opus") else "A"

        esc = MP.run_escalation(tasks, MP.TIERS, call)
        row = esc["rows"][0]
        assert row["solved_by"] == "sonnet"
        assert row["cost"] == 0.2 + 1.0 + 3.0
        assert esc["solve_rate"] == 1.0
        assert esc["escalated_rate"] == 1.0

    def test_run_escalation_cheap_tier_stops_early(self):
        tasks = [_task("C")]

        def call(model, prompt):            # gemma already correct -> no escalation
            return "C"

        esc = MP.run_escalation(tasks, MP.TIERS, call)
        assert esc["rows"][0]["solved_by"] == "gemma"
        assert esc["rows"][0]["cost"] == 0.2
        assert esc["escalated_rate"] == 0.0

    def test_run_escalation_unsolved_when_all_fail(self):
        tasks = [_task("C")]

        def call(model, prompt):            # nobody answers C
            return "A"

        esc = MP.run_escalation(tasks, MP.TIERS, call)
        assert esc["rows"][0]["solved_by"] is None
        assert esc["solve_rate"] == 0.0


if __name__ == "__main__":
    unittest.main()
