# 処方マップ — タスク条件 → 推奨(構造, 統治膜)

二つの計測の合成（密度 ρ=0.4 固定）。各セル = (推奨構造 / 膜の厚み m*)。

| stakes \ 通信コスト | human≈3.0 | transition≈1.0 | AI≈0.1 | deep-AI≈0.03 |
|---|---|---|---|---|
| **low≈0.8** | hierarchy / m*=0.0 | market / m*=0.0 | flat / m*=0.0 | flat / m*=0.0 |
| **mid≈8** | hierarchy / m*=0.658 | market / m*=0.658 | flat / m*=0.658 | flat / m*=0.658 |
| **high≈40** | hierarchy / m*=1.0 | market / m*=1.0 | flat / m*=1.0 | flat / m*=1.0 |

## 読み
- 横（通信コスト低下＝AI化）: 構造は **hierarchy → market → flat** へ（第一の計測）。
- 縦（stakes 上昇）: 統治膜 **m* が 0 → 部分 → 1** へ厚くなる（第二の計測）。
- 右下（AI域・高 stakes）= **平ら/市場な機構に厚い統治膜** ＝ テーゼ「AIネイティブ機構＋人間統治膜」の具体形。
- 左上（人間域・低 stakes）= 階層で膜不要、という*人間組織の既定*に一致（モデルの sanity check）。

## 妥当性
- 構造選択と膜の厚みは分離可能と仮定（第一近似）。 実際は相互作用がありうる（市場は監督点が分散し膜を張りにくい等）→ **検証済み（[`JOINT.md`](JOINT.md)）: 高 stakes で分離が破れる（市場→階層、1/9 セル）**。
- 各軸の限界は [`first-measurement.md`](../docs/first-measurement.md) / [`second-measurement.md`](../docs/second-measurement.md) を参照。
