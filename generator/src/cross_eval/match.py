"""Fuzzy answer matching, as published in MATCHING.md. An extractor (an LLM that never sees the gold
answer) turns a reply into a claim; these fixed rules decide whether the claim matches the gold answer.

A claim is {"values": [...], "sig_figs": int | None, "clarifying": bool}. For entity lists and rankings,
"values" holds the listed items in reply order."""

from __future__ import annotations

import math
import re
from datetime import date
from difflib import SequenceMatcher

DEFAULT_TOLERANCE = {"money": 0.01, "number": 0.01, "percent": 0.01, "count": 0.0}
DEFAULT_MIN_SIG_FIGS = 2
NAME_SIMILARITY = 0.88
LEGAL_SUFFIXES = re.compile(r"\b(inc|llc|corp|co|corporation|company|ltd|group|holdings)\b\.?", re.I)


def normalize_name(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = LEGAL_SUFFIXES.sub(" ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def round_sig(x: float, sig: int) -> float:
    if x == 0:
        return 0.0
    return round(x, sig - 1 - int(math.floor(math.log10(abs(x)))))


def number_matches(gold: float, claim: float, tolerance: float, sig_figs: int | None, min_sig_figs: int) -> bool:
    if gold == 0:
        return abs(claim) <= 1e-9
    if abs(claim - gold) <= abs(gold) * tolerance + 1e-9:
        return True
    return sig_figs is not None and sig_figs >= min_sig_figs and math.isclose(round_sig(gold, sig_figs), claim, rel_tol=1e-9, abs_tol=1e-9)


def entity_matches(names: list[str], claim: str) -> bool:
    c = normalize_name(claim)
    for n in names:
        g = normalize_name(n)
        if c == g or SequenceMatcher(None, c, g).ratio() >= NAME_SIMILARITY:
            return True
    return False


def date_matches(gold: str, claim: str, granularity: str) -> bool:
    g, c = date.fromisoformat(gold), date.fromisoformat(claim)
    if granularity == "year":
        return g.year == c.year
    if granularity == "month":
        return (g.year, g.month) == (c.year, c.month)
    return g == c


def _single(answer: dict, value, claim: dict) -> bool:
    t = answer["type"]
    if t in ("money", "number", "percent", "count"):
        if not isinstance(claim, (int, float)):
            return False
        tol = answer.get("tolerance", DEFAULT_TOLERANCE[t])
        if t == "count" and "tolerance" not in answer:
            return float(claim) == float(value)
        return number_matches(float(value), float(claim), tol, answer.get("_sig_figs"), answer.get("min_sig_figs", DEFAULT_MIN_SIG_FIGS))
    if t == "entity":
        return isinstance(claim, str) and entity_matches([value] + answer.get("aliases", []), claim)
    if t == "date":
        return date_matches(value, claim, answer.get("granularity", "day"))
    if t == "yes_no":
        return str(claim).strip().lower() in (("yes", "true") if value else ("no", "false"))
    raise ValueError(f"unknown answer type {t}")


def _list_matches(answer: dict, gold: list, claims: list, ordered: bool) -> bool:
    aliases = answer.get("aliases", {})
    item = {**answer, "type": "entity"}
    if ordered:
        return len(claims) == len(gold) and all(
            _single({**item, "aliases": aliases.get(g, [])}, g, c) for g, c in zip(gold, claims))
    unmatched = list(claims)
    for g in gold:
        hit = next((c for c in unmatched if _single({**item, "aliases": aliases.get(g, [])}, g, c)), None)
        if hit is None:
            return False
        unmatched.remove(hit)
    return not unmatched or not answer.get("complete_set", True)


def match(answer: dict, claim: dict) -> dict:
    """Returns {"correct": bool, "reading": str | None, "clarifying": bool}."""
    if claim.get("clarifying") and not claim.get("values"):
        return {"correct": False, "reading": None, "clarifying": True}
    values = claim.get("values", [])
    readings = [(None, answer["value"])] + [(a["reading"], a["value"]) for a in answer.get("accepted", [])]
    scoped = {**answer, "_sig_figs": claim.get("sig_figs")}
    if answer["type"] in ("entity_list", "ranked_list"):
        for reading, gold in readings:
            if _list_matches(scoped, gold, values, ordered=answer["type"] == "ranked_list"):
                return {"correct": True, "reading": reading, "clarifying": False}
        return {"correct": False, "reading": None, "clarifying": False}
    if not values:
        return {"correct": False, "reading": None, "clarifying": False}
    matched_reading = None
    for v in values:
        hit = next((reading for reading, gold in readings if _single(scoped, gold, v)), "__miss__")
        if hit == "__miss__":
            return {"correct": False, "reading": None, "clarifying": False}
        matched_reading = matched_reading or hit
    return {"correct": True, "reading": matched_reading, "clarifying": False}
