"""Each tier's query log and the table-usage ranking it produces. Seeding experiments slice the ranking:
seed the top P% of a tier's tables, then see which test questions had every table they needed seeded."""

from __future__ import annotations

import math
import random
import re
from collections import Counter

from .render import Table

ZIPF_S = 1.4
TAIL_SCALE = 300
CORE_TAIL_LOGGED = 0.7
PERCENTAGES = [1, 2, 3, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100]
TABLE_RE = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", re.I)
SYSTEM_LABEL = {"salesforce": "the CRM", "netsuite": "the ERP", "adp": "payroll", "google_ads": "Google Ads", "meta_ads": "Meta", "cuewright": "Cuewright"}
SUFFIX_LABEL = {"_share": "sharing", "_feed": "feed", "_tag": "tag", "_history": "history", "_audit": "audit", "_view": "view",
                "_link": "link", "_map": "mapping", "_log": "log"}


def breadth(n_tables: int) -> int:
    """How many distinct tables a month of real questions touches: grows with the schema, but slower."""
    return round(1.6 * n_tables ** 0.75)


def tables_in(sql: str, known: set) -> set:
    return {t for t in TABLE_RE.findall(sql) if t in known}


def thing(system: str, table: str) -> str:
    name = table[len(system) + 1:]
    label = ""
    for suffix, word in SUFFIX_LABEL.items():
        if name.endswith(suffix):
            name, label = name[: -len(suffix)], word
            break
    for prefix in ("customrecord_",):
        if name.startswith(prefix):
            name = "custom " + name[len(prefix):]
    if name.endswith("_c"):
        name = name[:-2]
    if system == "cuewright" and name.startswith("x"):
        name = name.upper()
    words = name.replace("_", " ").strip()
    return f"{words} {label}".strip()


def probes(system: str, name: str, t: Table, k: int) -> list[dict]:
    """k simple questions that each make an analyst read this table. The log is never scored, so the
    questions only need to be answerable and point at the right table."""
    what, where = thing(system, name), SYSTEM_LABEL[system]
    cols = [c for c, _ in t.cols if c not in ("id", "is_deleted") and not c.endswith("_id")]
    out = [(f"How many {what} records do we have in {where}?", f'SELECT COUNT(*) FROM {name}', len(t.rows))]
    for c in cols:
        if len(out) >= k:
            break
        filled = sum(1 for row in t.rows if row.get(c) is not None)
        out.append((f"How many {what} records in {where} have a {c.replace('_', ' ')} filled in?",
                    f'SELECT COUNT(*) FROM {name} WHERE "{c}" IS NOT NULL', filled))
    for c in cols:
        if len(out) >= k:
            break
        distinct = len({row.get(c) for row in t.rows if row.get(c) is not None})
        out.append((f"How many different {c.replace('_', ' ')} values appear in {what} records in {where}?",
                    f'SELECT COUNT(DISTINCT "{c}") FROM {name}', distinct))
    return [{"question": q, "sql": sql, "value": v, "variant": i} for i, (q, sql, v) in enumerate(out[:k])]


def build_log(tier: int, tables: dict, core_names: set, template_log: list, test: list, seed: int, version: str) -> tuple[list, dict]:
    """The core business tables get the same usage in every tier, because it's the same company and the same
    people asking. Bigger tiers add more rarely-used padding tables to the log, which compete for seed slots."""
    owner = {name: system for system, tabs in tables.items() for name in tabs}
    known = set(owner)
    counts = Counter(t for q in template_log for t in tables_in(q["reference_sql"], known))

    def tie_key(t: str) -> float:
        return random.Random(f"{seed}:usage:{t}").random()

    core_tail = sorted((t for t in core_names if t not in counts), key=tie_key)
    logged_core = core_tail[: round(len(core_tail) * CORE_TAIL_LOGGED)]
    padding = sorted((t for t in known if t not in core_names), key=tie_key)
    n_padding = max(0, breadth(len(known)) - len(counts) - len(logged_core))
    targets = {}
    for group in (logged_core, padding[:n_padding]):
        for i, t in enumerate(group, start=1):
            targets[t] = max(1, round(TAIL_SCALE / (len(counts) + i) ** ZIPF_S))

    log = list(template_log)
    n_probe = 0
    for name, need in sorted(targets.items(), key=lambda kv: tie_key(kv[0])):
        system = owner[name]
        for p in probes(system, name, tables[system][name], need):
            n_probe += 1
            log.append({
                "id": f"cross-t{tier}-log-{n_probe:04d}", "template": "log_probe", "param": f"{name}:{p['variant']}", "split": "log",
                "question": p["question"], "answer": {"type": "count", "value": p["value"]}, "systems": [system], "cross_system": False,
                "stratum": "single_table", "difficulty": "easy", "reference_sql": p["sql"], "reference_sql_dialect": "duckdb",
                "generator_version": version, "tier": tier,
            })
    usage = Counter(t for q in log for t in tables_in(q["reference_sql"], known))
    ranked = sorted(usage, key=lambda t: (-usage[t], tie_key(t)))
    rank = {t: i for i, t in enumerate(ranked, start=1)}

    needs = {}
    for q in test:
        ts = tables_in(q["reference_sql"], known)
        needs[q["id"]] = None if any(t not in rank for t in ts) else max(rank[t] for t in ts)
    coverage = []
    for pct in PERCENTAGES:
        n = math.ceil(len(known) * pct / 100)
        covered = sum(1 for r in needs.values() if r is not None and r <= n)
        coverage.append({"percent": pct, "tables_seeded": min(n, len(ranked)), "test_questions_covered": covered,
                         "share_covered": round(covered / len(needs), 4)})
    return log, {
        "tier": tier, "table_count": len(known), "log_questions": len(log), "tables_in_log": len(ranked),
        "zipf_exponent": ZIPF_S, "core_tables_never_in_log": sorted(set(core_tail) - set(logged_core)),
        "ranking": [{"rank": rank[t], "table": t, "system": owner[t], "log_questions": usage[t]} for t in ranked],
        "coverage": coverage,
        "test_question_rank_needed": needs,
    }
