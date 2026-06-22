# 実証: バグ修復の脱相関 — frontier の縁を*修復*で探す

生成では frontier 0 失敗・脱相関ゼロ。*修復*（微妙なバグを見つけ直す）は難しく、ベンダで違うバグを捕まえうる。union>単独 なら **補完能力 mesh が frontier の縁で点火**（PAPER §6.5）。

## 修復成功（1=全gold通過）
| task | opus | codex | sonnet |
|---|---|---|---|
| edit_distance | 1 | 1 | 1 |
| re_match | 1 | 1 | 1 |
| fraction | 1 | 1 | 1 |
| calc3 | 1 | 1 | 1 |

per-model 修復率: {'opus': 1.0, 'codex': 1.0, 'sonnet': 1.0}

## ペア union vs 単独最良（gain>0 ＝ frontier で mesh 点火）
| ペア | union | 単独最良 | gain | 相補（片方だけ直す） |
|---|---|---|---|---|
| opus + codex | 1.0 | 1.0 | **+0.0** | — |
| opus + sonnet | 1.0 | 1.0 | **+0.0** | — |
| codex + sonnet | 1.0 | 1.0 | **+0.0** | — |

## 読み
- **gain>0 ＝ frontier 異種ベンダでも修復は脱相関**＝補完能力 mesh が*実タスク級*で点火（生成では出なかった創発）。
- gain≈0 ＝ 修復でも frontier は同じ所を直す/直せない（相関）＝縁はさらに先。少標本・trials=1。
