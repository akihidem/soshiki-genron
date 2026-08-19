r"""gap.py ── 能力差の**連続スイープ**と、境界 p\*=w/s の**判定分解能の床**。

[`market.py`](market.py) は支配定理を導いた: エスカレーション市場が flat-strong を Pareto 支配
⟺ **p > w/s**（安いティアの完全解率 > コスト比）。ロードマップ①「能力差の連続スイープ ──
境界(p≈w/s) に寄せて実測」は、素直に読むと「もっと弱いモデル / 難タスクを探せば境界に届く」である。

**本ファイルはそれを否定する。境界に届かないのはモデルのせいでなく、標本数 n のせいである。**

定理が言うのは**真の** p についてであって、実験が持つのは推定量 p̂ にすぎない。ところが実測側
（`experiments/market_external.py` の `calibrate`/`map_models`）は

    "dominates": p > w / s          # ← p̂ の**点推定をそのまま二値判定**している

と、標本誤差を一切通さずに ✓ を刻んでいる。これは [`noise.py`](noise.py) が mesh 軸で潰したのと
**同型の fail-open** である（あちらは「観測 gain > 0 なら点火」だった）。境界の近傍ではこの符号比較は
純粋なコイン投げになる ── そして「境界に寄せる」とは、定義上その近傍へ行くことである。

## ① 保守的（構造的）分散モデル ── trials は境界分解能を買わない

p̂ = (1/n)·Σ_i (k_i/t)、k_i ~ Bin(t, p_i)（n タスク・各 t 試行）。二段抽出なので

    Var(p̂) = [ Var_task(p_i) + E_i[p_i(1−p_i)]/t ] / n

**第1項（タスク間分散）は t をいくら積んでも消えない。** そして実測の per-task solve_rate は
実際に 0/1 へ張り付く（`market_map_results.json` の gemma4:e2b = 1,1,1,0,1,1 ＝*構造的*能力差）。
その極 p_i ∈ {0,1} では E_i[p_i(1−p_i)] = 0 かつ Var_task = p(1−p) なので

    **Var(p̂) = p(1−p)/n**   ＝ タスク上の Bin(n, p)。**trials の寄与は厳密にゼロ。**

もう一方の極（全タスクが同一の p_i ＝ 純確率的）では全 n·t 抽出が独立で Bin(n·t, p) になる。
実測はこの両極を*同じ地図の中に*持っている（e2b は 0/1 張り付き＝構造的、gemma4:latest は
全タスク 0.5 ＝確率的）。どちらの極にいるかは事前に分からないので、[[fail-closed]] に従い
**保守側（構造的・Bin(n, ·)）を床に採る**。確率的側の床は `bracket` として併記するに留める。

## ② 判定床（厳密二項・正規近似なし）

**H0: p = w/s**（＝境界上。market の利得はちょうどゼロ）。
- **支配を宣言してよい**のは P(Bin(n, w/s) ≥ n·p̂) ≤ α のときだけ → 上側臨界 `crit_upper`。
- **非支配を宣言してよい**のは P(Bin(n, w/s) ≤ n·p̂) ≤ α のときだけ → 下側臨界 `crit_lower`。
- その間は **UNDECIDED**。「p̂ > w/s だったから支配」とは*言わない*（否定形でなく肯定形の証明）。

## ③ 帰結（すべて機械計算・α=0.05）

1. **現行手続きの第一種過誤は 0.345**（n=6, w/s=0.2）。真に境界上（利得ゼロ）のモデルを、
   MARKET_MAP は **3回に1回「支配」と刻む**。床を通せば 0.017 に落ちる。
2. **公開済み地図の ✓ 9 個のうち 3 個は支持されない**（`audit`）。gemma4:latest と
   gemma4-chat の →haiku、gemma4-chat の →sonnet は **UNDECIDED**。
3. **n=6 では「非支配」が*どんな観測でも*言えない**（下側の枝が空）。p̂=0/6 ですら
   P(X=0 | p=0.2) = 0.262 > α。⟹ **支配の主張は n=6 では原理的に反証不能**であり、
   「より弱いモデルを探して境界に寄せる」は、n=6 のままでは**空振りが確定している**。
4. 反証可能性が生まれる最小 n は **14**（w/s=0.2）。境界から δ=0.05 以内を判定するには
   **n=224** が要る（δ=0.10 でも 67）。⟹ ロードマップ①の次の一手は「弱いモデル探し」でなく
   **n を増やすこと**。

（同じ結論に mesh 軸でも到達している: NOISE.md「pytest-6 級（n=6）は床が 2 タスク＝gain 0.333
未満を原理的に検出できない ⟹ trials より先に n を増やす対象を選別する」。軸が違っても効くのは n。）

決定的（厳密・stdlib のみ・RNG なし）。 run: python3 -m model.gap
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass, field

# 実測の強ティア（experiments/market_external.py の _STRONG_TIERS と同じ・定価比の代理）
STRONG_TIERS = (("haiku", 1.0), ("sonnet", 3.0), ("opus", 15.0))
WEAK_COST = 0.2

# 支配地図の実測（experiments/market_map_results.json）。ここに転記せず run() が読む ──
# 実データとずれたら test_generated_docs.py の stale 床が落とす。
_MAP_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "experiments", "market_map_results.json")

DOMINATES = "DOMINATES"
NOT_DOMINATES = "DOES_NOT_DOMINATE"
UNDECIDED = "UNDECIDED"


@dataclass
class GapParams:
    alpha: float = 0.05                 # 片側有意水準（各枝に対して）
    n_max: int = 600                    # 必要 n の探索上限
    stability_window: int = 20          # 必要 n は「そこから先ずっと満たす」ことを要求（step のジッタ対策）
    n_grid: tuple = (6, 12, 14, 24, 50, 100, 200, 400)     # 盲帯スイープの n
    delta_grid: tuple = (0.30, 0.20, 0.10, 0.05)           # 境界からの目標分解能 δ
    p_grid: tuple = field(default_factory=lambda: tuple(round(0.05 * i, 2) for i in range(21)))


# --------------------------------------------------------------------------- #
# 厳密二項（log 空間の漸化式・math.comb の桁溢れと p**n の桁落ちを両方避ける）
# --------------------------------------------------------------------------- #
def _log_pmf_vector(n: int, p: float) -> list:
    """log P(X=i) を i=0..n について漸化式で。n が大きくても underflow で全滅しない。"""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0,1) for the exact tail")
    out = [n * math.log1p(-p)]                       # log P(X=0) = n·log(1−p)
    lo = math.log(p) - math.log1p(-p)                # log(p/(1−p))
    for i in range(1, n + 1):
        out.append(out[i - 1] + math.log((n - i + 1) / i) + lo)
    return out


def sf(k: int, n: int, p: float) -> float:
    """P(X ≥ k), X ~ Bin(n, p)。厳密。"""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    lp = _log_pmf_vector(n, p)
    return sum(math.exp(v) for v in lp[k:])


def cdf(k: int, n: int, p: float) -> float:
    """P(X ≤ k), X ~ Bin(n, p)。厳密。"""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    lp = _log_pmf_vector(n, p)
    return sum(math.exp(v) for v in lp[:k + 1])


# --------------------------------------------------------------------------- #
# ② 臨界値 ── 「肯定形で証明できた時だけ宣言する」
# --------------------------------------------------------------------------- #
def crit_upper(n: int, ratio: float, alpha: float = 0.05):
    """支配を宣言してよい最小の p̂。P(Bin(n, w/s) ≥ k) ≤ α なる最小 k → k/n。

    存在しない（どんな観測でも支配を証明できない）なら None。均質 w=s（ratio=1）では
    常に None ＝ 定理の regime ①「市場は勝てない」と一致する。
    """
    if n <= 0 or not 0.0 < ratio < 1.0:
        return None                       # ratio≥1 は p>1 を要求＝到達不能（regime ①）
    lp = _log_pmf_vector(n, ratio)
    tail = 0.0
    for k in range(n, -1, -1):            # 上側から積む（k を下げると tail は単調増加）
        tail += math.exp(lp[k])
        if tail > alpha:
            return (k + 1) / n if k + 1 <= n else None
    return 0.0


def crit_lower(n: int, ratio: float, alpha: float = 0.05):
    """非支配を宣言してよい最大の p̂。P(Bin(n, w/s) ≤ k) ≤ α なる最大 k → k/n。

    **None なら「非支配」はどんな観測でも言えない**（下側の枝が空＝反証不能）。
    n=6, w/s=0.2 がまさにこれ: p̂=0/6 でも P(X=0)=0.262 > α。
    """
    if n <= 0 or not 0.0 < ratio < 1.0:
        return None
    lp = _log_pmf_vector(n, ratio)
    head = 0.0
    for k in range(0, n + 1):
        head += math.exp(lp[k])
        if head > alpha:
            return (k - 1) / n if k - 1 >= 0 else None
    return 1.0


def verdict(p_hat: float, n: int, ratio: float, alpha: float = 0.05) -> str:
    """床を通した三値判定。UNDECIDED を潰さない（＝ fail-closed）。"""
    tol = 1e-9
    up, lo = crit_upper(n, ratio, alpha), crit_lower(n, ratio, alpha)
    if up is not None and p_hat >= up - tol:
        return DOMINATES
    if lo is not None and p_hat <= lo + tol:
        return NOT_DOMINATES
    return UNDECIDED


def type_i_error(n: int, ratio: float, alpha: float = 0.05) -> dict:
    """H0（真に境界上・利得ゼロ）で「支配」と誤って宣言する確率。

    - `gated`  : 床を通した手続き ⟹ 構成上 ≤ α。
    - `naive`  : 現行の `p̂ > w/s` そのまま ⟹ **α を大きく超える**（n=6,0.2 で 0.345）。

    α 準拠の判定は**丸める前**の値で行う（`gated` は表示用に 4 桁へ丸めるので、
    丸めが違反を隠しうる ── 0.05004 は round すると 0.05 に見えてしまう）。
    """
    up = crit_upper(n, ratio, alpha)
    gated = 0.0 if up is None else sf(int(round(up * n)), n, ratio)
    k_naive = math.floor(n * ratio) + 1          # p̂ > ratio ⟺ X > n·ratio ⟺ X ≥ floor(n·ratio)+1
    return {"gated": round(gated, 4), "naive": round(sf(k_naive, n, ratio), 4), "alpha": alpha,
            "gated_within_alpha": gated <= alpha}


# --------------------------------------------------------------------------- #
# ③ 盲帯 ── 定理は「支配」と言うのに、実験がそれを示せない領域
# --------------------------------------------------------------------------- #
def blind_band(n: int, ratio: float, alpha: float = 0.05) -> dict:
    """(w/s, crit_upper) の帯 ＝ 真に市場が勝っているのに n では検出できない p の範囲。"""
    up, lo = crit_upper(n, ratio, alpha), crit_lower(n, ratio, alpha)
    return {"n": n, "w_over_s": round(ratio, 4), "p_star": round(ratio, 4),
            "crit_upper": None if up is None else round(up, 4),
            "crit_lower": None if lo is None else round(lo, 4),
            "blind_half_width": None if up is None else round(up - ratio, 4),
            "refutable": lo is not None,
            "type_i": type_i_error(n, ratio, alpha)}


def min_n_for_refutation(ratio: float, alpha: float = 0.05):
    """「非支配」が*言えるようになる*最小 n（最良の観測 p̂=0 ですら証明できない n がある）。

    P(X=0 | Bin(n, ratio)) = (1−ratio)^n ≤ α ⟺ n ≥ log α / log(1−ratio)。
    """
    if not 0.0 < ratio < 1.0:
        return None
    return math.ceil(math.log(alpha) / math.log1p(-ratio))


def min_n_for_margin(ratio: float, delta: float, alpha: float = 0.05,
                     n_max: int = 600, window: int = 20):
    """境界から δ 以内の点を判定できる最小 n（＝ crit_upper − w/s ≤ δ）。

    crit_upper は k/n の階段なので単調でない。よって「そこから先 window 個ずっと満たす」
    最小の n を返す（見かけ上たまたま満たす n を掴まない）。
    """
    ok = []
    for n in range(1, n_max + window + 1):
        up = crit_upper(n, ratio, alpha)
        ok.append(up is not None and up - ratio <= delta + 1e-12)
    for n in range(1, n_max + 1):
        if all(ok[n - 1:n - 1 + window]):
            return n
    return None


# --------------------------------------------------------------------------- #
# ④ 実測地図の再判定 ── 公開済みの ✓ は床を越えているか
# --------------------------------------------------------------------------- #
def load_map(path: str = _MAP_JSON) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def audit(mp: dict, alpha: float = 0.05) -> dict:
    """market_map_results.json の各 (weak, strong) を床で再判定。

    n はタスク数（構造的極・保守側）。trials は**分解能を上げない**ので使わない ──
    それを示すために `bracket_stochastic`（Bin(n·t, ·) の楽観側）も併記する。
    """
    t = int(mp.get("trials", 1))
    rows, retracted = [], 0
    for m in mp["models"]:
        n = len(m["per_task"])
        p_hat = float(m["p_weak"])
        # 構造的か確率的か: per-task solve_rate が 0/1 に張り付くほど構造的（trials は無力）
        rates = list(m["per_task"].values())
        structural = all(r in (0.0, 1.0) for r in rates)
        for pr in m["pairs"]:
            ratio = float(pr["w_over_s"])
            v = verdict(p_hat, n, ratio, alpha)
            # 旧手続きが「何を主張していたか」の履歴。キーは `dominates_pointwise` に改名済み
            # （素の値を読める名前を消して、床を通さない出力経路が KeyError で落ちるようにした）。
            claimed = bool(pr.get("dominates_pointwise", pr.get("dominates", p_hat > ratio)))
            supported = (v == DOMINATES)
            if claimed and not supported:
                retracted += 1
            rows.append({
                "weak": m["weak"], "strong": pr["strong"], "n_tasks": n, "trials": t,
                "p_hat": round(p_hat, 4), "w_over_s": round(ratio, 4),
                "margin": round(p_hat - ratio, 4),
                "crit_upper": (lambda u: None if u is None else round(u, 4))(crit_upper(n, ratio, alpha)),
                "claimed_dominates": claimed, "verdict": v, "supported": supported,
                "per_task_structural": structural,
                # 楽観側（全 n·t 抽出が独立と*仮定*した場合）の臨界値。床には使わない。
                "bracket_stochastic_crit": (lambda u: None if u is None else round(u, 4))(
                    crit_upper(n * t, ratio, alpha)),
            })
    return {"alpha": alpha, "trials": t, "rows": rows,
            "claimed": sum(1 for r in rows if r["claimed_dominates"]),
            "supported": sum(1 for r in rows if r["supported"]),
            "retracted": retracted}


# --------------------------------------------------------------------------- #
# ⑤ 連続スイープ ── 能力差 (p, w/s) 平面を掃いて判定領域を描く
# --------------------------------------------------------------------------- #
def sweep_p(n: int, ratio: float, p_grid, alpha: float = 0.05) -> list:
    """p を連続に掃いて三値判定を返す（＝ロードマップ①の「能力差の連続スイープ」の本体）。"""
    return [{"p": p, "verdict": verdict(p, n, ratio, alpha)} for p in p_grid]


def run(prm: "GapParams | None" = None) -> dict:
    prm = prm or GapParams()
    a, mp = prm.alpha, load_map()
    tiers = [{"strong": name, "w": WEAK_COST, "s": s, "w_over_s": round(WEAK_COST / s, 4)}
             for name, s in STRONG_TIERS]

    bands = [{"strong": t["strong"], "w_over_s": t["w_over_s"],
              "by_n": [blind_band(n, t["w_over_s"], a) for n in prm.n_grid],
              "min_n_refutable": min_n_for_refutation(t["w_over_s"], a),
              "min_n_by_delta": [{"delta": d,
                                  "n": min_n_for_margin(t["w_over_s"], d, a, prm.n_max,
                                                        prm.stability_window)}
                                 for d in prm.delta_grid]}
             for t in tiers]

    au = audit(mp, a)
    n_set = {row["n_tasks"] for row in au["rows"]}
    if len(n_set) != 1:                                   # 地図が不揃いなら見出しの n が意味を失う
        raise ValueError(f"map has heterogeneous task counts: {sorted(n_set)}")
    n_real = n_set.pop()                                  # 実測地図のタスク数
    haiku = next(b for b in bands if b["strong"] == "haiku")
    band_real = blind_band(n_real, haiku["w_over_s"], a)  # n_grid に依存せず実測 n で直接計算
    min_n_ref = haiku["min_n_refutable"]
    min_n_d05 = next(d["n"] for d in haiku["min_n_by_delta"] if d["delta"] == 0.05)
    min_n_d10 = next(d["n"] for d in haiku["min_n_by_delta"] if d["delta"] == 0.10)

    return {
        "params": dataclasses.asdict(prm),
        "tiers": tiers,
        "theorem": "market が flat-strong を Pareto 支配 ⟺ p > w/s（model/market.py）",
        "problem": ("定理は**真の** p の話だが、実測は推定量 p̂ しか持たない。"
                    "現行の実測（market_external.calibrate）は p̂ > w/s を*点推定のまま*二値判定しており、"
                    "境界の近傍では判定が純ノイズになる ── そして「境界に寄せる」とは、その近傍へ行くことである。"),
        "floor": ("H0: p = w/s。支配は P(Bin(n, w/s) ≥ n·p̂) ≤ α のときだけ、"
                  "非支配は P(Bin(n, w/s) ≤ n·p̂) ≤ α のときだけ宣言してよい。間は UNDECIDED。"),
        "variance_note": ("Var(p̂) = [Var_task(p_i) + E[p_i(1−p_i)]/t]/n。第1項は trials で消えない。"
                          "per-task が 0/1 に張り付く実測（構造的能力差）では E[p_i(1−p_i)]=0 となり "
                          "Var(p̂)=p(1−p)/n ＝ **trials の寄与は厳密にゼロ**。保守側としてこの極を床に採る。"),
        "bands": bands,
        "audit": au,
        "sweep_p_at_measured_n": {
            "n": n_real, "strong": "haiku", "w_over_s": haiku["w_over_s"],
            "rows": sweep_p(n_real, haiku["w_over_s"], prm.p_grid, a),
        },
        "headline": {
            "n_measured": n_real,
            "type_i_naive": band_real["type_i"]["naive"],
            "type_i_gated": band_real["type_i"]["gated"],
            "claimed": au["claimed"], "supported": au["supported"], "retracted": au["retracted"],
            "refutable_at_measured_n": band_real["refutable"],
            "min_n_refutable_haiku": min_n_ref,
            "min_n_delta10_haiku": min_n_d10,
            "min_n_delta05_haiku": min_n_d05,
        },
        # 数値は一切ハードコードしない（散文が数値からずれる事故を構造的に不可能にする。
        #  この repo は一度 NOISE.md でそれを踏んでおり、test_generated_docs.py はその床である）
        "finding": (f"境界 p≈w/s に届かないのは「ローカルモデルが皆強い」からでなく、"
                    f"**n={n_real} では境界の近傍がそもそも判定不能**だから。"
                    f"n={n_real}・w/s={haiku['w_over_s']} では下側の枝が空＝"
                    f"**どんな観測でも「非支配」を言えない**（p̂=0/{n_real} でも H0 と両立する）。"
                    f"⟹ ロードマップ①の次の一手は「より弱いモデル探し」ではなく **n を増やすこと**。"
                    f"反証可能性の発生は n≥{min_n_ref}、境界から δ=0.05 の分解能には n={min_n_d05}。"),
        "falsifier": ("床が偽なら: (a) H0 の下で gated 手続きの第一種過誤が α を超える"
                      "（構成上あり得ない ── `type_i.gated ≤ α` を test が固定）、または "
                      "(b) 構造的極（Bin(n,·)）が保守側でない、すなわち真の Var(p̂) が p(1−p)/n を*超える*。"
                      "(b) はタスク間分散が Var_task = p(1−p) を超える時に起こるが、Bernoulli の分散は "
                      "p(1−p) が上限なので起こり得ない。⟹ 床は保守側であることが証明可能。"),
    }


# --------------------------------------------------------------------------- #
def _fmt(x) -> str:
    return "—" if x is None else str(x)


def _md(r: dict) -> str:
    h, au = r["headline"], r["audit"]
    L = ["# 能力差の連続スイープ ── 境界 p\\*=w/s の**判定分解能の床**",
         "",
         "支配定理（[`MARKET.md`](MARKET.md)）は **p > w/s** で市場が単一モデルを Pareto 支配すると言う。"
         "ロードマップ①は「境界(p≈w/s) に寄せて実測」する計画だった。本モデルはその計画に**先に床を課す**。"
         "生数値 [`gap_results.json`](gap_results.json)。",
         "",
         f"> {r['finding']}",
         "",
         "## 問題 ── 定理は真の p の話、実験が持つのは p̂",
         f"- {r['problem']}",
         f"- **床**: {r['floor']}",
         f"- **分散**: {r['variance_note']}",
         "",
         f"## ① 現行手続きの第一種過誤（n={h['n_measured']}・w/s=0.2・α=0.05）",
         "| 手続き | H0（真に境界上・利得ゼロ）で「支配」と誤宣言する確率 |",
         "|---|---|",
         f"| 現行 `p̂ > w/s`（点推定の二値判定） | **{h['type_i_naive']}** |",
         f"| 床を通した判定 | **{h['type_i_gated']}** (≤ α) |",
         "",
         f"つまり公開済みの ✓ は、真に利得ゼロのモデルに対しても **{h['type_i_naive']:.0%} の確率で立つ**。",
         "",
         "## ② 公開済み支配地図の再判定"
         f"（[`../experiments/MARKET_MAP.md`](../experiments/MARKET_MAP.md)・n={h['n_measured']}・trials={au['trials']}）",
         "| 弱モデル | 強ティア | p̂ | w/s | 余裕 p̂−w/s | 支配に要る p̂ | 現行 | **床を通すと** |",
         "|---|---|---|---|---|---|---|---|"]
    for row in au["rows"]:
        mark = {"DOMINATES": "**支配**", "DOES_NOT_DOMINATE": "**非支配**", "UNDECIDED": "**判定不能**"}[row["verdict"]]
        L.append(f"| {row['weak']} | {row['strong']} | {row['p_hat']} | {row['w_over_s']} | "
                 f"{row['margin']} | {_fmt(row['crit_upper'])} | "
                 f"{'✓' if row['claimed_dominates'] else '—'} | {mark} |")
    L += ["",
          f"**主張 {au['claimed']} 件のうち床を越えるのは {au['supported']} 件・"
          f"{au['retracted']} 件は判定不能**（＝観測は境界上の H0 と両立する）。"
          "定理が偽なのではない。*実測がその主張を支える標本を持っていない*。",
          "",
          "## ③ 盲帯 ── 定理は「支配」と言うのに実験が示せない領域",
          "",
          "| 強ティア | w/s | n | 支配に要る p̂ | 盲帯の幅 | 非支配を言えるか |",
          "|---|---|---|---|---|---|"]
    for b in r["bands"]:
        for bn in b["by_n"]:
            L.append(f"| {b['strong']} | {b['w_over_s']} | {bn['n']} | {_fmt(bn['crit_upper'])} | "
                     f"{_fmt(bn['blind_half_width'])} | {'✓' if bn['refutable'] else '**不可**'} |")
    L += ["",
          "「盲帯の幅」＝ w/s から、支配を宣言できる最小の p̂ までの距離。"
          "**この帯の中では、市場が本当に勝っていても実験はそう言えない。** n が増えると帯は 1/√n で縮む。",
          "",
          "## ④ 境界に寄るのに必要な n（＝ロードマップ①の実際の値段）",
          "",
          "| 強ティア | w/s | 反証可能になる最小 n | δ≤0.30 | δ≤0.20 | δ≤0.10 | δ≤0.05 |",
          "|---|---|---|---|---|---|---|"]
    for b in r["bands"]:
        by_d = {d["delta"]: d["n"] for d in b["min_n_by_delta"]}
        L.append(f"| {b['strong']} | {b['w_over_s']} | **{_fmt(b['min_n_refutable'])}** | "
                 + " | ".join(_fmt(by_d[d]) for d in (0.30, 0.20, 0.10, 0.05)) + " |")
    sw = r["sweep_p_at_measured_n"]
    und = [x["p"] for x in sw["rows"] if x["verdict"] == UNDECIDED]
    dom = [x["p"] for x in sw["rows"] if x["verdict"] == DOMINATES]
    nd = [x["p"] for x in sw["rows"] if x["verdict"] == NOT_DOMINATES]
    L += ["",
          f"## ⑤ 能力差の連続スイープ（実測の n={sw['n']}・→{sw['strong']}・w/s={sw['w_over_s']}）",
          "",
          "p を 0→1 に連続に動かし、床を通した判定がどこで変わるかを見る:",
          "",
          f"- **非支配**と言える p: {('なし（下側の枝が空）' if not nd else f'{min(nd)}〜{max(nd)}')}",
          f"- **判定不能**な p: {min(und)}〜{max(und)}"
          f"（幅 {round(max(und) - min(und), 2)} ＝ p 軸のほぼ {round((len(und) / len(sw['rows'])) * 100)}%）",
          f"- **支配**と言える p: {min(dom)}〜{max(dom)}",
          "",
          f"境界は w/s={sw['w_over_s']} にあるのに、判定不能帯は {min(und)}〜{max(und)} に広がっている。"
          "**「境界に寄せる」ことは、判定不能帯の奥へ入っていくことに等しい。**"
          "より弱いモデルを探すほど、n=6 のままでは*何も言えなくなる*。",
          "",
          "## 含意 ── ロードマップ①の書き換え",
          "- ✗ 「より弱いモデル / 難タスクで境界に寄せて実測」（n=6 のまま） → **反証不能な観測しか出ない**。",
          f"- ✓ **まず n を増やす**。反証可能性の発生 n≥{h['min_n_refutable_haiku']}、"
          f"境界から δ=0.10 の分解能に n={h['min_n_delta10_haiku']}、δ=0.05 なら "
          f"n={h['min_n_delta05_haiku']}（→haiku）。",
          "- ✓ **trials では買えない**。per-task が 0/1 に張り付く（＝能力差が構造的）限り、"
          "trials の分散寄与は厳密にゼロ。NOISE.md が mesh 軸で出した「trials より先に n」と同じ結論。",
          "",
          "## 反証条件",
          f"- {r['falsifier']}"]
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "gap_results.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "GAP.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    h = r["headline"]
    print(f"type-I error @ n={h['n_measured']}, w/s=0.2: naive={h['type_i_naive']} "
          f"vs gated={h['type_i_gated']} (alpha=0.05)")
    print(f"published map: claimed={h['claimed']} supported={h['supported']} "
          f"RETRACTED={h['retracted']}")
    print(f"refutable at n={h['n_measured']}? {h['refutable_at_measured_n']}  "
          f"(need n>={h['min_n_refutable_haiku']} to say 'does not dominate' at all)")
    print(f"n needed to resolve within 0.05 of the boundary (->haiku): {h['min_n_delta05_haiku']}")
    print(f"wrote {os.path.join(out_dir, 'gap_results.json')} and GAP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
