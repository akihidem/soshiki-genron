# 業界標準 AI ベンチマーク調査 ＋ soshiki-genron 対応 (2026-06-23)

> 自前 market 系マイクロベンチを「業界標準の LLM 評価」に位置づけるための調査メモ。
> PAPER.md の関連研究／実験設計の判断材料。情報源は末尾。

## TL;DR
- 旧ベンチ（MMLU / HumanEval / MBPP / GSM8K）は frontier 飽和で**識別力を喪失**。業界は未飽和の新ベンチ群へ移行。
- これは本研究の market 系が古典アルゴで gemma/haiku を `p≈1.0` 飽和させたのと**同型現象**（人間の難しさ ≠ LLM の難しさ＋学習データ汚染）。
- **業界標準を網羅測定する必要はない**（研究目的＝mesh が単一を超えるか、であって単一能力ランキングではない）。
- 価値があるのは1点：escalation/mesh が古典アルゴで発火しなかった穴を、**未飽和ベンチ1本**で埋めること。推奨は GPQA Diamond 風（選択式・採点容易・Docker 不要）。

## 1. 2026 ヘッドライン標準セット
複数ソースが共通で挙げる短リスト：
**HLE ＋ GPQA Diamond ＋ FrontierMath ＋ AIME 2025 ＋ SWE-bench Verified ＋ Aider Polyglot ＋ τ-bench ＋ GAIA ＋ BFCL v3 ＋ MMMU-Pro ＋ RULER**

## 2. 能力領域別

| 領域 | 代表ベンチ（2026標準） | 何を測る | 状態 |
|---|---|---|---|
| 汎用知識・推論 | GPQA Diamond / MMLU-Pro / HLE | PhD級198問(検索不能) / 10択+CoT強制 / 専門家3000問 | HLE は低50%台＝未飽和の本命 |
| マルチモーダル | MMMU-Pro | 画像＋文書の統合理解 | 伸び盛り |
| 数学 | AIME 2025 / HMMT / FrontierMath | 競技数学 / 研究級・未公開問題 | 競技は95-99%飽和、FrontierMath 40%台 |
| コーディング | SWE-bench Verified / LiveCodeBench / Aider Polyglot | 実GitHubリポ修復 / 競プロ / 多言語編集 | SWE-bench Verified が事実上の業界標準 |
| エージェント/ツール | τ-bench / GAIA / BFCL v3 / Terminal-Bench | 対話ツール使用 / 汎用アシスタント / 関数呼出 / CLI長期タスク | exploit 脆弱性が露呈（§5-2） |
| 長文脈 | RULER | 長コンテキストの検索・追跡 | |
| ~~旧・飽和~~ | ~~MMLU / HumanEval / MBPP / GSM8K~~ | — | frontier が90%+でクラスタ＝比較に使えない |

## 3. 集約リーダーボード & 評価ハーネス
- **LMArena**（arena.ai、旧 LMSYS Chatbot Arena）— 人間選好 Elo（frontier 帯 ≈1450–1561）
- **Artificial Analysis** — 100+ モデルを intelligence/price/speed で横断比較
- **HELM**（Stanford CRFM）— 42シナリオ×7指標（accuracy/fairness/bias/toxicity/efficiency/robustness/calibration）
- **llm-stats.com** / **Open LLM Leaderboard**（HuggingFace・open-weight）
- 再現用ハーネス: **lm-eval-harness**（EleutherAI）/ **simple-evals**（OpenAI）/ HELM
- ※順位・スコア固有値は変動が速く、本メモでは扱わない（種類と性質が主眼）

## 4. 自前 market 系 ↔ 業界標準 対応表 ★

