# 実証: trials>1 で「mesh 点火」はノイズと判明（cross-vendor 脱相関の頑健化）

単一試行の N=24（pytest+sympy・one-shot）では **opus×codex に*相互*相補が出て union 0.792>best 0.75・gain +0.042** に見えた（[`SWEBENCH_ALL.md`](SWEBENCH_ALL.md)）。これが**実像かノイズか**を、同じ N=24 を独立に2回回して検定した。

## 2 試行の比較（N=24）

| | opus 解 | codex 解 | union | best | **gain** | 相互相補 |
|---|:--:|:--:|:--:|:--:|:--:|---|
| **trial 1** | 16/24 (0.667) | 18/24 (0.75) | 0.792 | 0.75 | **+0.042** | あり（見かけ） |
| **trial 2** | 19/24 (0.792) | 18/24 (0.75) | 0.792 | 0.792 | **0.0** | なし |

**gain は +0.042 → 0 に flip した。**

## per-instance の安定性（2 試行）

| instance | opus (t1,t2) | codex (t1,t2) | 判定 |
|---|:--:|:--:|---|
| `sympy-24443` | (1,1) | (0,0) | **opus-only（安定）** |
| `pytest-11148` | (0,**1**) | (1,1) | flip（opus が t2 で解いた） |
| `sympy-24325` | (0,**1**) | (1,1) | flip |
| `sympy-24661` | (0,**1**) | (1,1) | flip |

- **codex は決定的**: 18/24 が2試行で完全一致（variance 0）。`codex exec` は再現的。
- **opus は ~3/24 = 12% の run-to-run variance**: `claude-cli-run.py`（対話 TUI・非決定）経由のため、trial 1 で落とした 3 件を trial 2 では解いた。
- **安定な相互相補は無い**: 安定 opus-only は `sympy-24443` の 1 件のみ（*一方向*）、安定 codex-only は **0 件**（trial 1 の codex-only は全部 opus の不調由来だった）。

## 結論（頑健）

- **opus×codex に*安定な相互相補は無い* → cross-vendor mesh は実バグでも*点火しない*（robust gain = 0）。**
- **単一試行の +0.042 は opus のノイズ由来の偽陽性**だった。pytest n=6 の「非対称・gain 0」は *N 不足でなく正しかった*。
- 唯一の安定差 `sympy-24443`（opus が確実に解き codex が確実に落とす）は*一方向*で、union を単独最良より上げない。
- **燃料は能力相補性**: 同水準 frontier 2者は相関が強すぎて mesh を生まない（能力差のある gemma+haiku は +0.1＝対照的）。

## メタ計測教訓

- **非決定 TUI 採点（claude-cli-run.py）の単一試行は ~12% のセル variance を持つ。** 小さい gain（<0.05）は trials>1 でしか実像と判定できない ── 単一試行で +0.04 を「点火」と読むのは早合点（本リポでも一度 commit/push してしまい、本検定で撤回）。
- **codex は決定的・opus は非決定**という非対称も所見: ベンダ比較では*採点ハーネスの決定性*もモデル間で揃っていない（opus 側だけ trials が要る）。
