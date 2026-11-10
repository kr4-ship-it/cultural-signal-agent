"""The evidence critic: rule-based on purpose.

These are the tracker's evidence rules (method v0.4.1, sections 3 and 9),
written as code. A model drafts the answer; it does not get to grade it. Each
rule returns an issue with a rule id, the claim it concerns and a fix
instruction that the revise step can act on.
"""
from __future__ import annotations

import re

from .store import REL_STRENGTH

NEG = r"(?:not|no|never|isn't|aren't|without|unverified|rather than|instead of|n't|yet to be)"

# Words in a claim's text that assert a relationship, community status or certainty.
TEXT_PATTERNS = [
    ("adoption", re.compile(r"\b(adopt(?:ed|ion|ing|s)?|taken up by|picked up by)\b", re.I)),
    ("transmission", re.compile(r"\b(spread(?:s|ing)? (?:from|to|into|via|through)|mov(?:ed|ing) (?:from|into)|migrat\w+|jump(?:ed|ing) (?:from|to))\b", re.I)),
]
VERIFIED_COMMUNITY = re.compile(r"\b(verified|confirmed|established|proven) community\b", re.I)
ESTABLISHED = re.compile(r"\b(established|proven|well-documented) (?:movement|trend)\b", re.I)
CERTAINTY = re.compile(r"\b(definitely|certainly|undeniably|clearly proves|guaranteed|proves that)\b", re.I)
TREND_WORDS = re.compile(r"\b(emerging|rising|new) trend\b|\btrending up\b", re.I)
COMMERCIAL_WORDS = re.compile(r"\b(ad|ads|advertis\w*|brand\w*|partnership\w*|audience\w*|commercial|paid|sponsor\w*)\b", re.I)


def _negated(text: str, start: int) -> bool:
    window = text[max(0, start - 40):start]
    return re.search(NEG + r"\W+(?:\w+\W+){0,3}$", window, re.I) is not None


def _asserted(claim: dict) -> dict:
    """What the claim asserts: its declared fields, plus anything its wording asserts."""
    a = dict(claim.get("asserts") or {})
    text = claim.get("text", "")
    for rel, pat in TEXT_PATTERNS:
        for m in pat.finditer(text):
            if not _negated(text, m.start()):
                if REL_STRENGTH.get(rel, 0) > REL_STRENGTH.get(a.get("relationship"), 0):
                    a["relationship"] = rel
    for pat, key in ((VERIFIED_COMMUNITY, "community_verified"), (ESTABLISHED, "movement_established"),
                     (TREND_WORDS, "trend_new")):
        m = pat.search(text)
        if m and not _negated(text, m.start()):
            a[key] = True
    m = CERTAINTY.search(text)
    if m:
        a["certainty"] = m.group(0)
    return a


def check(claims: list[dict], evidence: dict[str, dict]) -> list[dict]:
    issues: list[dict] = []

    def flag(rule, i, msg, fix):
        issues.append({"rule": rule, "claim": i, "message": msg, "fix": fix})

    for i, c in enumerate(claims):
        cites = c.get("cites") or []
        known = [evidence[x] for x in cites if x in evidence]
        a = _asserted(c)

        # R1: every claim cites evidence that was actually retrieved.
        if not cites:
            flag("R1_CITATION", i, "Claim cites no evidence.", "Cite a retrieved record or drop the claim.")
            continue
        missing = [x for x in cites if x not in evidence]
        if missing:
            flag("R1_CITATION", i, f"Cites records that were not retrieved: {missing}.",
                 "Cite only retrieved records, or drop the claim.")
        if not known:
            continue

        # R2: the relationship asserted cannot be stronger than the evidence.
        rel = a.get("relationship")
        best = max(known, key=lambda r: REL_STRENGTH.get(r.get("relationship"), 0))
        if REL_STRENGTH.get(rel, 0) > REL_STRENGTH.get(best.get("relationship"), 0):
            allowed = best.get("relationship") or "no relationship"
            flag("R2_RELATIONSHIP", i,
                 f"Asserts '{rel}', but the strongest cited evidence supports only '{allowed}' ({best['verification']}).",
                 f"Describe it as '{allowed}' and say {rel} is not verified.")

        # R3: a verified community needs a verified community record. None exists yet.
        if a.get("community_verified") and not any(r["kind"] == "community" and r["level"] >= 2 for r in known):
            flag("R3_COMMUNITY", i, "Calls a community verified; no cited community meets the community test.",
                 "Say it is traced or a candidate, not verified.")

        # R4: an established movement needs 2+ Tier 1-2 sources.
        if a.get("movement_established") and not any(r["kind"] == "movement" and r["level"] >= 2 for r in known):
            flag("R4_MOVEMENT", i, "Calls something established without a movement that meets the two-source rule.",
                 "Remove 'established' or cite a movement that meets the rule.")

        # R5: commercial evidence alone is not cultural evidence.
        if all(r["layer"] == "commercial" for r in known) and not COMMERCIAL_WORDS.search(c.get("text", "")):
            flag("R5_COMMERCIAL_ONLY", i, "A cultural claim rests only on ads or creator partnerships.",
                 "Label it as the commercial layer, or cite cultural evidence.")

        # R6: calendar tags are seasonal, not trends.
        if a.get("trend_new") and all(r["layer"] == "calendar" for r in known):
            flag("R6_CALENDAR", i, "Calls a seasonal (calendar) tag a trend.", "Describe it as seasonal.")

        # R7: no certainty language. One month of data.
        if a.get("certainty"):
            flag("R7_CERTAINTY", i, f"Uses certainty language ('{a['certainty']}') on one snapshot.",
                 "Remove it; state the confidence instead.")

    return issues