| soshiki-genron 自前 | 対応する業界標準 | 関係 |
|---|---|---|
| `market_external` / `market_gap`（古典アルゴ生成） | HumanEval / MBPP | 同型。どちらも飽和・contamination で識別力低 |
| `market_ladder`（難度階段） | LiveCodeBench / Aider Polyglot | 難度別コード生成 |
| `experiments/swebench_repair.py`（実バグ修復 N=24） | **SWE-bench Verified** | 直接の自前実装＝Docker 無し縮小版（pytest/sympy のみ） |
| `experiments/meshflow.py`（escalation＋検証ルーティング） | τ-bench（の問題意識） | 単一モデルでなく**組成（オーケストレーション）層**を測る＝業界標準に正面の対応物が少ない＝本研究の独自地帯 |
| `market_novel` / `market_openended`（学習データ外） | **FrontierMath / HLE の思想** | contamination 回避の動機が同型 |
| 外部検証ゲート（sandbox gold） | SWE-bench の test-based 判定 / Berkeley RDI の堅牢採点要件 | 「外部検証の堅牢性こそベンチの命」で一致 |
| `market_decorr`（脱相関 union） | （対応物ほぼ無し＝mesh 研究固有） | アンサンブル＝外部検証器つき verifier-union |

**含意**: 本研究は「単一モデルの能力測定（業界標準の主戦場）」ではなく、**その上の組成層（escalation / mesh / 検証ルーティング）**を測っている。meshflow と decorr に業界の正面対応物が薄い＝そこが独自貢献。

## 5. soshiki-genron への含意（3点）
1. **飽和の同型**: 旧ベンチが天井張り付き→業界が HLE/FrontierMath/SWE-bench へ逃げた。本研究で gemma/haiku が古典アルゴ飽和したのと同じ。根＝人間の難しさ≠LLM の難しさ＋学習データ汚染。FrontierMath が novel・未公開問題にしたのは `market_novel/openended` の動機と同一。
2. **harness exploit の同型**: 2026 Berkeley RDI 研究が SWE-bench Verified / Terminal-Bench / WebArena / OSWorld / GAIA を含む8大エージェントベンチを「タスクを解かずに near-perfect を取れる」と暴いた（漏洩参照解・`eval()` 未サニタイズ・prompt-injection 可能な LLM judge・correctness を飛ばす採点）。本研究の教訓「初回 all-zero は3層 harness artifact」「陽性対照 known-correct→solved=1 を先に通す」「外部検証が背骨」と完全同型。
3. **位置づけ**: market 系＝自前マイクロベンチ、swebench_repair.py＝業界標準の自前縮小実装。やってきたことは業界の縮図であり、独自地帯は組成層。

## 6. 「業界標準で自分のベンチを測るべきか」の判断

| ベンチ | 自前で回せるか | 推奨度 | 理由 |
|---|---|---|---|
| **GPQA Diamond** | ◎（選択式198問・採点容易・Docker 不要・stdlib） | **★推奨** | 未飽和・escalation/mesh の発火土俵になる。contamination 注意（gated 配布版を使う） |
| LiveCodeBench (hard) | ○（コード・自前 grade 流用可） | △ | コード採点器を再利用できるが時系列汚染管理が要る |
| SWE-bench Verified | △（Docker 必須・N=24 が上限と既知） | △ | 既に縮小実装済み。フル版は Docker 領域で本環境では非現実的 |
| τ-bench / GAIA / Terminal-Bench | △（環境シミュレーション重い） | × | 構築コスト大・exploit 脆弱性で解釈も難 |
| HLE / FrontierMath | ×（access 制限・採点に専門知識/非公開） | × | 自前で回せない |
| AIME / HMMT | ○（数値答・採点容易） | △ | 競技数学は95%+飽和＝モデル差が出ない |

**結論**: 網羅測定は不要。研究の穴（古典アルゴでは安ティアが解き切り escalation/mesh が発火しない）を埋める**未飽和タスク1点**として **GPQA Diamond** を自前マイクロベンチに足すのが費用対効果◎。これで「安ティアが落とす→sonnet/opus へ昇格」「単独不可→mesh 点火」が初めて観測でき、market_external 系と同じ採点フレームに載る。

