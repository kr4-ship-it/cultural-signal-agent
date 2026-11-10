"""Loads the frozen tracker snapshot into one list of evidence records.

Every record has the same shape, so the critic can check any claim against
any kind of evidence with the same rules:

  id            stable id the answer must cite, e.g. "signal:#bulin47"
  kind          signal | rank | bridge | community | movement | commercial
  layer         cultural | commercial | landscape | calendar | ranking
  title, text   what the record says
  theme         theme name (or None)
  worlds        subset of the six worlds
  relationship  the strongest relationship type this record can support
  verification  plain-language verification status, as recorded
  level         0 = placement/lead, 1 = traced/observed, 2 = verified
  first_observed_at, last_checked_at, refs
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

WORLDS = {
    "Sports & competition": ["sport", "sports", "football", "nfl", "fitness", "training", "gym", "competition"],
    "Gaming & digital worlds": ["gaming", "game", "games", "gamer", "gamers", "digital"],
    "Music & dance": ["music", "dance", "song", "sound", "concert"],
    "Fashion": ["fashion", "clothing", "outfit", "outfits", "style", "apparel"],
    "Beauty": ["beauty", "skincare", "makeup", "hair", "personal care"],
    "Food": ["food", "eating", "cooking", "drink", "drinks", "recipe"],
}
SHORT = {"Sports": "Sports & competition", "Gaming": "Gaming & digital worlds", "Music": "Music & dance",
         "Fashion": "Fashion", "Beauty": "Beauty", "Food": "Food"}

# Creative Center industry lists used for the monthly top-100 rankings.
INDUSTRY_WORLD = {"14000000000": "Beauty", "22000000000": "Fashion", "25000000000": "Gaming & digital worlds",
                  "27000000000": "Food", "28000000000": "Sports & competition"}

# Relationship types (method v0.4.1). Types, not a ladder, but each one needs at
# least this much evidence, so a claim may not assert a stronger type than its
# evidence supports.
REL_STRENGTH = {
    None: 0,
    "co-occurrence": 1,
    "shared meaning": 1,
    "cross-world use observed": 2,
    "affinity": 3,
    "adoption": 3,
    "transmission": 4,
}


def _worlds(text) -> list[str]:
    if isinstance(text, list):
        text = " | ".join(text)
    text = str(text or "")
    out = [full for full in WORLDS if full in text]
    for short, full in SHORT.items():
        if re.search(rf"\b{short}\b", text) and full not in out:
            out.append(full)
    return out


def _load(name):
    return json.loads((DATA / name).read_text())


@lru_cache(maxsize=1)
def records() -> list[dict]:
    recs: list[dict] = []

    for s in _load("dash_signals.json"):
        cal = s["outcome"] == "Calendar"
        recs.append(dict(
            id=f"signal:{s['hashtag']}", kind="signal", layer="calendar" if cal else "cultural",
            title=s["hashtag"],
            text=(f"{s['hashtag']}: {s['outcome']}; {s['shape']}; {s.get('posts') or 0:,} posts; "
                  f"placed under {s['theme']}" + (f" / {s['movement']}" if s.get("movement") else "")
                  + (f". Note: {s['note']}" if s.get("note") else "")),
            theme=None if s["theme"] == "UNPLACED" else s["theme"], worlds=_worlds(s["world"]),
            relationship=None if cal else "shared meaning",
            verification="calendar (seasonal, not a trend)" if cal else "placement unverified",
            level=0, outcome=s["outcome"], posts=s.get("posts") or 0,
            first_observed_at="2026-10-19", last_checked_at="2026-10-22",
            refs="snapshots/cc_hashtags_US_30d_2026-10-22.json"))

    for b in _load("dash_bridges.json"):
        rel = b["step_name"].lower()
        recs.append(dict(
            id=f"bridge:{b['theme']}", kind="bridge", layer="cultural", title=f"{b['theme']} bridge",
            text=f"{b['theme']} links {b['worlds']}: {b['link']} Crossover evidence: {b['crossover_evidence']}",
            theme=b["theme"], worlds=_worlds(b["worlds"]), relationship=rel,
            verification=b["verification_status"], level=1 if rel == "cross-world use observed" else 0,
            commercial=b.get("commercial"), first_observed_at=b["first_observed_at"],
            last_checked_at=b["last_checked_at"], refs=b["evidence_refs"]))

    for c in _load("dash_communities.json"):
        aud = c["label"].startswith("AUDIENCE")
        traced = str(c["status"]).startswith("Traced")
        recs.append(dict(
            id=f"community:{c['community']}", kind="community", layer="commercial" if aud else "cultural",
            title=c["community"],
            text=f"{c['community']} ({c['label']}; {c['status']}). Evidence: {c['evidence']}",
            theme=c["theme"], worlds=_worlds(c["worlds"]),
            relationship="cross-world use observed" if traced and len(_worlds(c["worlds"])) > 1 else "shared meaning",
            verification=c["verification"], level=1 if traced else 0, label=c["label"],
            first_observed_at=c["first_observed_at"], last_checked_at=c["last_checked_at"],
            refs="dash_communities.json"))

    for m in _load("dash_movements.json"):
        recs.append(dict(
            id=f"movement:{m['id']}", kind="movement", layer="landscape", title=f"{m['id']} {m['movement']}",
            text=f"{m['id']} {m['movement']} ({m['stage']}). {m['what']} Sources: {m['sources']}.",
            theme=m["theme"], worlds=_worlds(m["world"]), relationship=None,
            verification=m["evidence_status"], level=2 if m["evidence_status"].startswith("Meets") else 0,
            first_observed_at="2026-10-15", last_checked_at="2026-10-21", refs=f"movements: {m['sources']}"))

    for i, l in enumerate(_load("dash_links.json")):
        if l["layer"] != "Commercial":
            continue
        recs.append(dict(
            id=f"commercial:{i}", kind="commercial", layer="commercial", title=l["evidence"],
            text=f"Commercial layer ({l['kind']}): {l['evidence']}. {l.get('detail') or ''}".strip(),
            theme=l["theme"], worlds=l.get("worlds") or [], relationship=None,
            verification=l["verification_status"], level=0,
            first_observed_at=l["first_observed_at"], last_checked_at=l["last_checked_at"],
            refs=l["evidence_refs"]))

    recs.extend(_rank_records())
    return recs


CALENDAR = re.compile(r"halloween|spooky|october|november|december|bfcm|blackfriday|cybermonday|christmas|xmas|"
                      r"thanksgiving|holiday|winter20|fall20|autumn|fallvibes|diwali|navratri|trickortreat|"
                      r"costume|pumpkin|deals|sale|tiktokshop|primeday|advent|giftguide|gifts?\b|newyear", re.I)


def _rank_records() -> list[dict]:
    """Top-100 hashtag ranks per world list: Oct 22 vs Nov 4 (Creative Center, US, 30 days)."""
    old = _load("cc_hashtags_US_30d_2026-10-22.json")
    new = _load("cc_hashtags_US_30d_2026-11-04.json")
    out = []
    for ind, world in INDUSTRY_WORLD.items():
        before = {h["n"]: h["r"] for h in old.get(ind, [])}
        for h in new.get(ind, []):
            r0 = before.get(h["n"])
            move = "new to the list" if r0 is None else (f"up {r0 - h['r']} places" if r0 > h["r"]
                                                         else f"down {h['r'] - r0} places" if r0 < h["r"] else "unchanged")
            cal = bool(CALENDAR.search(h["n"]))
            out.append(dict(
                id=f"rank:{world}:#{h['n']}", kind="rank", layer="calendar" if cal else "ranking", title=f"#{h['n']}",
                text=f"#{h['n']} is #{h['r']} in the {world} top 100 on Nov 4 ({move} since Oct 22; {int(h['vv']):,} views).",
                theme=None, worlds=[world], relationship=None,
                verification="calendar / retail moment" if cal else "ranking only: not yet placed against the map",
                level=0,
                rank=h["r"], prev_rank=r0, hashtag=f"#{h['n']}",
                first_observed_at="2026-10-22" if r0 else "2026-11-04", last_checked_at="2026-11-04",
                refs="snapshots/cc_hashtags_US_30d_2026-11-04.json"))
    return out


def by_id() -> dict[str, dict]:
    return {r["id"]: r for r in records()}


def themes() -> list[str]:
    return [t["theme"] for t in _load("dash_themes.json") if t["theme"] != "UNPLACED"]
