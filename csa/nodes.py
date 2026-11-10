"""Graph nodes: route -> retrieve -> draft -> critic -> (revise -> critic)* -> approve -> answer."""
from __future__ import annotations

import re
from typing import Optional, TypedDict

from langchain_core.runnables import RunnableConfig

from . import llm
from .critic import check
from .store import REL_STRENGTH, SHORT, WORLDS, by_id, records, themes

MAX_REVISIONS = 2


class State(TypedDict, total=False):
    question: str
    intent: str                 # world | connection | entity | theme | communities | not_found
    targets: dict
    evidence: dict              # id -> record (what the drafter may cite)
    claims: list                # [{text, cites, asserts}]
    issues: list                # critic output
    revisions: int
    drafter: str                # "rules" or "claude"
    log: list                   # one line per node, for the trace
    approved: Optional[bool]
    answer: str


def _log(state, line):
    return (state.get("log") or []) + [line]


# ---------------------------------------------------------------- route
def route(state: State) -> State:
    q = state["question"]
    ql = q.lower()
    worlds = [w for w, keys in WORLDS.items()
              if any(re.search(rf"\b{re.escape(k)}\b", ql) for k in keys)
              or any(re.search(rf"\b{s.lower()}\b", ql) for s, f in SHORT.items() if f == w)]

    recs = records()
    names = {r["title"].lower().lstrip("#"): r for r in recs if r["kind"] in ("signal", "rank")}
    # World words ("sports", "beauty") name a world, not a hashtag or community,
    # unless written as a hashtag. Eval run 1 caught "sports" routing to a community.
    world_words = {k for keys in WORLDS.values() for k in keys} | {s.lower() for s in SHORT}
    words = set(re.findall(r"#?[a-z0-9]{3,}", ql))
    tags = [names[w.lstrip("#")]["title"] for w in words
            if w.lstrip("#") in names and (w.startswith("#") or w not in world_words)]
    stop = {"community", "brands", "targeting", "enthusiasts", "identity"} | world_words
    comms = [r["title"] for r in recs if r["kind"] == "community"
             and any(len(t) > 3 and re.search(rf"\b{t}\b", ql) for t in re.findall(r"[a-z]+", r["title"].lower())
                     if t not in stop)]
    th = [t for t in themes() if any(len(w) > 4 and w in ql
                                     for w in re.findall(r"[a-z]+", t.lower()) if w not in {"theme", "candidate"})]

    if re.search(r"\bcommunit(y|ies)\b", ql) and not comms and not tags:
        intent = "communities"
    elif tags or comms:
        intent = "entity"
    elif len(worlds) >= 2 or (worlds and re.search(r"connect|link|between|cross|bridge", ql)):
        intent = "connection"
    elif worlds:
        intent = "world"
    elif th:
        intent = "theme"
    else:
        intent = "not_found"
    targets = {"worlds": worlds, "hashtags": tags, "communities": comms, "themes": th}
    return {"intent": intent, "targets": targets, "revisions": 0,
            "log": _log(state, f"route: intent={intent} targets={ {k: v for k, v in targets.items() if v} }")}


