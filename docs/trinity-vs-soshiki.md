# TRINITY × soshiki — 後者の「予測力の優位」の検証

外部の実装論文 **TRINITY: An Evolved LLM Coordinator**（[arXiv:2512.04695](https://arxiv.org/abs/2512.04695), ICLR 2026, Xu et al.）を、本研究の解析モデルで読み直し、「soshiki は『AI 協調がいつ問題を解けるか』を*当てる*力で優位か」を検証した記録。文献ログは [`literature.md`](literature.md) のクラスタ E に対応。

> **一行**: 解かせる力＝TRINITY、解ける条件を*説明する*力＝soshiki。後者の優位は **説明レイヤーに限り検証済み**。ただし「予測」ではなく「retrodiction（事後再現）」に格下げ。

---

## 検証対象の主張
soshiki は閉形式の法則で、複数 LLM の協調が単一モデルを上回る条件を*事前に*言い当てられる ── という「予測力の優位」。

## 方法
1. soshiki の §5 市場モデル（`model/market.py`）を**実走**し、予測を出力として確認（解釈の又聞きでなく一次）。
2. TRINITY の観測（プール構成・2レジームの gain）と突き合わせ。
3. 敵対的に潰す（後付けでないか・他理論で十分でないか・自前実証は足りるか）。

## 一次根拠 — `python3 model/market.py` 生出力
```
threshold: 市場が flat-strong を Pareto 支配 ⟺ p > w/s（安いティアの完全解率 > コスト比）
①homogeneous (all sonnet)            market=1.0     dominates=False
②frontier-hetero (haiku/sonnet/opus) market=1.0     dominates=False
③large-gap (gemma×haiku)             market=0.3112  dominates=True
```
決定的モデルゆえ再走しても出力不変（`git status` で確認、tree 非汚染）。支配定理 **p\*=w/s**・解析 0.533 == 実測 0.533（[`../model/MARKET.md`](../model/MARKET.md)）。

## TRINITY の2レジーム ↔ soshiki の該当行
| TRINITY 実測 | soshiki の該当行 | 一致 |
|---|---|---|
| 広い異質プール（GPT-5/Gemini/Claude＋Gemma-27B/DeepSeek-32B/Qwen-32B×2）: Trinity **0.615** > 単一最良 **0.465** | **③ large-gap → dominates=True** | ✓ |
| 高難度 V6 で進化が **open を切捨て closed 3 に収束**: Trinity **86.2** vs GPT-5 単体 **83.8** | **①② → dominates=False**（w=s で p\*→1、安いティア不要） | ✓✓ |

→ **TRINITY が CMA-ES 探索で発見した「フロンティアでは安いモデルを捨てる」を、soshiki の一行閾値 p\*=w/s が*そのまま*演繹で出す。** これが「優位」の実体＝説明的圧縮。

---

## ✅ 検証された部分
- soshiki は narrative でなく**反証条件つき法則**（`MARKET.md`「p>w/s でも市場が支配しなければ偽」、解析==実測で自己整合）。
- その法則が **TRINITY に1パラメタも fit せず両レジーム＋収束方向を retrodict**。→ 説明・予測力の優位は本物。
- 否定側（フロンティア/均質→gain≈0）は本研究の**最も頑健な自前計測**: SWEBENCH +0.042→**撤回**→0（[`../experiments/SWEBENCH_ALL.md`](../experiments/SWEBENCH_ALL.md)）／REPAIR +0.0／DECORR **−0.083**／XVS は弱モデルでだけ +0.067。ノイズを自分で撤回する規律つき。

## ❌ 過大だった部分（初回主張の自己反証）
1. **予言でなく retrodiction**: soshiki モデル(2026-06-21〜22)は TRINITY 論文(2025-12)より後。独立開発・未 fit だが「事前に当てた」ではない。
2. **diversity→gain 自体は ML ensemble 理論と重複**（DECORR が自認）。soshiki 固有は*コスト閾値 p\*=w/s と execution-grounded routing*であって diversity 洞察そのものではない。
3. **肯定側の自前 empirics は薄い**: MARKET_GAP_HARD は market 0.367@1.0 で支配を示すが実エスカレーションは6中1件・trials=1、ORG_SIM_HETERO は天井交絡で便益ゼロ。→ **肯定レジームは TRINITY（0.615 vs 0.465・査読済・compute 整合）の方が強く実証している**。
4. **核心 bet「execution > model-judgment」は未検証**: soshiki は §9 で「静的品質は盲目」を測り routing を実行接地にしたが、*execution-grounded Verifier の TRINITY > 現 TRINITY* は誰も走らせていない＝standing bet。TRINITY の "Verifier" は ACCEPT/REVISE の言語判定のみ（実行非接地）。

## 判定（net）
**後者の優位は「説明レイヤーに限り検証済み」。** soshiki は free-parameter ゼロの閉形式法則で TRINITY の挙動を retrodict し、CMA-ES が探索で得た結論を演繹で出す ── ここは確かに勝つ。だが (a) 予言でなく retrodiction、(b) 中核 diversity 洞察は ensemble 理論と共有、(c) 肯定レジームの実証は TRINITY の方が強い、(d) 最鋭の execution>judgment は未検証。

→ **「解かせる力＝TRINITY、解ける条件を説明する力＝soshiki」は維持。ただし "予測する" は "retrodict する" に格下げ。**

## next（優位を「予測」に昇格させる唯一の道）
**execution-grounded Verifier の TRINITY を実際に走らせ、現 TRINITY（model-judgment Verifier）を超えるか測る。** 超えれば soshiki §5+§9 の core bet が*事前予測*として立証され、優位が説明レイヤーから実証レイヤーへ昇格する。外れれば §5 の検証ルーティングの効きが過大評価だったと判明する（どちらでも前進）。

## 信頼度・限界
- soshiki 側: 解析モデルは一次（実走）。肯定レジームの実 LLM 実証は n 小・trials=1・非有意（自認）。
- TRINITY 側: 数値は arXiv HTML（要約モデル経由）＝図表 eyeball 未。「open 切捨て収束」「0.465 vs 0.838 の config 差」は PDF 表確認まで断定保留。
- この検証は retrodiction の構造一致であり、因果や ex-ante 予測の証明ではない。
