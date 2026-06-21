# 実証: エージェント組織シミュレータ — flat vs hierarchy vs market（F3 接地）

実 LLM エージェント（sonnet）に相互依存タスク（設計→実装→テスト）を 3 構造で組織させ、コスト（コール数）・品質（静的検査）・**正しさ（sandbox 実行）**を測った。タスク 3 件。生数値 [`org_sim_results.json`](org_sim_results.json)・生成物 [`org_sim_artifacts.json`](org_sim_artifacts.json)。

## 集計
| 構造 | 平均コール（コスト） | 平均品質(静的) | 平均正しさ(実行) | 総コール |
|---|---|---|---|---|
| flat | 3.0 | 1.0 | 0.963 | 9 |
| hierarchy | 5.0 | 1.0 | 1.0 | 15 |
| market | 4.0 | 1.0 | 0.889 | 12 |

## 読み
- hierarchy/market のコール数 ＞ flat（調整OH）。**品質・正しさが同等以下なら → flat が安い**（解析 F3・tehai A/B を実エージェントで支持）。
- market は均質な組織では bidding OH のみで heterogeneity の便益が無い → flat に劣るはず（解析の予測）。
- 正しさ（実行＝tests が通る割合）は静的 coverage より厳しい本物の品質。

## タスク別
| task | 構造 | calls | quality(静的) | 正しさ(実行) | tests |
|---|---|---|---|---|---|
| textutil | flat | 3 | 1.0 | 0.889 | 16/18 |
| textutil | hierarchy | 5 | 1.0 | 1.0 | 3/3 |
| textutil | market | 4 | 1.0 | 0.667 | 2/3 |
| numutil | flat | 3 | 1.0 | 1.0 | 3/3 |
| numutil | hierarchy | 5 | 1.0 | 1.0 | 3/3 |
| numutil | market | 4 | 1.0 | 1.0 | 3/3 |
| timeutil | flat | 3 | 1.0 | 1.0 | 3/3 |
| timeutil | hierarchy | 5 | 1.0 | 1.0 | 17/17 |
| timeutil | market | 4 | 1.0 | 1.0 | 3/3 |

## 妥当性
- 品質は静的 coverage ＋ **正しさは sandbox 実行**（unshare で no-net/no-pid 隔離・generated code を実行）。構造の実装は最小（flat=共有黒板逐次・hierarchy=管理者2コール・market=bidding 1コール）。コストはコール数の代理。少標本。
