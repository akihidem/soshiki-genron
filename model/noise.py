r"""noise.py — 非決定な採点ハーネスの**検出床**（trials=1 が生む偽の mesh 点火を機械で弾く）。

[`mesh.py`](mesh.py) は「mesh 利得 > 0 ⟺ ρ<1（脱相関）」を*解析*で導いた。だが**実測の利得は
測定器のノイズでも立つ**。本リポは一度それに嵌り、撤回している（[`../experiments/SWEBENCH_TRIALS.md`
](../experiments/SWEBENCH_TRIALS.md)・PAPER §9-11）:

    N=24 の opus×codex で union 0.792 > best 0.75・**gain +0.042** が出て「real frontier で初の点火」と
    報告・commit した → 同じ N=24 を2回目に回すと **gain +0.042 → 0** に flip。codex は決定的（24/24
    が2試行で完全一致）だが opus は `claude-cli-run`（非決定 TUI）経由で **3/24 = 12.5% のセル不一致**
    を持っていた。trial-1 の codex-only 3件は、全部 opus の*不調*（ノイズ）だった。

本ファイルはその撤回が**運でなく予測可能だった**ことを機械で示し、以後の mesh 主張に**床**を課す。
「trials>1 を全実証へ」を prose の caveat でなく**判定器**にするのが目的。

## ① 恒等式 ── 「点火には*相互*相補が要る」を観察でなく定理にする

2モデルの解集合 A,B について a=|A\B|, b=|B\A|, c=|A∩B| とすると |A∪B| = c+a+b、|A|=c+a、|B|=c+b。
    gain = union − best = (c+a+b) − max(c+a, c+b) = a + b − max(a,b) = **min(a, b)**
    ⟹ **gain(率) = min(a,b)/n**。  gain>0 ⟺ a>0 *かつ* b>0 ⟺ **相互**相補。
（mesh.py の「入れ子（非対称）なら ρ<1 でも gain 0」は、この恒等式の系にすぎない）

## ② 帰無仮説と検出床

**H0**: 真の解集合に*相互*相補が無い（min(a_true, b_true) = 0 ＝ 入れ子 or 一致）。つまり真の gain = 0。
**ノイズ**: 各セルの採点が真値から独立に確率 f で反転。trials=t は多数決 → 実効反転率 f_eff(f, t)。

この下で**観測される** (a, b) の同時分布を厳密に畳み込み（DP・RNG なし）、
    **detection_floor** = P(min(a,b) ≥ m | H0) ≤ α を満たす最小の m
を返す。**観測 gain が m/n を超えない限り「点火」と報告してはならない。**

f は実測から推定する。2回の独立試行のセル不一致率 d は対称独立反転モデルで d = 2f(1−f) なので
    **f = (1 − √(1−2d)) / 2**。
本リポの実測: opus d=3/24=0.125 → f≈0.067 ／ codex d=0/24 → f=0 ／ fable d=3/6=0.5（対称モデルの上限）。

## ③ 頑健推定 ── 割れたセルは主張に使えない

trials>1 があるなら、A-only と数えてよいのは「**A が全試行で解き、B が全試行で落とす**」セルだけ。
片方でも試行間で割れたセルは、その相補性の証拠にならない（`robust_counts`）。これは
SWEBENCH_TRIALS.md が手で行った「安定な相互相補は無い」の機械化である。

決定的（厳密・stdlib のみ・RNG なし）。 run: python3 -m model.noise
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# 実測ベクトル ── 同じ N=24 を独立に2回。index は experiments/swebench_all_results.json の rows 順
# （pytest 6件 → sympy 18件）。trial-1 = swebench_all_results.json、
#   trial-2 = SWEBENCH_T2.md（pytest6）+ SWEBENCH_SYMPY_T2.md（sympy18）の instance 表。
# --------------------------------------------------------------------------- #
SWE24_OPUS_T1 = [0, 1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 0]   # 16/24
SWE24_OPUS_T2 = [0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0]   # 19/24
SWE24_CODEX_T1 = [0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0]  # 18/24
SWE24_CODEX_T2 = [0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0]  # 18/24（t1 と同一）

# pytest-6 部分集合（同じ index 0..5）。trial-1 = SWEBENCH.md、trial-2 = SWEBENCH_T2.md。
SWE6_OPUS_T1 = [0, 1, 0, 0, 1, 1]
SWE6_OPUS_T2 = [0, 1, 1, 0, 1, 1]
SWE6_CODEX_T1 = [0, 1, 1, 0, 1, 1]
SWE6_CODEX_T2 = [0, 1, 1, 0, 1, 1]

# fable-5 pytest-6（SWEBENCH_FABLE_PT6.md・3/6 flip で撤回済み。ここでは flip 率の実測点として使う）
SWE6_FABLE_T1 = [0, 1, 1, 0, 1, 1]
SWE6_FABLE_T2 = [0, 0, 0, 1, 1, 1]


# --------------------------------------------------------------------------- #
# ① 恒等式: mesh gain = min(a, b) / n
# --------------------------------------------------------------------------- #
def split_counts(va: list, vb: list) -> dict:
    r"""2本の解ベクトル（1=解けた）から a=|A\B| / b=|B\A| / common / neither を数える。"""
    if len(va) != len(vb):
        raise ValueError("solve vectors must have equal length")
    a = sum(1 for x, y in zip(va, vb) if x and not y)
    b = sum(1 for x, y in zip(va, vb) if y and not x)
    common = sum(1 for x, y in zip(va, vb) if x and y)
    return {"n": len(va), "a_only": a, "b_only": b, "common": common,
            "neither": len(va) - a - b - common}


def gain_from_counts(a: int, b: int, n: int) -> float:
    """**恒等式**: union − best_single = min(a, b) / n。gain>0 ⟺ *相互*相補（a>0 かつ b>0）。"""
    if n <= 0:
        return 0.0
    return min(a, b) / n


# --------------------------------------------------------------------------- #
# ② 実測ノイズ ── 試行間の不一致率 d → セル反転率 f → 多数決後の実効反転率 f_eff
# --------------------------------------------------------------------------- #
def disagreement_rate(trials: list) -> float:
    """同一モデルの複数試行の**セル不一致率 d**（全会一致でないセルの割合）。opus は 3/24=0.125。"""
    if not trials or not trials[0]:
        return 0.0
    n = len(trials[0])
    if any(len(v) != n for v in trials):
        raise ValueError("all trial vectors must have equal length")
    return sum(1 for k in range(n) if len({v[k] for v in trials}) > 1) / n


def flip_from_disagreement(d: float) -> float:
    """対称独立反転モデル: 2試行が食い違う確率 d = 2f(1−f) ⟹ **f = (1−√(1−2d))/2**。

    d ≥ 0.5 は対称モデルの表現域外（実数解なし）→ 0.5（＝コイン投げ＝情報ゼロ）に飽和させる。
    """
    if d <= 0.0:
        return 0.0
    if d >= 0.5:
        return 0.5
    return (1.0 - math.sqrt(1.0 - 2.0 * d)) / 2.0


def effective_flip(f: float, trials: int) -> float:
    """trials 回を**多数決**した後の実効反転率。偶数 trials の同数は 1/2 で誤りに倒す（保守側）。

    trials=1 → f。 trials=3 → 3f²(1−f)+f³。 f=0.5 ではどれだけ重ねても 0.5（情報が無い）。
    """
    if trials <= 1:
        return f
    p = 0.0
    for k in range(trials + 1):
        pk = math.comb(trials, k) * (f ** k) * ((1.0 - f) ** (trials - k))
        if 2 * k > trials:
            p += pk
        elif 2 * k == trials:
            p += 0.5 * pk
    return p


# --------------------------------------------------------------------------- #
# ③ 頑健推定 ── 試行間で割れたセルは相補性の証拠に使えない
# --------------------------------------------------------------------------- #
def stable_vector(trials: list) -> list:
    """全試行で一致したセルだけ 0/1、割れたセルは None（＝主張に使えない）。"""
    n = len(trials[0])
    out = []
    for k in range(n):
        vals = {v[k] for v in trials}
        out.append(next(iter(vals)) if len(vals) == 1 else None)
    return out


def robust_counts(trials_a: list, trials_b: list) -> dict:
    """*安定*セルだけで相互相補を数える。

    A-only と数えるには「**A が全試行で解き、B が全試行で落とす**」が要る。片方でも割れたら不算入。
    trials=1 では naive（=split_counts）に退化する ── だから trials=1 は床を持てない。
    """
    sa, sb = stable_vector(trials_a), stable_vector(trials_b)
    n = len(sa)
    a = sum(1 for x, y in zip(sa, sb) if x == 1 and y == 0)
    b = sum(1 for x, y in zip(sa, sb) if y == 1 and x == 0)
    common = sum(1 for x, y in zip(sa, sb) if x == 1 and y == 1)
    neither = sum(1 for x, y in zip(sa, sb) if x == 0 and y == 0)
    unstable = sum(1 for x, y in zip(sa, sb) if x is None or y is None)
    return {"n": n, "a_only": a, "b_only": b, "common": common, "neither": neither,
            "unstable": unstable, "gain": round(gain_from_counts(a, b, n), 4)}


# --------------------------------------------------------------------------- #
# ④ 帰無分布と検出床（厳密 DP・RNG なし）
# --------------------------------------------------------------------------- #
@dataclass
class TrueStructure:
    """真の（ノイズ抜きの）解集合の構造。H0 は min(a_only, b_only) == 0（相互相補ゼロ）。"""
    common: int
    a_only: int
    b_only: int
    neither: int

    @property
    def n(self) -> int:
        return self.common + self.a_only + self.b_only + self.neither

    @property
    def is_null(self) -> bool:
        return min(self.a_only, self.b_only) == 0


def _observed_probs(kind: str, fa: float, fb: float) -> tuple:
    """真のセル種別 kind が、観測で『A-only』/『B-only』に見える確率 (pa, pb)。

    A が真に解く時 A は確率 (1−fa) で 1 と観測され、真に落とす時は確率 fa で 1 と誤観測される。
    """
    if kind == "common":                       # 両者が真に解く
        return (1.0 - fa) * fb, fa * (1.0 - fb)
    if kind == "a_only":                       # A だけ真に解く
        return (1.0 - fa) * (1.0 - fb), fa * fb
    if kind == "b_only":                       # B だけ真に解く
        return fa * fb, (1.0 - fa) * (1.0 - fb)
    if kind == "neither":                      # 両者が真に落とす
        return fa * (1.0 - fb), (1.0 - fa) * fb
    raise ValueError(f"unknown cell kind: {kind}")


def null_joint(st: TrueStructure, fa: float, fb: float, trials: int = 1) -> dict:
    """観測 (a, b) の**厳密な同時分布** {(a,b): p}。タスクごとの独立畳み込み（DP）。"""
    ea, eb = effective_flip(fa, trials), effective_flip(fb, trials)
    dist = {(0, 0): 1.0}
    for kind in ("common", "a_only", "b_only", "neither"):
        pa, pb = _observed_probs(kind, ea, eb)
        pn = 1.0 - pa - pb                       # A-only でも B-only でもない（両解 or 両失敗）
        for _ in range(getattr(st, kind)):
            nxt: dict = {}
            for (a, b), p in dist.items():
                if pa > 0.0:
                    nxt[(a + 1, b)] = nxt.get((a + 1, b), 0.0) + p * pa
                if pb > 0.0:
                    nxt[(a, b + 1)] = nxt.get((a, b + 1), 0.0) + p * pb
                if pn > 0.0:
                    nxt[(a, b)] = nxt.get((a, b), 0.0) + p * pn
            dist = nxt
    return dist


def p_gain_ge(st: TrueStructure, fa: float, fb: float, trials: int, m: int) -> float:
    """P(観測 min(a,b) ≥ m)。m=0 なら 1.0。"""
    if m <= 0:
        return 1.0
    return sum(p for (a, b), p in null_joint(st, fa, fb, trials).items() if min(a, b) >= m)


def detection_floor(st: TrueStructure, fa: float, fb: float, trials: int = 1,
                    alpha: float = 0.05) -> dict:
    """H0 の下で P(min(a,b) ≥ m) ≤ α となる**最小の m**（＝報告してよい最小の gain）。

    観測 gain がこの床未満なら「点火」と報告してはならない ── ノイズだけで同じ値が出るから。
    """
    if not st.is_null:
        raise ValueError("detection_floor は H0（min(a_only, b_only)=0）の構造にのみ定義される")
    dist = null_joint(st, fa, fb, trials)
    for m in range(1, st.n + 1):
        p = sum(pp for (a, b), pp in dist.items() if min(a, b) >= m)
        if p <= alpha:
            return {"m": m, "gain": round(m / st.n, 4), "p_at_m": round(p, 6),
                    "alpha": alpha, "trials": trials, "n": st.n,
                    "f_eff_a": round(effective_flip(fa, trials), 6),
                    "f_eff_b": round(effective_flip(fb, trials), 6)}
    return {"m": None, "gain": None, "p_at_m": None, "alpha": alpha, "trials": trials, "n": st.n,
            "f_eff_a": round(effective_flip(fa, trials), 6),
            "f_eff_b": round(effective_flip(fb, trials), 6)}


def min_trials_for(st: TrueStructure, fa: float, fb: float, m: int,
                   alpha: float = 0.05, t_max: int = 25) -> "int | None":
    """m タスク分の gain を報告可能にするのに要る trials（奇数のみ）。t_max まで届かなければ None。"""
    for t in range(1, t_max + 1, 2):
        if p_gain_ge(st, fa, fb, t, m) <= alpha:
            return t
    return None


def reportable(observed_m: int, st: TrueStructure, fa: float, fb: float,
               trials: int = 1, alpha: float = 0.05) -> bool:
    """**ゲート**: 観測された m タスク分の gain を『点火』と報告してよいか（床を超えたか）。"""
    fl = detection_floor(st, fa, fb, trials, alpha)
    return fl["m"] is not None and observed_m >= fl["m"]


# --------------------------------------------------------------------------- #
# ⑤ 本リポの実測へ適用
# --------------------------------------------------------------------------- #
def swebench_case() -> dict:
    """実 SWE-bench N=24（opus×codex）に①〜④を適用し、撤回が予測可能だったことを示す。"""
    opus_trials = [SWE24_OPUS_T1, SWE24_OPUS_T2]
    codex_trials = [SWE24_CODEX_T1, SWE24_CODEX_T2]

    d_opus = disagreement_rate(opus_trials)
    d_codex = disagreement_rate(codex_trials)
    f_opus = flip_from_disagreement(d_opus)
    f_codex = flip_from_disagreement(d_codex)

    naive = split_counts(SWE24_OPUS_T1, SWE24_CODEX_T1)        # trial-1 だけを見た時（＝当時の報告）
    naive["gain"] = round(gain_from_counts(naive["a_only"], naive["b_only"], naive["n"]), 4)
    naive_t2 = split_counts(SWE24_OPUS_T2, SWE24_CODEX_T2)
    naive_t2["gain"] = round(gain_from_counts(naive_t2["a_only"], naive_t2["b_only"], naive_t2["n"]), 4)

    robust = robust_counts(opus_trials, codex_trials)          # 安定セルだけ（＝頑健な結論）

    # H0 構造: trials=2 の頑健データが言う「opus の解集合 ⊇ codex の解集合（相互相補ゼロ）」。
    # 割れた 3 セル（opus が trial-2 で解いた）は「真は opus も解く」＝common に寄せる（A 案）。
    h0_a = TrueStructure(common=robust["common"] + robust["unstable"], a_only=robust["a_only"],
                         b_only=robust["b_only"], neither=robust["neither"])
    # 感度確認: 割れた 3 セルを「真は両者落とす」＝neither に寄せる（B 案）。どちらも H0。
    h0_b = TrueStructure(common=robust["common"], a_only=robust["a_only"],
                         b_only=robust["b_only"], neither=robust["neither"] + robust["unstable"])

    observed_m = min(naive["a_only"], naive["b_only"])          # trial-1 の gain が乗っていたタスク数 = 1

    floors = []
    for t in (1, 3, 5, 7):
        fa_ = detection_floor(h0_a, f_opus, f_codex, trials=t)
        fb_ = detection_floor(h0_b, f_opus, f_codex, trials=t)
        floors.append({"trials": t,
                       "floor_m_A": fa_["m"], "floor_gain_A": fa_["gain"],
                       "floor_m_B": fb_["m"], "floor_gain_B": fb_["gain"],
                       "p_false_ignition_A": round(p_gain_ge(h0_a, f_opus, f_codex, t, 1), 4),
                       "reportable_A": reportable(observed_m, h0_a, f_opus, f_codex, trials=t)})

    # f の推定に依存しないことを見る（対称モデル f≈0.067 vs 「不一致率をそのまま f と読む」0.125 の両端）
    sensitivity = [{"f_opus": round(f, 4),
                    "floor_m_trials1": detection_floor(h0_a, f, f_codex, 1)["m"],
                    "floor_m_trials3": detection_floor(h0_a, f, f_codex, 3)["m"],
                    "p_false_ignition_trials1": round(p_gain_ge(h0_a, f, f_codex, 1, 1), 4)}
                   for f in (0.05, round(f_opus, 4), 0.10, 0.125)]

    return {
        "measured_noise": {
            "opus_disagreement_d": round(d_opus, 4), "opus_flip_f": round(f_opus, 4),
            "codex_disagreement_d": round(d_codex, 4), "codex_flip_f": round(f_codex, 4),
            "note": "同じ N=24 を独立2回（SWEBENCH_TRIALS.md）。codex は完全再現・opus だけ非決定。",
        },
        "trial1_naive": naive,          # 当時の報告: a=1, b=3 → gain +0.0417
        "trial2_naive": naive_t2,       # 2回目: a=1, b=0 → gain 0
        "robust_trials2": robust,       # 安定セルのみ: a=1, b=0, unstable=3 → gain 0
        "h0_structure_A": dataclasses.asdict(h0_a),
        "h0_structure_B": dataclasses.asdict(h0_b),
        "observed_gain_tasks": observed_m,
        "p_trial1_gain_under_h0": round(p_gain_ge(h0_a, f_opus, f_codex, 1, observed_m), 4),
        "floor_by_trials": floors,
        "f_sensitivity": sensitivity,
        "min_trials_for_1_task": min_trials_for(h0_a, f_opus, f_codex, 1),
        "verdict": ("trial-1 の +0.042 は H0（相互相補ゼロ）＋opus のノイズだけで高確率に生じる。"
                    "trials=1 の検出床は 3 タスク（gain 0.125）で、観測 1 タスク（0.042）は 3 倍下。"
                    "**撤回は運でなく、trial-2 を回す前に計算できた。**"),
    }


def pytest6_case() -> dict:
    """pytest-6 部分集合（trials=2）── 頑健にも gain 0。ただし n=6 では床が高すぎて何も検出できない。"""
    opus_trials = [SWE6_OPUS_T1, SWE6_OPUS_T2]
    codex_trials = [SWE6_CODEX_T1, SWE6_CODEX_T2]
    robust = robust_counts(opus_trials, codex_trials)
    f_opus = flip_from_disagreement(disagreement_rate(opus_trials))
    f_codex = flip_from_disagreement(disagreement_rate(codex_trials))
    h0 = TrueStructure(common=robust["common"] + robust["unstable"], a_only=robust["a_only"],
                       b_only=robust["b_only"], neither=robust["neither"])
    return {"robust": robust, "f_opus": round(f_opus, 4), "f_codex": round(f_codex, 4),
            "floor_trials1": detection_floor(h0, f_opus, f_codex, 1),
            "floor_trials3": detection_floor(h0, f_opus, f_codex, 3)}


def fable_case() -> dict:
    """fable-5 pytest-6 ── 不一致 3/6 = 0.5 ＝ 対称モデルの上限＝**多数決を重ねても情報が増えない**。"""
    trials = [SWE6_FABLE_T1, SWE6_FABLE_T2]
    d = disagreement_rate(trials)
    f = flip_from_disagreement(d)
    return {"disagreement_d": round(d, 4), "flip_f": round(f, 4),
            "f_eff_by_trials": {t: round(effective_flip(f, t), 4) for t in (1, 3, 5, 9)},
            "note": ("d=0.5 は対称反転モデルの表現域の縁＝採点が実質コイン投げ。f_eff はどの trials でも "
                     "0.5 のまま＝**このハーネスでは fable の per-instance 値は何回回しても確定しない**。"
                     "SWEBENCH_FABLE_PT6.md の『非コード出力で parse 不能』＝採点器の故障であって、"
                     "trials を増やして平均する対象ではない（先に harness を直す）。")}


def run() -> dict:
    return {"identity": "mesh gain = min(a, b) / n（a=|A\\B|, b=|B\\A|）⟹ gain>0 ⟺ *相互*相補",
            "null_hypothesis": "H0: min(a_true, b_true) = 0（真の相互相補ゼロ＝入れ子 or 一致）",
            "noise_model": "各セルが独立に確率 f で反転。2試行不一致率 d = 2f(1−f) ⟹ f=(1−√(1−2d))/2。"
                           "trials=t は多数決 → f_eff(f,t)。",
            "swebench_n24": swebench_case(),
            "pytest6": pytest6_case(),
            "fable_pt6": fable_case(),
            "gate": ("観測 gain（タスク数 m）が detection_floor(n, f, trials, α=0.05) 未満なら "
                     "『点火』と報告しない。trials=1 は robust_counts が naive に退化する＝床を持てない。"),
            "falsifier": ("同一条件で trials を増やした時、観測 gain が床を超えたまま安定するなら"
                          "『床未満は報告しない』は保守的すぎる＝本モデルは偽（床を下げるべき）。")}


def _md(r: dict) -> str:
    s = r["swebench_n24"]
    mn = s["measured_noise"]
    L = ["# 検出床 — 非決定な採点ハーネスの下で mesh 利得を報告してよい最小値",
         "",
         "[`MESH.md`](MESH.md) は「利得>0 ⟺ ρ<1」を*解析*で導いた。だが**実測の利得は測定器のノイズでも"
         "立つ**。本リポは一度それに嵌り撤回した（[`../experiments/SWEBENCH_TRIALS.md`]"
         "(../experiments/SWEBENCH_TRIALS.md)）。ここではその撤回が**運でなく予測可能**だったことを示し、"
         "以後の mesh 主張に床を課す。生数値 [`noise_results.json`](noise_results.json)。",
         "",
         "## ① 恒等式（「点火には*相互*相補が要る」を定理にする）",
         "",
         f"> **{r['identity']}**",
         "",
         "`union − best = (c+a+b) − max(c+a, c+b) = a + b − max(a,b) = min(a,b)`。"
         "MESH.md の「入れ子（非対称）なら ρ<1 でも gain 0」は、この恒等式の系にすぎない。",
         "",
         "## ② 実測ノイズ（同じ N=24 を独立2回）",
         "",
         "| モデル | 試行間セル不一致率 d | 反転率 f = (1−√(1−2d))/2 |",
         "|---|---|---|",
         f"| opus（`claude-cli-run` 非決定 TUI） | **{mn['opus_disagreement_d']}** (3/24) | **{mn['opus_flip_f']}** |",
         f"| codex（`codex exec`） | {mn['codex_disagreement_d']} (0/24) | {mn['codex_flip_f']} |",
         "",
         f"{mn['note']} **ベンダ間で採点の決定性すら非対称**＝opus 側にだけ trials が要る。",
         "",
         "## ③ 何が観測され、頑健には何が残ったか",
         "",
         "| | a=opus-only | b=codex-only | gain = min(a,b)/n |",
         "|---|---|---|---|"]
    t1, t2, rb = s["trial1_naive"], s["trial2_naive"], s["robust_trials2"]
    L += [f"| trial-1 のみ（当時の報告） | {t1['a_only']} | {t1['b_only']} | **+{t1['gain']}** ← 「初の点火」と報告 |",
          f"| trial-2 のみ | {t2['a_only']} | {t2['b_only']} | **{t2['gain']}** |",
          f"| **頑健（安定セルのみ・trials=2）** | {rb['a_only']} | {rb['b_only']} | "
          f"**{rb['gain']}**（不安定セル {rb['unstable']} 件は不算入） |",
          "",
          "「A-only」と数えてよいのは *A が全試行で解き B が全試行で落とす* セルだけ。trial-1 の codex-only "
          "3件は opus が trial-2 で解いた＝**opus の不調（ノイズ）であって codex の相補性ではない**。",
          "",
          "## ④ 検出床 ── H0（相互相補ゼロ）の下でノイズだけが作る gain",
          "",
          f"H0 構造 A: {s['h0_structure_A']}（割れた 3 セルを common へ）／"
          f"B: {s['h0_structure_B']}（neither へ）── どちらも H0。",
          "",
          "| trials | 実効反転率 f_eff(opus) | 検出床 m (A / B) | 床の gain | ノイズだけで gain≥1タスク が出る確率 | 観測 1 タスクは報告可? |",
          "|---|---|---|---|---|---|"]
    for fl in s["floor_by_trials"]:
        fe = effective_flip(mn["opus_flip_f"], fl["trials"])
        L.append(f"| {fl['trials']} | {round(fe, 4)} | **{fl['floor_m_A']}** / {fl['floor_m_B']} | "
                 f"{fl['floor_gain_A']} | **{fl['p_false_ignition_A']}** | "
                 f"{'✓' if fl['reportable_A'] else '**✗**'} |")
    L += ["",
          f"- **trials=1 の検出床は {s['floor_by_trials'][0]['floor_m_A']} タスク（gain "
          f"{s['floor_by_trials'][0]['floor_gain_A']}）。観測された +{t1['gain']} は 1 タスク分＝床の 1/3。**",
          f"- H0 の下で trial-1 の観測（gain≥1タスク）が出る確率は **{s['p_trial1_gain_under_h0']}** ── "
          "つまり **あの「点火」はノイズの*期待される*出力**であって、H0 に対する証拠ではなかった。",
          f"- **{s['verdict']}**",
          "",
          "### f の推定に依存しないか（感度）",
          "",
          "| 仮定した f(opus) | trials=1 の床 | trials=3 の床 | ノイズだけで gain≥1 が出る確率(trials=1) |",
          "|---|---|---|---|"]
    for sv in s["f_sensitivity"]:
        L.append(f"| {sv['f_opus']} | {sv['floor_m_trials1']} | {sv['floor_m_trials3']} | "
                 f"{sv['p_false_ignition_trials1']} |")
    mt = s["min_trials_for_1_task"]
    L += ["",
          "**床の*値*は f に依存する**（実測レンジ f=0.067〜0.125 では trials=1 の床は 3 タスクだが、"
          "データに裏付けのない楽観値 f=0.05 まで下げると 2 に落ちる）。"
          "**依存しないのは結論の方**: どの f でも床は 2 以上＝**観測された 1 タスクは床未満**で、"
          "ノイズだけで「点火」が出る確率はどの f でも過半（0.58〜0.85）。trials=3 の床はレンジ全域で 2 タスク。",
          "",
          f"1 タスク分（gain 0.042）を報告可能にするのに要る trials: "
          f"**{mt if mt else '25 回以内では到達不能'}**"
          f"（= 24 instance × 2 model × {mt if mt else '?'} = "
          f"**{24 * 2 * mt if mt else '?'} 実行**）。"
          "当時 trials=1 で「点火」と報告したのは、**必要標本の 1/5** だった。",
          "",
          "## ⑤ fable-5（採点が壊れている時は trials を増やしても無駄）",
          ""]
    fb = r["fable_pt6"]
    L += [f"- 不一致率 d = **{fb['disagreement_d']}**（3/6）→ f = {fb['flip_f']} ＝ 対称モデルの上限。",
          f"- 多数決後の実効反転率: {fb['f_eff_by_trials']} ── **どれだけ重ねても 0.5 のまま**。",
          f"- {fb['note']}",
          "",
          "## ⑥ ゲート（以後の mesh 主張に課す床）",
          "",
          f"> {r['gate']}",
          "",
          "## 反証条件",
          f"- {r['falsifier']}"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "noise_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "NOISE.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")

    s = r["swebench_n24"]
    mn = s["measured_noise"]
    print(f"identity: {r['identity']}")
    print(f"H0:       {r['null_hypothesis']}")
    print()
    print(f"measured noise: opus d={mn['opus_disagreement_d']} -> f={mn['opus_flip_f']} | "
          f"codex d={mn['codex_disagreement_d']} -> f={mn['codex_flip_f']}")
    print(f"trial-1 (as reported): a={s['trial1_naive']['a_only']} b={s['trial1_naive']['b_only']} "
          f"gain=+{s['trial1_naive']['gain']}")
    print(f"trial-2:               a={s['trial2_naive']['a_only']} b={s['trial2_naive']['b_only']} "
          f"gain={s['trial2_naive']['gain']}")
    print(f"ROBUST (stable only):  a={s['robust_trials2']['a_only']} b={s['robust_trials2']['b_only']} "
          f"gain={s['robust_trials2']['gain']} (unstable={s['robust_trials2']['unstable']})")
    print()
    print("detection floor under H0 (no mutual complementarity):")
    for fl in s["floor_by_trials"]:
        print(f"  trials={fl['trials']}: floor={fl['floor_m_A']} tasks (gain {fl['floor_gain_A']})  "
              f"P(noise-only gain>=1 task)={fl['p_false_ignition_A']}  "
              f"observed-1-task reportable={fl['reportable_A']}")
    print()
    print(f"P(trial-1 observation | H0 + measured noise) = {s['p_trial1_gain_under_h0']}")
    print(f"VERDICT: {s['verdict']}")
    print(f"\nwrote {os.path.join(out_dir, 'noise_results.json')} and NOISE.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