## 7. 実測ログ：自前 MMLU-Pro で escalation/mesh を測る（2026-06-23）

`experiments/mmlu_pro_bench.py`（新規・10 tests 緑）で MMLU-Pro を gemma→haiku→sonnet→opus の
検証ルーティングに載せ、§6 の処方どおり未飽和土俵を作った。実 LLM 実測の要点：

- **未飽和土俵の成立**：physics で gemma p=0.50（古典アルゴの 0.77–0.87 から急落）＝escalation が
  初めて意味を持つ（escalated_rate=0.5）。古典アルゴは gemma が解き切り昇格ゼロだった。
- **偽の脱相関を発見（本セッションの白眉）**：math で当初 opus p=0.25 ≪ haiku 0.80、脱相関5問（全部
  opus落×haiku解）が出た。だが原因は **プロンプトが「ONLY the single letter」で CoT を禁じていた
  harness artifact**（TUI 落ちではない＝raw は len=2 の即レター）。opus が指示に忠実に推論せず即答→
  当てずっぽう。CoT を許すと **opus 0.25→0.90**、haiku 0.90、**両者は同じ問題だけを共有して落とす＝
  脱相関消滅**。即レター時の「脱相関」は強モデルを不公平に縛って捏造した人為物だった。
- **教訓**：不公平な測定条件が **偽の脱相関 → 偽の mesh 燃料** を生む。de-confound の新パターン。
  公平化すると opus≈haiku（同 hardcore 共有）で union 天井=1−hardcore率を単一で達成＝**mesh 不点火**。
  SWE-bench・古典アルゴと QA で独立に同じ向き。市場支配：公平条件で p 同じなら cost 1/15 の haiku が完全支配。
- **harness fix**：`make_prompt` を CoT 許可＋`Answer: <letter>` に修正済み（`extract_choice` が末尾を拾う）。
- **trials=3 で確定**（`mmlu_cot_trials.json`）：haiku=opus=**0.875 で per-task 完全一致**（7687 だけ両方 0/3 落とす唯一の hardcore）。脱相関ゼロを追認＝**mesh 純利得 0.000**、union 天井(1−1/8=0.875)を単一で達成。同系統（Anthropic）は誤りが相関し hardcore を共有＝SWE-bench 結論の QA 再現。opus 非決定の懸念も解消（0.875 安定）。

## 8. judge を外部錨で校正する（自由記述に拡張する前提・2026-06-23）

自由記述を judge で測る前に、judge 自体を陽性/陰性対照で検品した（「known-correct を先に通す」の judge 版）。位置バイアス除去（A/B 入替）込み。

- **easy control（good vs 明白に悪い）**：haiku/sonnet/opus 全員 6/6。「judge は無能でない」を示すだけ＝過信注意（対照が簡単すぎる罠）。
- **hard control（good vs subtly-worse＝事実誤り1個）**：単発では opus 3/6 に崩れたが、生出力は整形済み・~7s・非空＝TUI 落ちではなく**生成非決定のアーティファクト**。**trials=5 で公平化すると**：

  | judge | resolution | cost |
  |---|---|---|
  | sonnet | **1.00** (30/30) | 3.0 |
  | haiku | **0.97** (29/30) | 1.0 |
  | opus | **0.83** (25/30) | 15.0 |

- **結論**：**judge には haiku/sonnet、opus は外す**。安い haiku(1.0) が最強 opus(15.0) を judge として上回る＝**市場支配定理が judge 役割にも適用**。**generator 最強 ≠ judge 最強**＝役割別にモデルを配置せよ（組織処方に直結）。opus の弱点＝completeness バイアス（"詳しいが誤り"を高評価、sky は trials でも 0.60）。
- **judge 選定の作法**：hard calibration（微妙な質差）＋ trials（非決定を均す）＋ correctness-first プロンプト。easy/単発では opus も良く見えるので不可。**単発測定は強モデルを不当に過小評価する**（opus 3/6→trials 0.83）。
- これで「judge も使い自由記述も」の土台が完成＝信頼できる judge を外部錨で特定。openended の judge confound（+0.83→−0.08）を踏まずに自由記述 mesh へ進める。

