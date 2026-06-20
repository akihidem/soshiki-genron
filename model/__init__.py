"""② 実験基盤の胚 — 組織構造のコストをモデル化し計測する。

coordination: 通信コスト c_comm の関数として、平ら/階層/市場の各構造の
総コスト（通信 + 構造オーバーヘッド + 誤り）を第一原理から計算する決定的モデル。
sweep: c_comm（と相互依存密度）を掃引し、どの構造が最小コストかの交差点・相図を測る。

第一原理「モデルと実験による計測」の最初の具体化。tehai の A/B（2点観測）を曲線へ一般化し、
foundations.md F3「階層＝帯域削減装置→通信が安いと惰性」と Malone「調整コスト低下→市場化」を
反証可能な計測にする。
"""

from .coordination import (
    Params, cost_flat, cost_hierarchy, cost_market, winner, STRUCTURES,
)

__all__ = ["Params", "cost_flat", "cost_hierarchy", "cost_market", "winner", "STRUCTURES"]
