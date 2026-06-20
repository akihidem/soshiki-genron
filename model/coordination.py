"""調整コストモデル — 構造の総コストを c_comm の関数として計算する。

第一原理（Galbraith の情報処理ビュー / Malone の調整コスト論）から、3つの純粋な
調整戦略を、共通の単位（コスト）で組み立てる:

    総コスト(構造, c_comm) = c_comm · 通信量(構造) + 構造オーバーヘッド(構造) + 誤りコスト(構造)

- c_comm … 通信1単位あたりのコスト（掃引する変数。人間=高、AI=低）
- 通信量  … その構造が目標を調整するのに要するメッセージ数
- 構造OH  … 調整専従ノード（管理者）や取引の、通信非依存な構造コスト
- 誤りコスト … 検証様式の差（自部門レビューは盲点を共有し流出 / 外部検証はノードで捕捉）

各構造の通信量がどの量に比例するかが核心:
- flat（平ら/共有状態）: 相互依存の **辺の数 E** に比例（各依存を直接調整）
- hierarchy（階層）     : **エージェント数 N** に funnel（E→N）。ただし管理者OHと残留ルーティングを払う
- market（市場/競売）   : 入札ラウンド × N。取引OHを払うが、最適割り当てで誤りを減らす

→ c_comm が高く E≫N のとき階層が有利（希少な通信を節約）。c_comm が下がると
  c_comm·E が縮み、階層の管理者OH（通信非依存）が死荷重になり flat/market が逆転する。
  これは「測れる仮説」であって、結果はパラメタから創発する（出来レースにしない）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Params:
    n: int = 12                  # agents / tasks
    density: float = 0.4         # interdependency density in [0,1] -> edges
    span: int = 4                # manager span of control (-> #coordinators)
    mgr_overhead: float = 2.0    # structural cost per coordinator (comm-INDEPENDENT)
    txn_overhead: float = 0.1    # market transaction cost per task
    market_rounds: int = 2       # bidding rounds
    hier_routing: float = 0.1    # residual cross-edge routing kept inside a hierarchy
    # --- verification / error axis (the F5 thesis) ---
    p_defect: float = 0.1        # prob a unit carries a blind-spot defect
    escape_cost: float = 8.0     # cost when a blind-spot ships (self-review misses it)
    rework_cost: float = 2.0     # cost when caught at the node (external verification)
    market_match_gain: float = 0.3  # fraction of defects avoided by best-agent matching
    same_error: bool = False     # if True, all structures pay the SAME error cost
                                 # (isolates the pure coordination-cost crossover)

    def edges(self) -> float:
        return self.density * self.n * (self.n - 1) / 2.0

    def coordinators(self) -> int:
        return max(1, math.ceil(self.n / self.span))

    def expected_defects(self) -> float:
        return self.p_defect * self.n


def _bundle(comm: float, overhead: float, error: float) -> dict:
    return {"comm": round(comm, 4), "overhead": round(overhead, 4),
            "error": round(error, 4), "total": round(comm + overhead + error, 4)}


def _err(p: Params, structure: str) -> float:
    """Error cost by verification mode. With same_error, neutralize the axis."""
    d = p.expected_defects()
    if p.same_error:
        return d * p.rework_cost
    if structure == "hierarchy":
        # self-review shares blind spots -> the defect ships downstream
        return d * p.escape_cost
    if structure == "market":
        # external + best-agent matching avoids a fraction of defects
        return (d * (1.0 - p.market_match_gain)) * p.rework_cost
    # flat: every node externally verified -> caught at the node, cheap rework
    return d * p.rework_cost


def cost_flat(p: Params, c_comm: float) -> dict:
    comm = c_comm * p.edges()                 # every interdependency edge coordinated directly
    return _bundle(comm, 0.0, _err(p, "flat"))


def cost_hierarchy(p: Params, c_comm: float) -> dict:
    # funnels E direct edges into N report-links (+ a residual cross-routing tax)
    comm = c_comm * (p.n + p.hier_routing * p.edges())
    overhead = p.mgr_overhead * p.coordinators()   # coordinators don't produce work
    return _bundle(comm, overhead, _err(p, "hierarchy"))


def cost_market(p: Params, c_comm: float) -> dict:
    comm = c_comm * p.market_rounds * p.n
    overhead = p.txn_overhead * p.n
    return _bundle(comm, overhead, _err(p, "market"))


STRUCTURES = {
    "flat": cost_flat,
    "hierarchy": cost_hierarchy,
    "market": cost_market,
}


def costs(p: Params, c_comm: float) -> dict:
    return {name: fn(p, c_comm) for name, fn in STRUCTURES.items()}


def winner(p: Params, c_comm: float) -> tuple[str, float]:
    """The cost-minimizing structure at this communication cost.
    Deterministic tie-break by STRUCTURES order (flat < hierarchy < market)."""
    cs = costs(p, c_comm)
    best = min(STRUCTURES, key=lambda k: (cs[k]["total"], list(STRUCTURES).index(k)))
    return best, cs[best]["total"]