# ---------------------------------------------------------------- retrieve
def retrieve(state: State) -> State:
    t, intent, recs = state["targets"], state["intent"], records()
    ev: list[dict] = []

    def add(rs, n=None):
        for r in rs[:n] if n else rs:
            if r not in ev:
                ev.append(r)

    def in_world(r, w):
        return w in r["worlds"]

    if intent == "world":
        w = t["worlds"][0]
        ranks = [r for r in recs if r["kind"] == "rank" and in_world(r, w) and r["layer"] != "calendar"]
        add(sorted(ranks, key=lambda r: r["rank"]), 8)                                  # top of the list now
        add([r for r in ranks if r["prev_rank"] is None and r["rank"] <= 50], 4)        # new entries
        add(sorted([r for r in ranks if r["prev_rank"] and r["prev_rank"] - r["rank"] >= 20],
                   key=lambda r: r["rank"] - r["prev_rank"]), 4)                        # climbers
        add([r for r in recs if r["kind"] == "bridge" and in_world(r, w)])
        add([r for r in recs if r["kind"] == "community" and r["layer"] == "cultural" and in_world(r, w)], 4)
        add(sorted([r for r in recs if r["kind"] == "signal" and r["layer"] == "cultural" and in_world(r, w)],
                   key=lambda r: -r["posts"]), 5)
        add([r for r in recs if r["kind"] == "commercial" and in_world(r, w)], 2)
    elif intent == "connection":
        ws = t["worlds"][:2]
        both = lambda r: all(w in r["worlds"] for w in ws)
        add([r for r in recs if r["kind"] == "bridge" and both(r)])
        add([r for r in recs if r["kind"] == "community" and r["layer"] == "cultural" and both(r)])
        add([r for r in recs if r["kind"] == "signal" and r["layer"] == "cultural" and both(r)], 6)
    elif intent == "entity":
        for tag in t["hashtags"]:
            add([r for r in recs if r["kind"] in ("signal", "rank") and r["title"].lower() == tag.lower()])
            add([r for r in recs if r["kind"] in ("bridge", "community") and tag.lower() in r["text"].lower()])
        for c in t["communities"]:
            add([r for r in recs if r["title"] == c])
        for r in list(ev):
            if r.get("theme") and r["kind"] == "signal":
                add([b for b in recs if b["kind"] == "bridge" and b["theme"] == r["theme"]])
    elif intent == "theme":
        th = t["themes"][0]
        add([r for r in recs if r["kind"] == "bridge" and r["theme"] == th])
        add([r for r in recs if r["kind"] == "movement" and r["theme"] == th], 5)
        add([r for r in recs if r["kind"] == "community" and r["theme"] == th and r["layer"] == "cultural"])
        add(sorted([r for r in recs if r["kind"] == "signal" and r["theme"] == th and r["layer"] == "cultural"],
                   key=lambda r: -r["posts"]), 5)
    elif intent == "communities":
        add([r for r in recs if r["kind"] == "community"])

    evidence = {r["id"]: r for r in ev[:30]}
    return {"evidence": evidence, "log": _log(state, f"retrieve: {len(evidence)} records")}


# ---------------------------------------------------------------- draft
def _rule_claims(state: State) -> list[dict]:
    """Baseline drafter: one plain claim per record, no model needed."""
    out = []
    for r in state["evidence"].values():
        k = r["kind"]
        if k == "rank":
            text = r["text"] + (" Seasonal or retail moment." if r["layer"] == "calendar" else " Not yet placed against the map.")
        elif k == "bridge":
            text = f"{r['text']} Relationship type: {r['relationship']} ({r['verification']})."
        elif k == "community":
            text = f"{r['text']} Status: {r['verification']}."
        elif k == "movement":
            text = f"{r['text']} Evidence status: {r['verification']}."
        elif k == "commercial":
            text = f"{r['text']} (commercial layer, not cultural evidence)."
        else:
            text = r["text"] + ("." if r["layer"] == "cultural" else " This is a seasonal (calendar) tag.")
        out.append({"text": text, "cites": [r["id"]], "asserts": {"relationship": r.get("relationship")}})
    return out


def draft(state: State) -> State:
    if state["intent"] == "not_found" or not state.get("evidence"):
        return {"claims": [], "drafter": "rules", "log": _log(state, "draft: nothing to draft from")}
    if llm.available():
        claims = llm.draft(state["question"], state["evidence"])
        who = "claude"
    else:
        claims = _rule_claims(state)
        who = "rules"
    return {"claims": claims, "drafter": who, "log": _log(state, f"draft ({who}): {len(claims)} claims")}


# ---------------------------------------------------------------- critic
def critic(state: State) -> State:
    issues = check(state.get("claims") or [], state.get("evidence") or {})
    rules = sorted({i["rule"] for i in issues})
    return {"issues": issues, "log": _log(state, f"critic: {len(issues)} issues {rules if rules else ''}".strip())}


def after_critic(state: State) -> str:
    if state.get("issues") and state.get("revisions", 0) < MAX_REVISIONS:
        return "revise"
    return "approve"


