"""Optional Claude drafter. Used only when ANTHROPIC_API_KEY is set.

The model writes claims in a fixed JSON shape and declares what each claim
asserts. The critic re-checks the wording anyway, so an under-declared
assertion is still caught.
"""
from __future__ import annotations

import json
import os

MODEL = os.environ.get("CSA_MODEL", "claude-sonnet-4-5")

SYSTEM = """You answer questions about a brand-blind cultural signal tracker.
Use ONLY the evidence records given. Each claim must cite record ids from them.
Relationship types (weakest to strongest evidence): co-occurrence, shared meaning,
cross-world use observed, adoption (verified: 5+ unrelated creators, dated), transmission.
Never assert a relationship stronger than the cited record's "relationship" field.
Ads and creator partnerships are commercial, not cultural evidence; say so.
Calendar tags are seasonal, not trends. No certainty words. Plain language.
Return JSON only: {"claims":[{"text":"...","cites":["id",...],
"asserts":{"relationship":null|"<type>","community_verified":false,"movement_established":false,"trend_new":false}}]}"""


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _call(prompt: str) -> list[dict]:
    from langchain_anthropic import ChatAnthropic
    model = ChatAnthropic(model=MODEL, temperature=0, max_tokens=2000)
    out = model.invoke([("system", SYSTEM), ("human", prompt)]).content
    if isinstance(out, list):
        out = "".join(p.get("text", "") for p in out if isinstance(p, dict))
    out = out[out.find("{"): out.rfind("}") + 1]
    return json.loads(out)["claims"]


def _ev(evidence: dict) -> str:
    keep = ("id", "kind", "layer", "text", "theme", "worlds", "relationship", "verification")
    return json.dumps([{k: r.get(k) for k in keep} for r in evidence.values()], ensure_ascii=False)


def draft(question: str, evidence: dict) -> list[dict]:
    return _call(f"Question: {question}\n\nEvidence records:\n{_ev(evidence)}\n\nWrite 3-7 claims that answer it.")


def revise(question: str, evidence: dict, claims: list, issues: list) -> list[dict]:
    return _call(f"Question: {question}\n\nEvidence records:\n{_ev(evidence)}\n\nYour draft:\n"
                 f"{json.dumps(claims, ensure_ascii=False)}\n\nThe evidence critic found:\n"
                 f"{json.dumps(issues, ensure_ascii=False)}\n\nRewrite the claims so every issue is fixed.")
