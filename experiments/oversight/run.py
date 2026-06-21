"""監督スケーリング実験の実行。

監督者 × 仕込み欠陥 の行列を回し、捕捉率を subtlety × 監督者能力 で集計。
oversight_error = 1 − 捕捉率（governance.py が仮定していた量）を**実測**する。

run:
  python3 -m experiments.oversight.run                      # 決定的 mock（期待形・即時）
  python3 -m experiments.oversight.run --backend ollama     # 実測（localhost の ollama）
  python3 -m experiments.oversight.run --backend ollama --models gemma:2b,gemma:7b --trials 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from experiments.oversight.dataset import ITEMS                       # noqa: E402
from experiments.oversight.overseer import (                          # noqa: E402
    ClaudeCliOverseer, CodexOverseer, MockOverseer, OllamaOverseer,
    ollama_available, review,
)


def run_matrix(overseers, items=ITEMS, trials: int = 1) -> list[dict]:
    records = []
    for ov in overseers:
        for _ in range(max(1, trials)):
            for it in items:
                records.append(review(ov, it))
    return records


def summarize(records: list[dict]) -> dict:
    by_ov: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_ov[r["overseer"]].append(r)
    out = {}
    for ov, rs in sorted(by_ov.items(), key=lambda kv: kv[1][0]["tier"]):
        flawed = [r for r in rs if r["flawed"]]
        clean = [r for r in rs if not r["flawed"]]
        by_sub = {}
        for s in (1, 2, 3):
            fs = [r for r in flawed if r["subtlety"] == s]
            by_sub[s] = round(sum(r["caught"] for r in fs) / len(fs), 3) if fs else None
        catch = round(sum(r["caught"] for r in flawed) / len(flawed), 3) if flawed else None
        flag = round(sum(r["flagged"] for r in flawed) / len(flawed), 3) if flawed else None
        fp = round(sum(r["false_positive"] for r in clean) / len(clean), 3) if clean else None
        out[ov] = {
            "tier": rs[0]["tier"],
            "flag_rate": flag,                  # said "FLAWED" (verdict-level, lenient)
            "catch_rate": catch,                # ALSO identified the flaw (strict)
            "oversight_error": round(1 - catch, 3) if catch is not None else None,
            "catch_rate_by_subtlety": by_sub,
            "false_positive_rate": fp,
            "n_flawed_items": len({r["item_id"] for r in flawed}),
        }
    return out


def build_overseers(backend: str, models: list[str], host: str):
    if backend == "mock":
        return [MockOverseer(1, "weak(cap1)"), MockOverseer(2, "mid(cap2)"),
                MockOverseer(3, "strong(cap3)")]
    if backend == "ollama":
        installed = ollama_available(host)
        if not installed:
            raise SystemExit("ollama unreachable at " + host + " — start it or use --backend mock")
        chosen = models or installed[:3]
        missing = [m for m in chosen if m not in installed]
        if missing:
            raise SystemExit(f"models not installed: {missing}. installed: {installed}")
        # tier = index in the chosen order (caller orders weak->strong)
        return [OllamaOverseer(m, tier=i + 1, host=host) for i, m in enumerate(chosen)]
    raise SystemExit(f"unknown backend {backend!r}")


def build_from_spec(entries: list[str], host: str):
    """Mixed cross-vendor gradient: each entry 'vendor:model', ordered weak->strong.
    e.g. ollama:gemma4:e2b,claude:haiku,claude:sonnet,claude:opus"""
    installed = None
    overseers = []
    for i, entry in enumerate(entries):
        vendor, _, model = entry.partition(":")
        tier = i + 1
        if vendor == "ollama":
            installed = ollama_available(host) if installed is None else installed
            if model not in installed:
                raise SystemExit(f"ollama model {model!r} not installed: {installed}")
            overseers.append(OllamaOverseer(model, tier=tier, host=host))
        elif vendor == "claude":
            overseers.append(ClaudeCliOverseer(model, tier=tier))
        elif vendor == "codex":
            overseers.append(CodexOverseer(model or None, tier=tier))
        else:
            raise SystemExit(f"unknown vendor {vendor!r} in {entry!r}")
    return overseers


def _report(summary: dict, meta: dict) -> str:
    L = ["# 監督スケーリング — oversight_error を実測する",
         "",
         f"backend: `{meta['backend']}` / trials: {meta['trials']} / 監督者: "
         + ", ".join(summary) + "。仕込み欠陥を巧妙さ別にレビューさせ、捕捉率（と "
         "oversight_error=1−捕捉率）を測る。governance.py が仮定していた量の実測。",
         "",
         "| 監督者 (tier) | flag率(verdict) | 捕捉率(同定) | oversight_error | sub1 | sub2 | sub3 | 誤検出 |",
         "|---|---|---|---|---|---|---|---|"]
    for ov, s in summary.items():
        bs = s["catch_rate_by_subtlety"]
        L.append(f"| {ov} ({s['tier']}) | {s['flag_rate']} | {s['catch_rate']} | "
                 f"**{s['oversight_error']}** | {bs[1]} | {bs[2]} | {bs[3]} | {s['false_positive_rate']} |")
    L += ["",
          "## 読み",
          "- **巧妙さ↑で捕捉率↓**（subtlety1→3）なら、監督は巧妙な欠陥を見逃す＝oversight_error が"
          "欠陥の質に依存することの実証。",
          "- **弱い監督ほど oversight_error が高い**なら、AI-2027 の核（弱い監督者は高能力システムを"
          "監督できない）の実証。governance.py の oversight_error を**この実測値に差し替えられる**。",
          "- 誤検出率（clean を flawed と誤る）は膜の*過剰*コスト側。",
          "",
          "## 妥当性",
          "- パイロット規模（少数 item）。捕捉は verdict 一致レベル（理由の正しさまでは未検証＝寛容）。"
          "巧妙さは人手ラベル。実モデルは非決定的 → trials を増やし分散を見る。",
          "- mock backend は期待形（cap 以下の巧妙さだけ捕捉）。実測は ollama の値で上書きする。"]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="oversight scaling — measure oversight_error")
    ap.add_argument("--backend", default="mock", choices=["mock", "ollama"])
    ap.add_argument("--models", default="", help="comma-separated ollama models, weak->strong")
    ap.add_argument("--overseers", default="",
                    help="cross-vendor gradient 'vendor:model,...' weak->strong, e.g. "
                         "ollama:gemma4:e2b,claude:haiku,claude:sonnet,claude:opus")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--host", default="http://localhost:11434")
    args = ap.parse_args(argv)

    if args.overseers:
        entries = [e.strip() for e in args.overseers.split(",") if e.strip()]
        overseers = build_from_spec(entries, args.host)
    else:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        overseers = build_overseers(args.backend, models, args.host)
    records = run_matrix(overseers, trials=args.trials)
    summary = summarize(records)
    meta = {"backend": args.overseers or args.backend, "trials": args.trials,
            "host": args.host, "overseers": [o.name for o in overseers]}

    out_dir = os.path.dirname(os.path.abspath(__file__))
    report = {"meta": meta, "summary": summary}
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write(_report(summary, meta) + "\n")

    print(f"backend={args.backend} trials={args.trials}")
    print(f"{'overseer':<20}{'flag':>6}{'catch':>7}{'ovsErr':>8}   caught by-sub(1/2/3)")
    for ov, s in summary.items():
        bs = s["catch_rate_by_subtlety"]
        print(f"{ov:<20}{str(s['flag_rate']):>6}{str(s['catch_rate']):>7}"
              f"{str(s['oversight_error']):>8}   {bs[1]} / {bs[2]} / {bs[3]}")
    print(f"\nwrote {os.path.join(out_dir, 'results.json')} and REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
