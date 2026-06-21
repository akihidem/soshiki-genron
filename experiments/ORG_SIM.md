# 実証: エージェント組織シミュレータ — flat vs hierarchy（F3 接地）

実 LLM エージェント（sonnet）に相互依存タスク（設計→実装→テスト）を 2 構造で組織させ、コスト（コール数）と品質（静的検査）を測った。タスク 2 件。生数値 [`org_sim_results.json`](org_sim_results.json)。

## 集計
| 構造 | 平均コール（コスト） | 平均品質 | 総コール |
|---|---|---|---|
| flat | 3.0 | 1.0 | 6 |
| hierarchy | 5.0 | 0.666 | 10 |

## 読み
- hierarchy のコール数 ＞ flat（管理者OH）。**品質が同等以下なら → flat が安い（解析 F3・tehai A/B を実エージェントで支持）**。
- hierarchy の品質が*明確に高い*なら、管理者の統合がOHを正当化（構造の価値）。

## タスク別
| task | 構造 | calls | quality | impl_cov | test_cov |
|---|---|---|---|---|---|
| textutil | flat | 3 | 1.0 | 1.0 | 1.0 |
| textutil | hierarchy | 5 | 0.333 | 0.333 | 0.333 |
| numutil | flat | 3 | 1.0 | 1.0 | 1.0 |
| numutil | hierarchy | 5 | 1.0 | 1.0 | 1.0 |

## 妥当性
- 少標本・品質は静的検査（実行せず＝coverage/consistency の代理・正しさ自体は未検証）。構造の実装は最小（flat=共有黒板の逐次・hierarchy=管理者2コール）。コストはコール数の代理。
