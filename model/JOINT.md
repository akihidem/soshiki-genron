# 結合最適 — 構造×統治膜の分離可能性を反証する

design_map の「構造と膜は独立」を検証。構造ごとの膜の張りにくさ gov_factor={'hierarchy': 0.7, 'flat': 1.0, 'market': 1.5}（階層=集中で安い／市場=分散で高い）を入れ、(構造, 膜) を同時最適化。密度 ρ=0.4。生数値 [`joint_results.json`](joint_results.json)。

## 主結果: 分離可能性が破れたセル = **1 / 9**

各セル = 分離最適の構造 → 結合最適の構造（★=食い違い）。

| stakes \ 通信 | human≈3.0 | transition≈1.0 | AI≈0.1 |
|---|---|---|---|
| **low≈0.8** | hierarchy→hierarchy | market→market | flat→flat |
| **mid≈8** | hierarchy→hierarchy | market→market | flat→flat |
| **high≈40** | hierarchy→hierarchy | market→hierarchy ★ | flat→flat |

## 読み
- ★のセルでは、**統治しやすさが効率を上書きする** — 効率最適でない構造が、膜が安いがゆえに結合では選ばれる。
- 典型: 高 stakes（厚い膜が要る）で、市場のように膜が高くつく構造が、より統治しやすい構造に負ける。
- ★が1つでもあれば design_map の**分離可能性は偽**（本モデル下）。今回 1 個。

## 妥当性
- gov_factor は第一原理的だが*仮定*（集中度↔統治しやすさ）。結論は質的（分離が破れうる・破れる向き）＋感度で読む。
- 調整コストと統治損失は同一の抽象コスト単位として加算。相対スケールは仮定。
- [`../docs/foundations.md`](../docs/foundations.md) §5 の「最適性 vs 可読性」が、構造選択そのものに食い込むことを示す。
