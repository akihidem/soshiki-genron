# 監督スケーリング — 第一パイロットの所見（予想外・measurement-first が効いた）

統治膜モデル（[`second-measurement.md`](second-measurement.md)）が*仮定*していた `oversight_error` を、実モデルで接地しようとした最初の実測。**仮説は再現せず**、概念を修正させられた —— これが計測第一の価値。

## 実測（`experiments/oversight/`・ollama・10件・trials=1）

| 監督者 | 捕捉率 | oversight_error | subtlety 1/2/3 | 誤検出(FP) |
|---|---|---|---|---|
| gemma4:e2b（弱） | 1.0 | 0.0 | 1.0 / 1.0 / 1.0 | 0.0 |
| gemma4:latest（強） | 1.0 | 0.0 | 1.0 / 1.0 / 1.0 | **0.33** |

**仮説（弱い監督は巧妙な欠陥を見逃す → oversight_error↑）は再現しなかった**。両者とも7件の仕込み欠陥を全部 FLAWED と判定。

## 診断
1. **verdict-level メトリクスが寛容すぎる** — 「FLAWED と言えば捕捉」なので、レビュー prompt が誘発する *FLAWED-bias*（疑い深い監督者役）が recall を水増し。強モデルの FP=0.33（clean を flawed と誤る）がその bias を裏付ける。
2. **真の失敗モードは recall でなく precision** — 「強い」監督ほど過剰に flag する（狼少年）。これは膜の*別の*失敗モード（過剰コスト・alert fatigue）で、トイモデルが想定した「見逃し」とは異なる。
3. 欠陥が両モデルの射程内／能力差が小さい可能性。

## 含意
- **トイモデルの oversight_error 前提は、この実測では裏取りされなかった** → `governance.py` の値は据え置き、**未接地**と明記する（仮の数字を実測のフリさせない）。
- **実証が概念を修正した**: 監督の失敗は「見逃し（recall）」より「過剰 flag（precision）」で現れうる。統治膜のコストは効率税だけでなく**誤検出ノイズ**にも。→ governance モデルに precision 項を足す動機。
- AI-2027 の「監督破綻」も、単純な見逃しでなく **alien/neuralese で*判断できない*（verdict 自体が無意味になる）** 形である点に注意 —— 本パイロットの「平易な欠陥」とは別レジーム。超人差はまだ測れていない。

## 追測定: フロンティア能力勾配（厳格メトリクス・gemma→claude）

指摘を受け、小さい能力差（gemma 同士）をやめ**実フロンティア勾配**で再測。捕捉は**同定一致**（説明が欠陥を正しく名指し）で厳格化。

| 監督者 | flag | 捕捉(同定) | oversight_error | subtlety3 | 誤検出FP |
|---|---|---|---|---|---|
| gemma4:e2b（最弱） | 1.0 | 0.857 | 0.143 | **0.667** | 0.0 |
| claude:haiku | 1.0 | 1.0 | 0.0 | 1.0 | 0.0 |
| claude:sonnet | 1.0 | 1.0 | 0.0 | 1.0 | **0.333** |
| claude:opus（最強） | 1.0 | 1.0 | 0.0 | 1.0 | **0.333** |

2つの所見:
1. **recall（実欠陥の捕捉）はほぼ天井** — 最弱 e2b だけが巧妙欠陥で 0.667 に落ちる。haiku 以上は全部捕捉。→ **これらの欠陥は frontier には簡単すぎる**。AI-2027 の crux（弱い監督が*超人の*巧妙な欠陥を見逃す）には、**opus 級が生成した本当に難しい欠陥**が要る（次の実験）。能力勾配の軸自体は機能した（最弱端で崩れた）。
2. **precision（誤検出しない）は能力とともに悪化（再現）** — FP: haiku 0.0 / sonnet 0.33 / opus 0.33（先の gemma-latest パイロットも 0.33）。**強い監督ほど clean を flawed と誤る**。能力は監督を単調には改善しない —— precision を*下げ*うる。2実験で再現。

→ 接地の結論: oversight の失敗は（少なくともこの難度では）**見逃し(recall)でなく過剰flag(precision)**で現れ、しかも**能力とともに悪化**。これが下記 B（governance に precision 項）の実測的動機。recall 側の crux は欠陥を難化して別途測る。

> コスト: claude 監督は `claude-cli-run.py`（対話TUI＝サブスク無料枠）経由に切替済み（`overseer.py`・次回以降コストゼロ）。

## 第三測定: opus 生成の巧妙欠陥での recall crux（真の weak-oversees-strong）

手作り欠陥が frontier に簡単すぎたので、**opus に自分の水準で巧妙な欠陥を6件生成させ**（`generate.py`・全 subtlety 3：dict aliasing / sin(1/x) 非一様連続 / 二分探索の挿入位置 off-by-one / SQL NOT IN+NULL / 指数最小の率加算 / str が iterable で無限再帰）、弱い監督に同定させた。

| 監督者 | flag | 捕捉(同定) | oversight_error |
|---|---|---|---|
| gemma4:e2b（最弱・~2B） | 0.5 | 0.5 | **0.5** |
| claude:haiku | 1.0 | 1.0 | 0.0 |
| claude:sonnet（強・独立） | 1.0 | 1.0 | 0.0 |
| claude:opus（自己レビュー） | 1.0 | 1.0 | 0.0 |

所見:
1. **recall crux は（部分的に）再現した** — opus 級の巧妙欠陥に対し、最弱 e2b は**半分を見逃す**（oversight_error=0.5・しかも flag すら 0.5＝半分は clean と誤判定）。手作り（~0）や勾配（e2b 0.14）より大きく崩れた。**「十分に弱い監督は、強いモデルの巧妙な誤りを見逃す」を実測**。
2. **ただし frontier 監督（haiku 以上）は opus の巧妙欠陥も全部捕捉** — 崩れには**大きな能力差**（e2b≈2B vs opus）が要る。1段差（haiku↔opus）では崩れない。
3. **完全崩壊（oversight_error→1）は未到達** — AI-2027 の核は*超人/neuralese で判断自体ができない* producer。opus は haiku にとって alien ではない。利用可能な最大差（opus→e2b）でも 0.5 止まり。**→1 への崩壊は測定可能モデルの外への外挿**。
4. 注: N=6・trials=1（少標本・ノイズ）。opus の ground truth は自己申告（可謬）だが、「強は捕捉・弱は見逃し」の向きは明確。

→ **governance.py の oversight_error の接地レンジ**: capable な監督では ~0、巨大な能力差で ~0.5、AI-2027 の →1 は超人 producer への外挿。これで「未接地」だった量に**測定された範囲**が付いた。

## 厳密版に必要（次の反復）
1. 捕捉を「欠陥を正しく**同定**したか」で測る（説明が仕込み欠陥に一致）。verdict 一致でなく内容一致。
2. もっと巧妙な欠陥／もっと大きな能力差（例: 強モデルが生成した欠陥を弱モデルに監督させる）。
3. **precision と recall を両方**測る（過剰 flag も失敗）。trials を増やし分散を見る。

> 結論: 最初の実証は仮説を否定し、メトリクスと失敗モードの理解を更新した。これは「概念を測定という外部錨に繋ぐ」第一原理が機能した証拠 —— トイモデルを実測のフリで通さなかった。
