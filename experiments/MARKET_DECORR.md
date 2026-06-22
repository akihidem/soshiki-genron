# 弱モデル mesh の概念実証 — 誤りは脱相関するか（union > 単独最良か）

多様なモデルの誤りが*別タスク*に出れば、pair-union が単独を超える＝ML アンサンブル原理＝『多様性 mesh』組織の種。誤りが起きる task で測る（trials=3）。

## solve_rate 行列（どのモデルがどこで誤るか）
| task | gemma4:e2b | haiku | sonnet |
|---|---|---|---|
| roman | 0.333 | 1.0 | 1.0 |
| calc | 0.0 | 1.0 | 1.0 |
| atoms | 0.0 | 1.0 | 1.0 |
| negabinary | 1.0 | 0.667 | 1.0 |
| wildcard_plus | 0.667 | 1.0 | 1.0 |

## ペア union vs 単独最良（gain>0 ＝ 脱相関で mesh が単独を超える）
| ペア | union | 単独最良 | gain | 相補タスク（片方だけ解く） |
|---|---|---|---|---|
| gemma4:e2b + haiku | 1.0 | 0.933 | **+0.067** | roman, calc, atoms, negabinary, wildcard_plus |
| gemma4:e2b + sonnet | 1.0 | 1.0 | **+0.0** | roman, calc, atoms, wildcard_plus |
| haiku + sonnet | 1.0 | 1.0 | **+0.0** | negabinary |

## 読み
- **gain>0 のペアがあれば mesh 原理は実在**：異種が互いの盲点を覆い、組み合わせが単独を超える。
- 相補タスクが在る＝誤りが*別 instance* に出る（脱相関）＝mesh の燃料。
- frontier(opus/codex) は誤らずここに出ない（§5）＝mesh は能力の縁でだけ点火（弱い所では*実在*）。
