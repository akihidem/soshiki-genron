"""Tests for model/gap.py ── 境界 p*=w/s の判定分解能の床。

床の主張は2つで、どちらも**機械で検証できる形**にしてある:

  ① gated 手続きの第一種過誤 ≤ α（H0＝真に境界上 で「支配」と誤宣言する確率）
  ② naive 手続き（現行の `p̂ > w/s`）の第一種過誤は α を**大きく超える**（＝バグは実在する）

①②は `verdict()` を**通して**全観測を列挙し、`fractions.Fraction` の厳密有理演算で
帰無確率を積み上げて確かめる。gap.py の log 空間実装とは*別経路*なので、
`_log_pmf_vector` にバグがあれば同語反復でなく本当に落ちる（test_noise.py の
`_brute_force_joint` と同じ作法）。
"""

import math
import os
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import market  # noqa: E402
from model.gap import (  # noqa: E402
    DOMINATES, NOT_DOMINATES, UNDECIDED,
    audit, blind_band, cdf, crit_lower, crit_upper, load_map,
    min_n_for_margin, min_n_for_refutation, run, sf, sweep_p, type_i_error, verdict,
)

ALPHA = 0.05
# 実測地図の3ティア（w=0.2 / s=1,3,15）
RATIOS = (Fraction(1, 5), Fraction(2, 30), Fraction(2, 150))


def _exact_pmf(k: int, n: int, p: Fraction) -> Fraction:
    """厳密有理数の二項 pmf ── gap.py の log 空間実装と**独立**な経路。"""
    return Fraction(math.comb(n, k)) * p ** k * (1 - p) ** (n - k)


def _exact_tail_ge(k: int, n: int, p: Fraction) -> Fraction:
    return sum((_exact_pmf(i, n, p) for i in range(k, n + 1)), Fraction(0))


class ExactBinomialTests(unittest.TestCase):
    """log 空間の厳密尾部が、有理数の厳密尾部と一致するか。"""

    def test_sf_matches_exact_rational(self):
        for n in (1, 6, 12, 25):
            for p in RATIOS:
                for k in range(0, n + 2):
                    with self.subTest(n=n, p=str(p), k=k):
                        self.assertAlmostEqual(sf(k, n, float(p)),
                                               float(_exact_tail_ge(k, n, p)), places=12)

    def test_pmf_sums_to_one_and_cdf_complements_sf(self):
        for n in (1, 6, 30):
            for p in (0.0133, 0.0667, 0.2, 0.5, 0.9):
                with self.subTest(n=n, p=p):
                    self.assertAlmostEqual(sf(0, n, p), 1.0, places=12)
                    for k in range(0, n + 1):
                        # P(X>=k) + P(X<=k-1) == 1
                        self.assertAlmostEqual(sf(k, n, p) + cdf(k - 1, n, p), 1.0, places=12)

    def test_no_underflow_at_large_n(self):
        """n=400・p=0.0133 でも (1-p)^n が 0 に潰れて全滅しない（log 空間の要点）。"""
        self.assertAlmostEqual(sf(0, 400, 0.0133), 1.0, places=12)
        self.assertGreater(sf(1, 400, 0.0133), 0.99)
        self.assertIsNotNone(crit_upper(400, 0.0133, ALPHA))