## 9. 自由記述 mesh の決着：多様性の寄与は負（2026-06-23）

calibrated judge（haiku・correctness-first・trials=3）で自由記述（設計問い）の synthesis gain を測定：

- 生 gain：synth(sonnet が opus+gemma を統合) vs best_single = **+0.333**（点火に見えた）
- **de-confound（cross vs same-vendor merge）**：
  - cross(opus+gemma) gain = **+0.056**
  - same(opus+opus, 2ドラフト) gain = **+0.389**
  - **diversity effect (cross − same) = −0.333（負）**
- **結論**：+0.333 は **merge/再編集効果**（2ドラフトを統合し直すと少し上がる＝best-of-N）で、**多様性(mesh)の寄与はゼロ以下**。むしろ**弱い gemma を混ぜると gain が下がる（多様性は有害）**。openended `+0.83→−0.08` を再現・強化。**自由記述でも mesh は点火しない**。組み合わせる価値は「多様性」でなく「同じ強いモデルをもう一度引いて統合」（best-of-N）。

### 今日の総括：mesh 点火を5角度で探して全敗
古典アルゴ escalation／opus×haiku(math)／physics／gemma×haiku／自由記述 mesh——すべて純利得 ≈0 以下。**市場支配（単一最強モデルが最適）が checkable と自由記述の両方で独立に確認された**。mesh 燃料＝脱相関は (1)同系統で相関 (2)弱モデルは包含 (3)不公平測定で捏造 (4)自由記述で多様性有害——どの経路でも点火しない。

## 10. 結論の補正：冗長並列 vs 役割分業（2026-06-24）

§1–9 の「mesh 不点火・市場支配」は **冗長並列 mesh（同タスクを独立に解いた union/synthesis）に限った結論**。Sakana の TRINITY（ICLR 2026）/ Fugu は **役割分業＋検証＋学習協調**（Thinker/Worker/Verifier マルチターン）で単体超えを実証（SWE-Bench Pro 73.7 > Opus 4.8）＝**別メカニズム**。

- 正しい言明：「冗長並列 mesh は脱相関なしに超えない」（実証）＋「役割分業協調は超えうる」（Trinity が実証・本研究 §8 の generator≠judge が支持）。
- soshiki-genron §6.5 は役割分業を処方しながら、実験では冗長 mesh しか潰していなかった＝盲点。Fugu はその処方の学習最適化実装。
- **次の研究計画 → [`docs/role-division-research-plan.md`](role-division-research-plan.md)**（役割分業が単体を超えるか・利得は分業 vs 反復か・checkable 外部 gold・群 solo/redundant/role-same/role-cross/role-searched）。

## Sources
- The 2026 LLM Benchmark Reference: 17 Benchmarks — https://benchmarkingagents.com/benchmarks-list/
- Knowledge Benchmarks 2026 (GPQA/HLE) — https://benchlm.ai/knowledge
- Coding Leaderboard (SWE-bench/LiveCodeBench) — https://benchlm.ai/coding
- Math Benchmarks 2026 (AIME/HMMT/FrontierMath) — https://benchlm.ai/math
- Humanity's Last Exam Leaderboard — https://artificialanalysis.ai/evaluations/humanitys-last-exam
- Artificial Analysis Model Leaderboard — https://artificialanalysis.ai/leaderboards/models
- Terminal-Bench (arXiv) — https://arxiv.org/pdf/2601.11868
- UTBoost: Rigorous Evaluation of Coding Agents on SWE-Bench (arXiv) — https://arxiv.org/pdf/2506.09289
- LLM Leaderboard Explained 2026 (FutureAGI) — https://futureagi.com/blog/llm-leaderboard-explained/
- llm-stats.com AI Benchmarks — https://llm-stats.com/benchmarks
