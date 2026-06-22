# 支配地図 — 複数ローカル弱モデルを (p_weak, w/s) 平面に置く

支配定理 p\*=w/s（[`../model/MARKET.md`](../model/MARKET.md)）に対し、ローカル弱モデル群の 完全解率 p_weak を測り、各 weak→strong ペアが支配領域に入るかを地図化（trials=2）。

## p_weak と支配（✓ = market が flat-strong を Pareto 支配 ＝ p>w/s）
| 弱モデル | p_weak | →haiku (w/s=0.2) | →sonnet (0.067) | →opus (0.013) |
|---|---|---|---|---|
| gemma4:e2b | **0.8333** | ✓ | ✓ | ✓ |
| gemma4:latest | **0.5** | ✓ | ✓ | ✓ |
| gemma4-chat:latest | **0.4167** | ✓ | ✓ | ✓ |

## per-task solve_rate（1.0 到達率）— どのタスクで能力差が出るか
| 弱モデル | clamp | leap | revwords | roman | intervals | wildcard |
|---|---|---|---|---|---|---|
| gemma4:e2b | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| gemma4:latest | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| gemma4-chat:latest | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | 0.0 |

## 読み
- 弱モデルが p>w/s（特に最も厳しい →haiku の閾値 0.2）を超える限り、市場は単一モデルを支配。
- ローカル小型モデルが全て高 p（≫0.2）に固まるなら → 支配は頑健・境界(p≈0.2)は更に難しいタスクでのみ。
- per-task で 0/1 に割れるタスクが*構造的*な能力差の在処（市場が高ティアを呼ぶ理由）。
