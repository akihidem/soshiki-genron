# open-ended mesh — cross-vendor 合成は単独を超えるか（LLM-judge・gold 無し領域）

生成: opus + codex／合成: opus が両者を merge／判定: opus, codex（A=gen0, B=gen1, **C=合成**・判定者は知らない）。主観的（judge bias）だが checkable コーディングが届かない縁の代理。

## 平均 synthesis gain（C − max(A,B)）= **+0.833**
| task | A | B | **C(合成)** | 単独最良 | gain |
|---|---|---|---|---|---|
| Design a token-bucket rate limiter for a web API: the public... | 3.0 | 3.5 | **4.5** | 3.5 | +1.0 |
| Cache results of an expensive idempotent function in a multi... | 3.5 | 4.0 | **4.5** | 4.0 | +0.5 |
| Design a backoff-and-retry policy for calls to a flaky downs... | 3.5 | 3.5 | **4.5** | 3.5 | +1.0 |

## 読み
- **gain>0 なら open-ended 領域で cross-vendor 合成が単独を超える**＝mesh が縁で点火（主観評価だが）。
- gain≈0/負なら合成は冗長 or judge が長さ等に釣られた可能性。**judge bias（自作びいき・長さびいき）に注意**＝この計測自体が交絡しうる（§9）。
