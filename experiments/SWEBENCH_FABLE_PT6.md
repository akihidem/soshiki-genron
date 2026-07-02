# fable-5 を pytest-6 mesh に足す試み — trials=1 で撤回(2026-07-02)

**結論を先に**: この計測は**採用しない**。fable-5 の pytest-6 solve ベクトルは単一試行では非再現で、
mesh(opus×codex×fable)の値として載せられない。§9-11(非決定採点の単一試行は偽差を生む)の再確認。

## 何をしたか
「soshiki-genron に fable の値も追加」の依頼で、fable-5 を pytest 系 6 instance(gold 検証ゲート通過分)で
実 SWE-bench 修復させた。harness は既存の `swebench_repair.py`(`--models fable --tag swebench_fable_pt6`)、
モデル経路は `claude-cli-run.py --model claude-fable-5`(TUI・one-shot・**trials=1**)。

## なぜ撤回するか(2 試行で非再現)

| instance | trial-1 | trial-2 | 備考 |
|---|---|---|---|
| pytest-11125 | 0 | 0 | 両試行 fail(SEARCH/REPLACE は出すが F2P 通らず)。既知の非決定 instance(§9-11) |
| pytest-11143 | 1 | **0** | trial-2 は fable が**非コード出力**(架空都市 "Volta" の散文)を返し parse 不能→0 |
| pytest-11148 | 1 | **0** | 同上(非コード出力・parse 不能) |
| pytest-11160 | 0 | **1** | **hard-core を trial-2 で fable が解いた**(recwarn.py `pop` を正しく修正)。trial-1 の 0 は noise |
| pytest-11178 | 1 | 1 | 両試行 solve(実パッチ) |
| pytest-11217 | 1 | 1 | 両試行 solve(実パッチ) |
| **ベクトル** | **[0,1,1,0,1,1]** | **[0,0,0,1,1,1]** | **3/6 flip** |

trial-1 が偶々 codex([0,1,1,0,1,1])と一致したのは**偶然**で、trial-2 では一致しない。
当初 commit(`d7d0ae9`)の「fable≡codex・failure_ρ=1.0・3-way gain 0・第3 frontier は純冗長」は
**すべて単一試行の産物**であり、本記録で撤回する(mesh.py の `_SWE6_FABLE` と 3-way エントリを削除)。

## 二つの故障モード(なぜ noise か)
1. **claude-cli-run の巨大プロンプト非決定性**: pytest src の全文(11143 は 46k 字・11148 は 26k 字)を
   TUI 経由で渡すと、fable が修復タスクを無視して無関係な散文("Behold the city of Volta …")を返す
   ことがある(trial-2 の 11143/11148)。数万字プロンプトを TUI に流すのは信頼できない。
2. **非決定な per-instance 差**: 同一モデル・同一プロンプトでも run ごとに solve が変わる(§9-11 で opus も
   `claude-cli-run` 経由で ~12% variance・11125 は再走で結果が変わると既述)。fable も同様で、
   ここでは 3/6 が 2 試行間で flip した。

## 正しい結論(何が言えるか)
- **単一試行では per-model rate も mesh 点火も結論できない**。fable を frontier mesh(opus×codex)に
  足す判定には、**full-24 × trials>1**(全モデル同一環境・複数試行)が要る。ここでは未実施。
- 唯一言える肯定的事実: **fable は hard-core instance(11160)を解ける**(trial-2 で実証)。
  「fable は opus/codex と同じ hard core を共有する」は**偽**。
- 手続き上の学び: 大きいプロンプトを `claude-cli-run` TUI に流す構成は SWE-bench では脆い。
  Agent tool 直叩き or `--print` 経路 or 出力 parse の頑健化が要る。

## 生データ
- trial-1 スコア: `swebench_fable_pt6_results.json` / `swebench_fable_pt6_artifacts.json`
- trial-2 スコア + 生出力頭: `swebench_fable_pt6_trial2.json`(架空都市散文の証拠を含む)
