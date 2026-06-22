# 通信コスト較正 — coordination.py を org_sim 実測で接地

coordination.py（解析）のコストはコール数でなく抽象単位だった。org_sim（実エージェント）のコール数で **mgr_overhead** と **c_comm** を接地する。

## 実測コール数（org_sim）
- flat=3.0 / hierarchy=5.0 / market=4.0

## 接地
- **mgr_overhead = hierarchy − flat = 2.0**（管理者の分解+統合2コール）／model 既定 2.0 と **一致**。
- market OH = market − flat = 1.0（入札1コール）。
- **c_comm（コール単位）≈ 0.0**: flat の調整は共有文脈経由＝追加コール無し。→ AI は「c_comm 低 → flat 勝ち」レジーム。

## 検証: 測定 mgr_overhead を入れた winner() の c_comm スイープ
| c_comm | winner | flat | hierarchy | market |
|---|---|---|---|---|
| 0.0 | **flat** | 2.4 | 8.4 | 3.6 |
| 0.01 | **flat** | 2.664 | 8.546 | 3.84 |
| 0.05 | **flat** | 3.72 | 9.132 | 4.8 |
| 0.1 | **flat** | 5.04 | 9.864 | 6.0 |
| 0.3 | **flat** | 10.32 | 12.792 | 10.8 |
| 1.0 | hierarchy | 28.8 | 23.04 | 27.6 |

→ c_comm≈0 で winner = **flat**（org_sim の flat 勝ちと一致）。

## 含意
- AI 設定では通信が*共有文脈*で安く（コール単位 c_comm≈0）、階層の mgr_overhead が死荷重になり flat が勝つ。解析 coordination.py の低-c_comm レジームが実測で接地された。

## 反証条件
- 測定 mgr_overhead が model 既定から大きく外れる、または c_comm≈0 で winner が flat 以外なら本接地は崩れる（coordination.py の AI レジーム想定が偽）。
