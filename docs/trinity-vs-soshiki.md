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

---

## 追記 (実測 2026-06-23): 精度を上げる lever の検証 — [`../experiments/config_mesh.py`](../experiments/config_mesh.py)
「cost度外視で生成物の質を上げるなら frontier 並列 mesh / loop はどうか」を local model（qwen2.5-coder:7b ほか）で matched-budget A/B ＋ held-out 採点で実測。

- **blind config 散らし(B) vs 同 config 反復(A) = gain 0**。盲目反復に上乗せ無し（各試行が前の失敗を見ないから）。
- **粗 feedback loop（p/n だけ返す）= むしろ悪化**。前の壊れたコードを次に渡し、誤りが連鎖して 0 に固着（negabinary 0.143→0.0、calc3 0.667→0.0）。
- **rich feedback loop（失敗した可視ケースの「入力==期待」を返す）＋ held-out 採点 = genuine に効く**。negabinary が 0.25→1.0(iter4) に登り **held-out も同時に 1.0**＝ごまかしでない。同じタスクが粗→悪化・rich→解決＝**feedback の質だけで「壊す→解く」が反転**。
- **Goodhart = 実 0 件**。可視を1.0にした全タスクで held-out も1.0（gap=0）。「可視は通すが held-out で落ちる」は皆無＝rich feedback は Goodhart-safe（この規模・タスク型では）。
- **律速は feedback でなく能力天井**。calc（式パーサ）・wildcard_plus は「入力==期待」を見せても平ら＝rich feedback は*直せる間違い*を直すだけで能力は足さない。

→ **総合**: rich-loop（agent の潜在能力を引き出す＝§9「検証の質」）⊕ escalation（天井超えで上位 agent へ＝§5）が、loop の*内側/外側*として相補。＝meshflow の within-tier/across-tier の実証的裏付け。ユーザ案「分解片ごとに /goal+/loop で再帰改善」は **rich feedback 前提なら成立**・粗 feedback では害。

- 限界: 1モデル・trials=1・ollama 非決定。clean な feedback-rescue は negabinary 1件（要追試）。raw: `config_mesh_results.json`(blind) / `config_mesh_rich_results.json`(rich+held-out)。

### 続報（実測完了 2026-06-23）— escalation で天井超え、3段で実証
Mac Studio MLX（Devstral-24B / Qwen3.5-122B-A10B）に同じ rich-loop を当てた:
- **wildcard_plus**: 7B 不可 → **24B で解決**（0.8→1.0・held追従・Goodhart 0）。
- **calc**: 7B も 24B も不可 → **122B で解決**（0.0→1.0 @iter1・held追従・Goodhart 0）。

**⚠️ 訂正（頑健化 trials=3）**: 当初「3段の梯子（7B→24B→122B 単調）」と書いたが、trials=3 で**非単調**が判明し撤回。実測:
| task | 7B(3) | 24B(3) | 122B |
|---|---|---|---|
| negabinary | **3/3** | **0/3** | 未測 |
| calc3 | **3/3** | **0/3** | 未測 |
| wildcard_plus | 0/3 | **3/3** | 1/1 |
| calc | 0/3 | 0/3 | 1/1 |

**24B は 7B が解く negabinary/calc3 を落とす**（診断済＝genuine。Devstral が negabinary に base −2 でなく普通の2進数を書く）。→ 能力は **total-order(梯子)でなく profile** ＝「上位 agent へ escalate」でなく **§5 の検証ルーティング*市場*（異種プールに投げ verifier を通った物を採る）が正しい機構**。robust データが §5（heterogeneity＋検証ルーティング＞単一モデル）を逆に裏付けた。
**頑健に立った**: ① **rich feedback は Goodhart-safe＝0/30 セル**。② rich-loop は *profile 内*で再現的（negabinary@7B 3/3・wildcard_plus@24B 3/3）。③ **calc は 7B/24B とも 0/3 で再現的に不可**＝122B 級が要る（122B は trials=1 のまま）。運用記録= local-llm-lab `experiments/2026-06-23-config-mesh-escalation.md`。
