# 難易度ラダー — 能力レンジ全体で帯を実測分類（barely-opus / impossible まで）

4ティア（sonnet < opus < codex）を検算済み難タスクに当て、各タスクを *最強の解けるティア* で分類（trials=2・gold は外部正解）。市場の支配定理は強ティアが解ける(p_strong=1)前提 ── impossible 帯はその前提が崩れる所。

## タスク別 solve_rate（1.0到達率）と帯
| task | sonnet | opus | codex | 最安の解き手 | 帯 |
|---|---|---|---|---|---|
| count_pal | 1.0 | 1.0 | 1.0 | sonnet | **easy** |
| calc_iv | 0.5 | 1.0 | 1.0 | sonnet | **easy** |

## エスカレーション市場の挙動（特に誰も解けない時）
| task | 梯子（model:solve_rate） | 市場コスト | 解けたティア | 最良正しさ |
|---|---|---|---|---|
| count_pal | sonnet:1.0 | 3.0 | sonnet | 1.0 |
| calc_iv | sonnet:0.5 → opus:1.0 | 18.0 | opus | 1.0 |

## 読み
- **barely-opus** 帯が存在すれば、frontier 内に勾配があり ②（frontier 異種）でも市場が効きうる（haiku/sonnet で試し opus へ）。
- **impossible** 帯では市場は全ティアを払い（最大コスト）正しさ<1 ── **支配定理の p_strong=1 前提が崩れ、市場は高コストで未解決**。＝「能力の天井を越えた仕事は、どの組織構造でも金を捨てるだけ」。
- 非標準ツイスト（wildcard+ の 1-or-more・negabinary）は memorized 解を壊す ── frontier を分離できるか。

## 妥当性
- gold は固定外部正解（参照実装で検算済）。少標本（trials 小）・gemma の cold-start は trials で緩和。コスト比は定価の代理。