class CriticalValueTests(unittest.TestCase):

    def test_crit_upper_is_minimal(self):
        """臨界値は「条件を満たす*最小*の k」── 一つ下の k は必ず α を破る。"""
        for n in (6, 14, 50):
            for p in (0.0133, 0.0667, 0.2):
                with self.subTest(n=n, p=p):
                    up = crit_upper(n, p, ALPHA)
                    self.assertIsNotNone(up)
                    k = int(round(up * n))
                    self.assertLessEqual(sf(k, n, p), ALPHA)          # 満たす
                    self.assertGreater(sf(k - 1, n, p), ALPHA)        # 一つ下は満たさない（最小性）

    def test_blind_band_is_strictly_positive(self):
        """盲帯は必ず在る: 支配を宣言できる最小 p̂ は w/s より真に大きい。"""
        for n in (6, 14, 50, 200, 400):
            for p in (0.0133, 0.0667, 0.2):
                with self.subTest(n=n, p=p):
                    b = blind_band(n, p, ALPHA)
                    self.assertGreater(b["crit_upper"], b["p_star"])
                    self.assertGreater(b["blind_half_width"], 0.0)

    def test_homogeneous_ratio_can_never_prove_dominance(self):
        """w=s（均質）は p>1 を要求 ⟹ どんな n でも支配を宣言できない（market.py の regime ① と一致）。"""
        for n in (6, 100, 400):
            self.assertIsNone(crit_upper(n, 1.0, ALPHA))
            self.assertEqual(verdict(1.0, n, 1.0, ALPHA), UNDECIDED)

    def test_gap_boundary_agrees_with_market_theorem(self):
        """境界そのものは market.py の p* = w/s と同一（床は定理を書き換えていない）。"""
        for _name, s in (("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0)):
            ratio = 0.2 / s
            self.assertAlmostEqual(blind_band(6, ratio, ALPHA)["p_star"],
                                   market.p_star(0.2, s), places=4)


class RefutationBranchTests(unittest.TestCase):
    """『非支配』を言える枝が、いつ存在するか。ここが本ファイルの主張の核。"""

    def test_refutation_is_impossible_at_the_measured_n(self):
        """n=6・w/s=0.2 では p̂=0/6 ですら「非支配」を証明できない（下側の枝が空）。"""
        self.assertIsNone(crit_lower(6, 0.2, ALPHA))
        self.assertGreater(cdf(0, 6, 0.2), ALPHA)                 # P(X=0)=0.2621 > α
        self.assertEqual(verdict(0.0, 6, 0.2, ALPHA), UNDECIDED)  # 全問不正解でも「非支配」と言えない
        self.assertFalse(blind_band(6, 0.2, ALPHA)["refutable"])

    def test_min_n_for_refutation_is_tight(self):
        """n≥14 で初めて反証可能になる。境目の両側を厳密に固定する。"""
        n_req = min_n_for_refutation(0.2, ALPHA)
        self.assertEqual(n_req, 14)
        self.assertGreater(cdf(0, n_req - 1, 0.2), ALPHA)      # n=13 ではまだ不可
        self.assertLessEqual(cdf(0, n_req, 0.2), ALPHA)        # n=14 で可
        self.assertIsNone(crit_lower(n_req - 1, 0.2, ALPHA))
        self.assertIsNotNone(crit_lower(n_req, 0.2, ALPHA))


class TypeIErrorTests(unittest.TestCase):
    """H0（真に境界上・市場の利得ゼロ）の下で誤って「支配」と宣言する確率。

    `verdict()` を通して全観測を列挙し、厳密有理数で帰無確率を積む（gap.py の内部実装に依存しない）。
    """

    def _null_prob_of(self, target: str, n: int, p: Fraction) -> float:
        tot = Fraction(0)
        for x in range(0, n + 1):                     # H0 の下で観測しうる X=0..n
            if verdict(x / n, n, float(p), ALPHA) == target:
                tot += _exact_pmf(x, n, p)

        return float(tot)

    def test_gated_procedure_respects_alpha_on_both_branches(self):
        """**床の核心**: 支配/非支配のどちらの宣言も、帰無の下で確率 ≤ α。"""
        for n in (6, 12, 14, 24, 50, 100):
            for p in RATIOS:
                with self.subTest(n=n, w_over_s=str(p)):
                    self.assertLessEqual(self._null_prob_of(DOMINATES, n, p), ALPHA + 1e-12)
                    self.assertLessEqual(self._null_prob_of(NOT_DOMINATES, n, p), ALPHA + 1e-12)

    def test_naive_procedure_blows_through_alpha(self):
        """現行の `p̂ > w/s` は、真に利得ゼロのモデルを n=6 で 34% も「支配」と刻む（バグは実在）。"""
        tot = Fraction(0)
        for x in range(0, 7):
            if Fraction(x, 6) > Fraction(1, 5):       # 現行手続き: p̂ > w/s
                tot += _exact_pmf(x, 6, Fraction(1, 5))
        self.assertAlmostEqual(float(tot), 0.3446, places=4)
        self.assertGreater(float(tot), 6 * ALPHA)     # α の6倍超

    def test_type_i_error_report_matches_the_enumeration(self):
        rep = type_i_error(6, 0.2, ALPHA)
        self.assertAlmostEqual(rep["naive"], 0.3446, places=4)
        # 表示値は 4 桁丸め（0.01696 → 0.017）。列挙値との一致はその精度で見る。
        self.assertAlmostEqual(rep["gated"], self._null_prob_of(DOMINATES, 6, Fraction(1, 5)), places=4)

    def test_alpha_compliance_is_decided_before_rounding(self):
        """丸めた表示値ではなく**丸める前**の値で α 準拠を判定しているか。

        表示だけ見て準拠を主張すると、0.05004 が round で 0.05 に化けて違反を隠す。
        """
        for n in (6, 12, 14, 24, 50, 100):
            for p in RATIOS:
                with self.subTest(n=n, w_over_s=str(p)):
                    rep = type_i_error(n, float(p), ALPHA)
                    self.assertTrue(rep["gated_within_alpha"])
                    # 準拠フラグは列挙した真の帰無確率と一致していなければならない
                    self.assertEqual(rep["gated_within_alpha"],
                                     self._null_prob_of(DOMINATES, n, p) <= ALPHA + 1e-12)


class VerdictTests(unittest.TestCase):

    def test_verdict_is_monotone_in_p_hat(self):
        """p̂ が上がって判定が*弱く*なることはない（NOT < UNDECIDED < DOMINATES）。"""
        order = {NOT_DOMINATES: 0, UNDECIDED: 1, DOMINATES: 2}
        for n in (6, 24, 100):
            for p in (0.0133, 0.0667, 0.2):
                with self.subTest(n=n, w_over_s=p):
                    seq = [order[verdict(i / 100, n, p, ALPHA)] for i in range(0, 101)]
                    self.assertEqual(seq, sorted(seq))

    def test_sweep_covers_a_large_undecided_band_at_n6(self):
        """能力差の連続スイープ: n=6 では p 軸の大半が判定不能・非支配は一つも出ない。"""
        rows = sweep_p(6, 0.2, tuple(round(0.05 * i, 2) for i in range(21)), ALPHA)
        kinds = {r["verdict"] for r in rows}
        self.assertNotIn(NOT_DOMINATES, kinds)                       # 下側の枝が空
        und = [r["p"] for r in rows if r["verdict"] == UNDECIDED]
        self.assertGreater(len(und), len(rows) / 2)                  # 半分以上が判定不能
        self.assertIn(0.0, und)                                      # 全滅の観測すら判定不能
        self.assertTrue(all(r["verdict"] == DOMINATES for r in rows if r["p"] >= 0.7))


class AuditTests(unittest.TestCase):
    """公開済み支配地図（experiments/market_map_results.json）の再判定。"""

    def setUp(self):
        self.au = audit(load_map(), ALPHA)

    def test_three_of_nine_published_checkmarks_are_not_supported(self):
        self.assertEqual(self.au["claimed"], 9)
        self.assertEqual(self.au["supported"], 6)
        self.assertEqual(self.au["retracted"], 3)

    def test_the_retracted_pairs_are_exactly_the_low_margin_ones(self):
        got = {(r["weak"], r["strong"]) for r in self.au["rows"]
               if r["claimed_dominates"] and not r["supported"]}
        self.assertEqual(got, {
            ("gemma4:latest", "haiku"),          # p̂=0.5    < 要 0.6667
            ("gemma4-chat:latest", "haiku"),     # p̂=0.4167 < 要 0.6667
            ("gemma4-chat:latest", "sonnet"),    # p̂=0.4167 < 要 0.5
        })

    def test_every_retracted_row_is_undecided_not_refuted(self):
        """撤回＝「非支配が示された」ではなく「何も言えない」。区別を潰さない。"""
        for r in self.au["rows"]:
            if r["claimed_dominates"] and not r["supported"]:
                self.assertEqual(r["verdict"], UNDECIDED)

    def test_structural_gap_is_actually_observed(self):
        """保守側（構造的極）を床に採る根拠＝per-task が 0/1 に張り付く実測が現に在る。"""
        rows = {r["weak"]: r["per_task_structural"] for r in self.au["rows"]}
        self.assertTrue(rows["gemma4:e2b"])        # 1,1,1,0,1,1 ＝ 構造的能力差


class RequiredSampleSizeTests(unittest.TestCase):

    def test_required_n_grows_as_the_boundary_is_approached(self):
        ns = [min_n_for_margin(0.2, d, ALPHA, 600, 20) for d in (0.30, 0.20, 0.10, 0.05)]
        self.assertEqual(ns, [12, 23, 67, 224])
        self.assertEqual(ns, sorted(ns))                      # δ を詰めるほど n は増える

    def test_min_n_for_margin_actually_satisfies_the_margin(self):
        """返した n で本当に δ 以内に入るか（そして安定窓の先でも保たれるか）。"""
        for d in (0.30, 0.20, 0.10, 0.05):
            n = min_n_for_margin(0.2, d, ALPHA, 600, 20)
            with self.subTest(delta=d, n=n):
                for k in range(n, n + 20):
                    self.assertLessEqual(crit_upper(k, 0.2, ALPHA) - 0.2, d + 1e-12)

    def test_n_six_cannot_reach_any_useful_margin(self):
        """実測の n=6 は最も緩い δ=0.30 にすら届かない（＝境界に寄れない）。"""
        self.assertGreater(crit_upper(6, 0.2, ALPHA) - 0.2, 0.30)


class RunTests(unittest.TestCase):

    def test_run_is_deterministic(self):
        self.assertEqual(run(), run())

    def test_headline_numbers_are_computed_not_hardcoded(self):
        """散文の数値が表の数値と一致するか（NOISE.md で一度踏んだ stale を再発させない）。"""
        r = run()
        h = r["headline"]
        self.assertIn(f"n≥{h['min_n_refutable_haiku']}", r["finding"])
        self.assertIn(f"n={h['min_n_delta05_haiku']}", r["finding"])
        self.assertIn(f"n={h['n_measured']}", r["finding"])
        self.assertFalse(h["refutable_at_measured_n"])
        haiku = next(b for b in r["bands"] if b["strong"] == "haiku")
        self.assertEqual(h["min_n_refutable_haiku"], haiku["min_n_refutable"])


if __name__ == "__main__":
    unittest.main()
