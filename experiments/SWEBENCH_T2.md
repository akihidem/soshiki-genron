# 実証: 実 SWE-bench（pytest 実 repo）で frontier は脱相関するか

修復方式: **one-shot**。

構築タスク（生成・145 意地悪ケース・微妙バグ修復）では frontier(opus/codex)は誤らず脱相関ゼロだった（PAPER §5）。ここは*実 repo の実 issue* ── pytest 7.4/8.0 の実バグを、user-issue ＋ バグのある実ファイルごと渡し、**SEARCH/REPLACE 差分**で one-shot 修復させ、**実テストスイートで採点**（FAIL_TO_PASS 全 pass かつ PASS_TO_PASS 新規 regression ゼロ ＝ SWE-bench 'resolved'）。

Docker 不可環境のため Python3.12 互換 instance のみ（gold patch が当環境で F2P を pass させる instance=6 件を gold 検証ゲートで選別）。

## instance × model（1=resolved）
| instance | file | opus | codex |
|---|---|---|---|
| pytest-dev__pytest-11125 | `src/_pytest/config/__init__.py` | 0 | 0 |
| pytest-dev__pytest-11143 | `src/_pytest/assertion/rewrite.py` | 1 | 1 |
| pytest-dev__pytest-11148 | `src/_pytest/pathlib.py` | 1 | 1 |
| pytest-dev__pytest-11160 | `src/_pytest/recwarn.py` | 0 | 0 |
| pytest-dev__pytest-11178 | `src/_pytest/python_api.py` | 1 | 1 |
| pytest-dev__pytest-11217 | `src/_pytest/fixtures.py` | 1 | 1 |

per-model resolved 率（n=6 instance）: {'opus': 0.667, 'codex': 0.667}

## ペア union vs 単独最良（gain>0 ＝ frontier で mesh 点火）
| ペア | union | 単独最良 | gain | A だけ解く | B だけ解く | 相補の型 |
|---|---|---|---|---|---|---|
| opus + codex | 0.667 | 0.667 | **+0.0** | — | — | 一致（差なし） |

## 読み（union>best には*相互*相補が要る ── ただの instance 差では足りない）
- **相互相補（双方が相手の落とす所を拾う）→ union>best ＝ mesh が*現実規模*で点火**。構築タスク（生成・145意地悪・微妙バグ修復）では両者*完全一致*で instance 差すら無かった。
- **非対称（片方の解集合が他方を包含）→ gain=0**。instance レベルの差（＝脱相関の芽）は出るが、支配側を単独で使えば足り union は増えない。実バグで*初めて instance 差が現れた*のは重要だが、n が小さいと一方向に偏りやすく mesh は点火しない。
- floor（両者 0）＝ one-shot 単一ファイル修復は frontier にも難（実 SWE-bench の反復エージェントharnessは~60-70%だが本実験は test feedback 無し one-shot）。少標本・要追試。