# ---------------------------------------------------------------- revise
def _downgrade(claim: dict, issue: dict, evidence: dict) -> Optional[dict]:
    c = {**claim, "asserts": dict(claim.get("asserts") or {})}
    rule = issue["rule"]
    if rule == "R1_CITATION":
        keep = [x for x in c.get("cites") or [] if x in evidence]
        if not keep:
            return None
        c["cites"] = keep
    elif rule == "R2_RELATIONSHIP":
        known = [evidence[x] for x in c["cites"] if x in evidence]
        allowed = max((r.get("relationship") for r in known), key=lambda x: REL_STRENGTH.get(x, 0))
        c["text"] = re.sub(r"\b(adopt(?:ed|ion|ing|s)?|taken up by|picked up by)\b", "used in", c["text"], flags=re.I)
        c["text"] = re.sub(r"\b(spread(?:s|ing)? (?:from|to|into|via|through)|mov(?:ed|ing) (?:from|into)|migrat\w+|jump(?:ed|ing) (?:from|to))\b",
                           "appearing via", c["text"], flags=re.I)
        c["text"] += f" (Relationship: {allowed or 'none established'}; not verified adoption or transmission.)"
        c["asserts"]["relationship"] = allowed
    elif rule == "R3_COMMUNITY":
        c["text"] = re.sub(r"\b(verified|confirmed|established|proven) community\b", "candidate community", c["text"], flags=re.I)
        c["asserts"]["community_verified"] = False
    elif rule == "R4_MOVEMENT":
        c["text"] = re.sub(r"\b(established|proven|well-documented) (movement|trend)\b", r"possible \2", c["text"], flags=re.I)
        c["asserts"]["movement_established"] = False
    elif rule == "R5_COMMERCIAL_ONLY":
        c["text"] = "Commercial layer (ads or creator partnerships, not cultural evidence): " + c["text"]
    elif rule == "R6_CALENDAR":
        c["text"] = re.sub(r"\b(emerging|rising|new) trend\b|\btrending up\b", "seasonal tag", c["text"], flags=re.I)
        c["asserts"]["trend_new"] = False
    elif rule == "R7_CERTAINTY":
        c["text"] = re.sub(r"\b(definitely|certainly|undeniably|clearly proves|guaranteed|proves that)\b ?", "",
                           c["text"], flags=re.I)
        c["asserts"].pop("certainty", None)
    return c


def revise(state: State) -> State:
    claims, issues, ev = list(state["claims"]), state["issues"], state["evidence"]
    if llm.available():
        claims = llm.revise(state["question"], ev, claims, issues)
        how = "claude"
    else:
        for iss in sorted(issues, key=lambda x: -x["claim"]):
            fixed = _downgrade(claims[iss["claim"]], iss, ev)
            if fixed is None:
                claims.pop(iss["claim"])
            else:
                claims[iss["claim"]] = fixed
        how = "rules"
    n = state.get("revisions", 0) + 1
    return {"claims": claims, "revisions": n, "log": _log(state, f"revise {n} ({how}): {len(issues)} issues addressed")}


# ---------------------------------------------------------------- approve (human in the loop)
def approve(state: State, config: RunnableConfig) -> State:
    cfg = (config or {}).get("configurable", {})
    if not cfg.get("require_approval"):
        return {"approved": None, "log": _log(state, "approve: skipped (not required)")}
    from langgraph.types import interrupt
    decision = interrupt({"claims": state.get("claims"), "open_issues": state.get("issues")})
    ok = str(decision).strip().lower() in {"y", "yes", "approve", "true"}
    return {"approved": ok, "log": _log(state, f"approve: {'approved' if ok else 'rejected'} by reviewer")}


# ---------------------------------------------------------------- answer
def answer(state: State) -> State:
    if state.get("approved") is False:
        return {"answer": "Held back: the reviewer did not approve this answer.", "log": _log(state, "answer: held")}
    if state["intent"] == "not_found" or not state.get("claims"):
        msg = ("Not in the tracker data. Agent 1 tracks six worlds (Sports, Gaming, Music, Fashion, Beauty, Food) "
               "from the October 2026 snapshot; this question doesn't match a world, theme, hashtag or community in it. "
               "That is not evidence it isn't happening; it may sit outside what the tracker captures.")
        return {"answer": msg, "log": _log(state, "answer: not found")}
    ev = state["evidence"]
    lines = [f"Q: {state['question']}", ""]
    for c in state["claims"]:
        lvl = max(ev[x]["level"] for x in c["cites"] if x in ev)
        conf = {0: "placement / lead", 1: "traced", 2: "verified"}[lvl]
        lines.append(f"- {c['text']}  [{', '.join(c['cites'])}] ({conf})")
    if state.get("issues"):
        lines += ["", "Open issues the critic could not resolve:"] + [f"- {i['rule']}: {i['message']}" for i in state["issues"]]
    lines += ["", "Nothing here is verified adoption or transmission; links are placements, traces or observed cross-world use."]
    return {"answer": "\n".join(lines), "log": _log(state, "answer: done")}
