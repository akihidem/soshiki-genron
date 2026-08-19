r"""replication.py ── 複製深度(trials)の台帳と、trials=1 の主張が*実際に*主張できている量。

ロードマップの「**trials>1 を全実証へ**」は、素直に読むと「標本を増やして精度を上げる」である。
本ファイルはその読みを否定する。**trials>1 が買うのは精度ではない。床の前提条件である。**

## ① なぜ trials=1 だと「床」がそもそも立たないか

[`noise.py`](noise.py) は非決定な採点ハーネスに対する**検出床**を与える。だがその床は**セル反転率 f**
を要求し、f は独立2試行のセル不一致率 d から

    d = 2f(1−f)  ⟹  f = (1 − √(1−2d)) / 2

として推定される。**d は t≥2 でしか定義されない。** つまり trials=1 の実測は「床を超えていない」の
ではなく、**床を計算することができない**。ノイズが小さいという主張ではなく、ノイズが*未測定*である。

本リポはこれで一度落ちている: 単一試行の opus×codex で gain **+0.042** を「real frontier で初の点火」
と報告・commit し、trial-2 で 0 に flip して撤回した（[`../experiments/SWEBENCH_TRIALS.md`
](../experiments/SWEBENCH_TRIALS.md)）。撤回後に f=0.067 を入れて計算すると、その観測は H0 の下で
**確率 0.68 ＝ ノイズの*期待される*出力**だった。**trial-2 を回す前に計算できた** ── ただし t≥2 が
一つでもあれば、という条件付きで。t=1 しか無い実測には、この事後計算すら適用できない。

⟹ **「trials>1 を全実証へ」＝「全実証を noise.py の床の適用範囲に入れる」**。贅沢でなく前提条件。

## ② trials は検出力を買わない ── それは n が買う

[`gap.py`](gap.py) ①が示したとおり、per-task が 0/1 に張り付く（＝能力差が構造的な）実測では
trials の分散寄与は**厳密にゼロ**である。検出力の側は n だけが決める。

本ファイルはその n 側の床を、群間比較に固有の形で与える。群 A,B の**対応**した二値スコア
（同一タスクを両群が解いたか）に対する厳密符号検定（McNemar exact）:

    不一致対 b = #(A=1,B=0), c = #(A=0,B=1),  m = b+c
    two-sided p = min(1, 2·Σ_{i≥max(b,c)} C(m,i) / 2^m)

ここで **n タスクで到達可能な最小の p は 2^{1−n}**（全 n 対が一方向に不一致という最良観測）。よって

    **n ≤ 5 では、どんな観測を得ても α=0.05 で有意にならない。**（2^{1−5}=0.0625 > 0.05）

これは観測に依存しない ── 実験を回す*前に*決まっている。標本が主張を支持しないのではなく、
**その n の実験は当該主張を支持しうる観測を持っていない**。

## ③ 何が実際に賭かっているか（本ファイルを書いた動機）

`docs/deployment-architecture.md` は本リポで最も**処方的**な文書で、「役割を切らない」「やらない＝
役割分業の固定パイプライン」を配置則として述べる。その根拠は

    構造利得 −0.167 ／ test_loop=1.0 vs 役割分業 ／ test_loop が役割分業を +0.5 上回る

で、いずれも `experiments/role_division_repair_real.json`（**trials=1・n=6**）の 1 ファイルに由来する。
③の再判定はこの全主張に符号検定を通す。結果は本文表のとおり **すべて p ≥ 0.25**（最小到達 p は
0.031 なので n=6 自体は反証可能域にあるが、観測がそこに届いていない）。

**処方が偽だと言っているのではない。処方を支える標本が、その処方を支えていないと言っている。**
これは撤回された +0.042 と同型の失敗が、モデル層でなく**処方層**で起きている状態である。

決定的（厳密・stdlib のみ・RNG なし）。 run: python3 -m model.replication
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
from dataclasses import dataclass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EXP_DIR = os.path.join(_ROOT, "experiments")

# --------------------------------------------------------------------------- #
# 判定ラベル（gap.py の三値と同じ作法 ── 肯定形で証明できた時だけ宣言する）
# --------------------------------------------------------------------------- #
SIGNIFICANT = "SIGNIFICANT"
UNDECIDED = "UNDECIDED"
IMPOSSIBLE = "IMPOSSIBLE_AT_THIS_N"   # その n では到達可能な最小 p ですら α を切れない

# 台帳の分類
REPLICATED = "REPLICATED"       # trials≥2 を宣言＝noise.py の床が適用できる
SINGLE = "SINGLE"               # trials=1 を宣言＝床が計算不能
UNDECLARED = "UNDECLARED"       # 複製深度を成果物から復元できない（宣言も scores も無い）

# 意図的に trials=1 のまま在ってよいファイル（＝理由が在るもの）。
# ここに無い SINGLE が現れたら test_replication が赤になる ── 「黙って増える」を防ぐのが目的。
EXEMPT: dict = {
    "role_division_demo.json":
        "決定的 mock デモ（harness の健全性確認であって科学的主張ではない。ファイル冒頭の出力にも"
        "DETERMINISTIC — NOT a scientific result と明記される）。複製しても同じ値が出る。",
}


@dataclass(frozen=True)
class ReplParams:
    alpha: float = 0.05
    # 台帳の走査対象。*_artifacts.json は生ログ（主張でない）ので除く。
    scan_dir: str = _EXP_DIR


# --------------------------------------------------------------------------- #
# ① 厳密符号検定（対応二値・McNemar exact）
# --------------------------------------------------------------------------- #
def sign_test(va: list, vb: list) -> dict:
    """対応した二値スコア列 A,B の厳密両側符号検定。

    H0: 不一致対の向きは 50:50（＝群間に差が無い）。一致対（両方解けた／両方落ちた）は
    情報を持たないので落とす ── これが「n タスク回したのに実質 m 対しか無い」の正体である。
    """
    if len(va) != len(vb):
        raise ValueError("対応していない（長さが違う）")
    b = sum(1 for x, y in zip(va, vb) if x > y)
    c = sum(1 for x, y in zip(va, vb) if x < y)
    m = b + c
    if m == 0:
        p = 1.0
    else:
        k = max(b, c)
        tail = sum(math.comb(m, i) for i in range(k, m + 1)) / (2 ** m)
        p = min(1.0, 2.0 * tail)
    # p は**丸めない**。閾値比較（p ≤ α）に使う値を表示都合で丸めると、境界で判定が変わりうるし
    # 大きい m では 0.0 に潰れて「不可能」と「極小」が区別できなくなる。表示は _fmt_p が持つ。
    return {"a_only": b, "b_only": c, "discordant": m, "p": p, "p_str": _fmt_p(p)}


def min_attainable_p(n: int) -> float:
    """n 対で**到達可能な**最小の両側 p。全 n 対が一方向に不一致という最良観測に対応する。

    観測に依らず n だけで決まる ── 実験を回す前に「その n で何が言えるか」が確定している。
    """
    if n <= 0:
        return 1.0
    return min(1.0, 2.0 ** (1 - n))


def min_n_for_significance(alpha: float = 0.05) -> int:
    """符号検定が*原理的に*有意になりうる最小の n。"""
    n = 1
    while min_attainable_p(n) > alpha:
        n += 1
    return n


def verdict(p: float, n: int, alpha: float = 0.05) -> str:
    """三値。**「有意でない」と「有意になりようがない」を混ぜない**のが要点。"""
    if min_attainable_p(n) > alpha:
        return IMPOSSIBLE
    return SIGNIFICANT if p <= alpha else UNDECIDED


# --------------------------------------------------------------------------- #
# ② 複製深度の台帳
# --------------------------------------------------------------------------- #
def declared_depth(obj) -> "int | None":
    """成果物から複製深度を復元する。宣言 `trials` を優先し、無ければ scores 列長に落ちる。

    scores 列長を「深度」と読んでよいのは、各 scores が同一セルの反復試行だから（本リポの
    実測スクリプトは全てその書式）。復元できなければ None ＝ UNDECLARED を返す（推測しない）。
    """
    found: list = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "trials" and isinstance(v, int):
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    if found:
        return min(found)

    lengths: list = []

    def walk_scores(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "scores" and isinstance(v, list):
                    lengths.append(len(v))
                else:
                    walk_scores(v)
        elif isinstance(o, list):
            for v in o:
                walk_scores(v)

    walk_scores(obj)
    return min(lengths) if lengths else None


def classify(depth: "int | None") -> str:
    if depth is None:
        return UNDECLARED
    return REPLICATED if depth >= 2 else SINGLE


def ledger(scan_dir: str = _EXP_DIR) -> dict:
    """実測成果物を走査して複製深度で分類する。

    走査対象は experiments/*.json のうち `*_artifacts.json` でないもの（artifacts は生ログであって
    主張ではない）。model/*.json は解析モデルの出力（決定的・複製の概念が無い）ので対象外。
    """
    rows = []
    for fname in sorted(os.listdir(scan_dir)):
        if not fname.endswith(".json") or fname.endswith("_artifacts.json"):
            continue
        with open(os.path.join(scan_dir, fname), encoding="utf-8") as f:
            obj = json.load(f)
        depth = declared_depth(obj)
        rows.append({"file": fname, "depth": depth, "klass": classify(depth),
                     "exempt": fname in EXEMPT})
    counts = {k: sum(1 for r in rows if r["klass"] == k)
              for k in (REPLICATED, SINGLE, UNDECLARED)}
    debt = [r for r in rows if r["klass"] == SINGLE and not r["exempt"]]
    return {"rows": rows, "counts": counts, "n_files": len(rows),
            "debt": debt,
            "declared_rate": round((counts[REPLICATED] + counts[SINGLE]) / len(rows), 4)
            if rows else 0.0}


# --------------------------------------------------------------------------- #
# ③ 再判定 ── 処方を支えている trials=1 実測に符号検定を通す
# --------------------------------------------------------------------------- #
_REPAIR_JSON = os.path.join(_EXP_DIR, "role_division_repair_real.json")

# 本ファイルが検定する対比。docs/deployment-architecture.md が処方の根拠として挙げるものに対応。
_CONTRASTS = (
    ("role_same", "solo", "構造利得（役割分業 − solo）", "「役割を切らない」の根拠 −0.167"),
    ("role_cross", "role_same", "多様性利得（異モデル役割 − 同モデル役割）", "cross の上乗せ"),
    ("role_cross", "solo", "総利得（役割分業 − solo）", "役割分業パイプラインの是非"),
    ("test_loop", "solo", "test 接地反復 − solo", "「L1 が既定ユニット」の根拠"),
    ("test_loop", "role_cross", "test 接地反復 − 役割分業", "「+0.5 上回る」の根拠"),
)


def load_repair(path: str = _REPAIR_JSON) -> dict:
    """trials=1 の実測を per-task の対応ベクトルへ畳む（決定的・タスク名でソート）。"""
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    tasks = sorted({c["task"] for c in obj["cells"]})
    by = {(c["task"], c["group"]): c for c in obj["cells"]}
    groups = sorted({c["group"] for c in obj["cells"]})
    vectors = {g: [by[(t, g)]["mean_score"] for t in tasks] for g in groups}
    return {"tasks": tasks, "groups": groups, "vectors": vectors,
            "trials": obj.get("trials"), "n": len(tasks)}


def reaudit(prm: ReplParams) -> dict:
    d = load_repair()
    n = d["n"]
    rows = []
    for a, b, label, used_for in _CONTRASTS:
        st = sign_test(d["vectors"][a], d["vectors"][b])
        rows.append({"contrast": f"{a} − {b}", "label": label, "used_for": used_for,
                     "mean_diff": round(sum(d["vectors"][a]) / n - sum(d["vectors"][b]) / n, 4),
                     **st, "verdict": verdict(st["p"], n, prm.alpha)})
    # 表示順は「弱い配置 → 強い配置」の物語順に固定する（sorted だと role_* が solo より前に来る）。
    order = ["solo", "role_same", "role_cross", "test_loop"]
    groups = [g for g in order if g in d["groups"]] + [g for g in d["groups"] if g not in order]
    return {"source": os.path.basename(_REPAIR_JSON), "trials": d["trials"], "n": n,
            "tasks": d["tasks"], "vectors": d["vectors"], "groups": groups, "rows": rows,
            "min_attainable_p": min_attainable_p(n), "min_attainable_p_str": _fmt_p(min_attainable_p(n)),
            "n_significant": sum(1 for r in rows if r["verdict"] == SIGNIFICANT)}


# --------------------------------------------------------------------------- #
# ④ n の値段 ── 符号検定が反証可能になる n
# --------------------------------------------------------------------------- #
def _fmt_p(p: float) -> str:
    """小さい p を 0.0 に丸め潰さない（表の上で「不可能」と「極小」が同じ見た目になるのを防ぐ）。"""
    if p >= 1e-4:
        return f"{p:.4g}"
    return f"{p:.1e}"


def n_ladder(alpha: float = 0.05, grid=(3, 4, 5, 6, 8, 10, 12, 24)) -> list:
    return [{"n": n, "min_p": min_attainable_p(n), "min_p_str": _fmt_p(min_attainable_p(n)),
             "falsifiable": min_attainable_p(n) <= alpha} for n in grid]


def run(prm: "ReplParams | None" = None) -> dict:
    prm = prm or ReplParams()
    lg = ledger(prm.scan_dir)
    ra = reaudit(prm)
    return {
        "params": dataclasses.asdict(prm) | {"scan_dir": os.path.basename(prm.scan_dir)},
        "ledger": lg,
        "reaudit": ra,
        "n_ladder": n_ladder(prm.alpha),
        "min_n": min_n_for_significance(prm.alpha),
        "finding": (
            f"実測成果物 {lg['n_files']} 件のうち複製深度を宣言しているのは "
            f"{lg['counts'][REPLICATED] + lg['counts'][SINGLE]} 件"
            f"（trials≥2 が {lg['counts'][REPLICATED]} 件・trials=1 が {lg['counts'][SINGLE]} 件）、"
            f"復元不能が {lg['counts'][UNDECLARED]} 件。"
            f"処方文書を支える {ra['source']}（trials={ra['trials']}・n={ra['n']}）の "
            f"{len(ra['rows'])} 主張は、符号検定を通すと有意 {ra['n_significant']} 件。"),
        "falsifier": (
            "本ファイルが偽なら: (a) t=1 からセル反転率 f を推定する手続きが在る"
            "（d=2f(1−f) は独立2試行を要するので在り得ない）、または (b) 対応二値で "
            "n 対から 2^{1−n} より小さい両側 p を出せる厳密検定が在る"
            "（符号検定の帰無分布は Binomial(m,1/2) で m≤n、その最小両側裾は 2·2^{−n}）。"),
    }


# --------------------------------------------------------------------------- #
# md レンダラ
# --------------------------------------------------------------------------- #
def _md(r: dict) -> str:
    lg, ra = r["ledger"], r["reaudit"]
    L = []
    A = L.append
    A("# 複製深度(trials)の台帳 ── trials>1 が買うのは精度でなく**床の前提条件**")
    A("")
    A("ロードマップの「trials>1 を全実証へ」を、標本の贅沢でなく**適用条件**として定式化する。"
      "生数値 [`replication_results.json`](replication_results.json)。")
    A("")
    A("> [`noise.py`](noise.py) の検出床はセル反転率 f を要求し、f は独立2試行の不一致率 "
      "d=2f(1−f) からしか推定できない。**t=1 の実測は「床を超えていない」のでなく「床を計算できない」。**"
      " 一方 trials は検出力を買わない（[`gap.py`](gap.py) ①）── 検出力は n が買い、対応二値の"
      f"符号検定では **n ≤ {r['min_n'] - 1} でどんな観測も α={r['params']['alpha']} で有意にならない**。")
    A("")
    A("## ① 台帳 ── 実測成果物の複製深度")
    A("")
    A(f"`experiments/` の主張ファイル {lg['n_files']} 件（`*_artifacts.json` は生ログなので除外）:")
    A("")
    A("| 分類 | 件数 | 意味 |")
    A("|---|---|---|")
    A(f"| `REPLICATED`（trials≥2） | {lg['counts'][REPLICATED]} | noise.py の床が**適用できる** |")
    A(f"| `SINGLE`（trials=1） | {lg['counts'][SINGLE]} | f が推定不能＝床が**立たない** |")
    A(f"| `UNDECLARED` | {lg['counts'][UNDECLARED]} | 成果物から深度を復元できない |")
    A("")
    A(f"深度の宣言率 **{lg['declared_rate']:.0%}**。`UNDECLARED` は「trials=1 だった」ではなく"
      "「**記録されていないので分からない**」である ── 台帳としては後者の方が重い。")
    A("")
    if lg["debt"]:
        A("**免除されていない trials=1（＝返済対象の負債）**:")
        A("")
        A("| ファイル | 深度 |")
        A("|---|---|")
        for row in lg["debt"]:
            A(f"| `{row['file']}` | {row['depth']} |")
    else:
        A("**免除されていない trials=1 は無い。**（免除 = 決定的 mock デモ等・"
          "`replication.EXEMPT` に理由付きで登録されているもの）")
    A("")
    A("## ② 再判定 ── 処方文書を支える trials=1 実測")
    A("")
    A(f"`experiments/{ra['source']}`（**trials={ra['trials']}・n={ra['n']}**・タスク "
      f"{', '.join(ra['tasks'])}）。`docs/deployment-architecture.md` は"
      "「役割を切らない」「やらない＝役割分業の固定パイプライン」をここから処方している。")
    A("")
    A("per-task の二値ベクトル:")
    A("")
    A("| 群 | ベクトル | 解決数 |")
    A("|---|---|---|")
    for g in ra["groups"]:
        v = ra["vectors"][g]
        A(f"| `{g}` | {', '.join(str(int(x)) for x in v)} | {int(sum(v))}/{ra['n']} |")
    A("")
    A("厳密符号検定（両側・一致対は情報を持たないので落ちる）:")
    A("")
    A("| 対比 | 平均差 | 不一致対 m | p | 判定 | 何の根拠か |")
    A("|---|---|---|---|---|---|")
    for row in ra["rows"]:
        A(f"| {row['label']} | {row['mean_diff']:+.3f} | {row['discordant']} | "
          f"{row['p_str']} | **{row['verdict']}** | {row['used_for']} |")
    A("")
    A(f"**{len(ra['rows'])} 主張のうち有意は {ra['n_significant']} 件。** n={ra['n']} で到達可能な最小 p は "
      f"{ra['min_attainable_p_str']}（全 {ra['n']} 対が一方向に不一致という最良観測）なので、n 自体は"
      "反証可能域に在る ── **観測がそこに届いていない**。「差が無い」ではなく「この標本は差の有無を"
      "決められない」である。")
    A("")
    A("処方が偽だと言っているのではない。**処方を支える標本が、その処方を支えていない。**"
      "撤回された mesh の +0.042 と同型の失敗が、モデル層でなく**処方層**で起きている状態である。")
    A("")
    A("## ③ n の値段 ── 符号検定が反証可能になる n")
    A("")
    A("| n | 到達可能な最小 p | 反証可能か |")
    A("|---|---|---|")
    for row in r["n_ladder"]:
        A(f"| {row['n']} | {row['min_p_str']} | {'✓' if row['falsifiable'] else '**不可**'} |")
    A("")
    A(f"**最小 n = {r['min_n']}。** これは観測に依らず実験を回す*前*に決まる。"
      "n=3 の群間比較（`role_division_real.json`）は trials=2 を持っていても、"
      "**どんな結果が出ても有意にならない**。複製深度と標本数は別々に返すしかない負債である。")
    A("")
    A("## 含意 ── 「trials>1 を全実証へ」の正しい読み")
    A("")
    A("- ✗ 「精度を上げるために試行を増やす」 → trials は構造的能力差の下で分散に**厳密にゼロ**しか"
      "寄与しない（gap.py ①）。")
    A("- ✓ **「全実証を noise.py の床の適用範囲に入れる」** ── t≥2 が一つでも在れば f が推定でき、"
      "撤回が*事後に*でなく*事前に*計算できるようになる。")
    A("- ✓ **検出力の負債は n で別に返す。** 群間比較では n≥"
      f"{r['min_n']} が反証可能性の入口。")
    A("- ✓ **深度を記録しない実測は、負債かどうかすら判定できない。** `UNDECLARED` "
      f"{lg['counts'][UNDECLARED]} 件を減らすことが台帳の最初の一手。")
    A("")
    A("## 反証条件")
    A("")
    A(f"- {r['falsifier']}")
    return "\n".join(L)


def main(argv=None) -> int:
    r = run()
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "replication_results.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False, indent=2, sort_keys=True))
    with open(os.path.join(here, "REPLICATION.md"), "w", encoding="utf-8") as f:
        f.write(_md(r) + "\n")
    print(r["finding"])
    print("wrote model/replication_results.json, model/REPLICATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
