"""Run both evaluation sets and write evals/results.md.

1. Critic traps: known overclaims (several taken from the October review) and
   clean claims. Measures whether the critic catches what it should and
   leaves correct claims alone.
2. Questions: end-to-end runs through the graph. Checks routing, required
   evidence, required and forbidden wording, and that the final answer has
   no unresolved critic issues.

    python evals/run_evals.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from csa import llm  # noqa: E402
from csa.critic import check  # noqa: E402
from csa.graph import build  # noqa: E402
from csa.store import by_id, records  # noqa: E402

E = Path(__file__).resolve().parent


def resolve(cite: str) -> str:
    recs = records()
    if cite == "@commercial_strength":
        return next(r["id"] for r in recs if r["kind"] == "commercial" and "fitness and wellness" in r["text"].lower())
    if cite == "@calendar_any":
        return next(r["id"] for r in recs if r["kind"] == "signal" and r["layer"] == "calendar")
    return cite


def run_traps():
    traps = json.loads((E / "critic_traps.json").read_text())
    ev = by_id()
    rows, tp, fn, fp, tn = [], 0, 0, 0, 0
    for t in traps:
        claims = [{**c, "cites": [resolve(x) for x in c["cites"]]} for c in t["claims"]]
        got = sorted({i["rule"] for i in check(claims, ev)})
        exp = sorted(t["expect"])
        ok = got == exp
        if exp:
            tp += ok
            fn += not ok
        else:
            tn += ok
            fp += not ok
        rows.append((t["id"], t["note"], ", ".join(exp) or "none", ", ".join(got) or "none", ok))
    return rows, dict(caught=tp, missed=fn, clean_passed=tn, false_flags=fp)


def run_questions():
    qs = json.loads((E / "questions.json").read_text())
    app = build()
    rows = []
    for i, q in enumerate(qs):
        t0 = time.time()
        out = app.invoke({"question": q["q"]}, {"configurable": {"thread_id": f"eval-{i}"}})
        ans, cites = out["answer"], {c for cl in out.get("claims") or [] for c in cl["cites"]}
        checks = {"intent": out["intent"] == q["intent"]}
        if "cite_any" in q:
            checks["evidence"] = bool(cites & set(q["cite_any"]))
        for s in q.get("text_all", []):
            checks[f"says '{s}'"] = s.lower() in ans.lower()
        for s in q.get("text_none", []):
            checks[f"avoids '{s}'"] = s.lower() not in ans.lower()
        if "min_claims" in q:
            checks["enough evidence"] = len(out.get("claims") or []) >= q["min_claims"]
        checks["critic clean"] = not out.get("issues")
        rows.append(dict(id=q["id"], q=q["q"], ok=all(checks.values()),
                         failed=[k for k, v in checks.items() if not v],
                         revisions=out.get("revisions", 0), claims=len(out.get("claims") or []),
                         secs=round(time.time() - t0, 2)))
    return rows


def main():
    traps, ts = run_traps()
    qs = run_questions()
    drafter = "Claude (" + llm.MODEL + ")" if llm.available() else "rule-based baseline (no API key set)"
    n_ok = sum(r["ok"] for r in qs)
    revised = sum(1 for r in qs if r["revisions"])
    lines = [
        "# Evaluation results", "",
        f"Run: {time.strftime('%Y-%m-%d %H:%M')} · drafter: {drafter} · data: October 2026 snapshot + Nov 4 ranks", "",
        "## 1. Critic traps", "",
        f"Overclaims caught: **{ts['caught']}/{ts['caught'] + ts['missed']}** · "
        f"clean claims left alone: **{ts['clean_passed']}/{ts['clean_passed'] + ts['false_flags']}**", "",
        "| Case | What it tests | Expected | Flagged | Pass |", "|---|---|---|---|---|",
        *[f"| {a} | {b} | {c} | {d} | {'✅' if e else '❌'} |" for a, b, c, d, e in traps], "",
        "## 2. Questions (end to end)", "",
        f"Passed: **{n_ok}/{len(qs)}** · answers that needed a revision loop: {revised}", "",
        "| Case | Question | Pass | Failed checks | Revisions | Claims |", "|---|---|---|---|---|---|",
        *[f"| {r['id']} | {r['q']} | {'✅' if r['ok'] else '❌'} | {', '.join(r['failed']) or '—'} | {r['revisions']} | {r['claims']} |" for r in qs],
    ]
    (E / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
