"""Builds the dataset: simulate, render, widen per tier, write Parquet, generate and verify questions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import duckdb

from .questions import generate
from .render import render
from .usage import build_log
from .width import TIER_TARGETS, widen
from .world import simulate

GENERATOR_VERSION = "0.2.0"
DEFAULT_SEED = 20261112
ARROW = {"str": pa.string(), "int": pa.int64(), "float": pa.float64(), "bool": pa.bool_(), "date": pa.date32()}


def to_arrow(t) -> pa.Table:
    schema = pa.schema([(c, ARROW[k]) for c, k in t.cols])
    return pa.Table.from_pydict({c: [row.get(c) for row in t.rows] for c, _ in t.cols}, schema=schema)


def write_tier(tables: dict, out: Path, core_names: set) -> dict:
    manifest = {"tables": []}
    for system in sorted(tables):
        (out / system).mkdir(parents=True, exist_ok=True)
        for name in sorted(tables[system]):
            t = tables[system][name]
            pq.write_table(to_arrow(t), out / system / f"{name}.parquet", compression="zstd", write_statistics=True)
            manifest["tables"].append({"system": system, "table": name, "role": "core" if name in core_names else "padding", "rows": len(t.rows),
                                       "columns": [{"name": c, "type": k} for c, k in t.cols]})
    manifest["column_count"] = sum(len(t["columns"]) for t in manifest["tables"])
    manifest["table_count"] = len(manifest["tables"])
    return manifest


def verify(questions: list, tier_dir: Path) -> list:
    """Runs every reference query against a tier and returns the questions whose result disagrees with gold."""
    con = duckdb.connect()
    for f in sorted(tier_dir.glob("*/*.parquet")):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f}')")
    bad = []
    for q in questions:
        a = q["answer"]
        try:
            got = con.execute(q["reference_sql"]).fetchone()[0]
        except Exception as e:  # noqa: BLE001 - reported with the question it broke
            bad.append((q, f"error: {e}"))
            continue
        if a["type"] == "entity":
            ok = got == a["value"] or got in a.get("aliases", [])
        elif a["type"] == "count":
            ok = got is not None and int(got) == a["value"]
        else:
            ok = got is not None and abs(float(got) - a["value"]) <= 0.05 + 1e-6 * abs(a["value"])
        if not ok:
            bad.append((q, got))
    return bad


def write_jsonl(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def check(label: str, bad: list, total: int) -> None:
    print(f"{label}: {total - len(bad)}/{total} reference queries reproduce gold")
    for q, got in bad[:40]:
        print("  MISMATCH", q["id"], q["template"], q["param"], "gold", q["answer"]["value"], "sql", got)
    if bad:
        raise SystemExit(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--tiers", default="1,2,3,4")
    args = ap.parse_args()
    tiers = [int(x) for x in args.tiers.split(",")]
    world = simulate(args.seed)
    core = render(world)
    core_names = {n for tabs in core.values() for n in tabs}
    questions = generate(world, core, GENERATOR_VERSION)
    test = [q for q in questions if q["split"] == "test"]
    template_log = [q for q in questions if q["split"] == "log"]
    usages = {}
    for tier in tiers:
        tables = widen(core, args.seed, tier)
        tier_dir = args.out / "data" / f"tier-{tier}"
        manifest = write_tier(tables, tier_dir, core_names)
        manifest.update({"tier": tier, "target_columns": TIER_TARGETS[tier], "seed": args.seed, "generator_version": GENERATOR_VERSION})
        (args.out / "schema").mkdir(parents=True, exist_ok=True)
        (args.out / "schema" / f"tier-{tier}.json").write_text(json.dumps(manifest, indent=1) + "\n")
        print(f"tier {tier}: {manifest['table_count']} tables, {manifest['column_count']} columns")
        log, usage = build_log(tier, tables, core_names, template_log, test, args.seed, GENERATOR_VERSION)
        check(f"tier {tier} log", verify(log, tier_dir), len(log))
        write_jsonl(args.out / "questions" / f"log-tier-{tier}.jsonl", log)
        (args.out / "usage").mkdir(parents=True, exist_ok=True)
        (args.out / "usage" / f"tier-{tier}.json").write_text(json.dumps(usage, indent=1) + "\n")
        usages[tier] = usage
    for tier in (tiers[0], tiers[-1]):
        check(f"tier {tier} test", verify(test, args.out / "data" / f"tier-{tier}"), len(test))
    write_jsonl(args.out / "questions" / "test.jsonl", test)
    print(f"{len(test)} test questions written")
    write_docs(args.out, world, test, usages, tiers)


def write_docs(out: Path, world, test: list, usages: dict, tiers: list) -> None:
    docs = Path(__file__).resolve().parents[2] / "dataset_docs"
    manifests = {t: json.loads((out / "schema" / f"tier-{t}.json").read_text()) for t in tiers}
    tier_rows = ["| Tier | Tables | Columns | Size on disk |", "|---|---|---|---|"]
    for t, m in manifests.items():
        size = sum(f.stat().st_size for f in (out / "data" / f"tier-{t}").rglob("*.parquet"))
        tier_rows.append(f"| {t} | {m['table_count']:,} | {m['column_count']:,} | {size / 1e6:.1f} MB |")
    strata = ["single_table", "single_system_join", "cross_system"]
    q_rows = ["| Stratum | Test questions |", "|---|---|"]
    for s_ in strata:
        q_rows.append(f"| `{s_}` | {sum(q['stratum'] == s_ for q in test)} |")
    q_rows.append(f"| Total | {len(test)} |")
    log_rows = ["| Tier | Log questions | Tables the log touches | Share of the tier's tables |", "|---|---|---|---|"]
    for t, u in usages.items():
        log_rows.append(f"| {t} | {u['log_questions']:,} | {u['tables_in_log']} | {u['tables_in_log'] / u['table_count']:.0%} |")
    cov_rows = ["| Seed the top… | " + " | ".join(f"Tier {t}" for t in tiers) + " |", "|---|" + "---|" * len(tiers)]
    for i, pct in enumerate(usages[tiers[0]]["coverage"]):
        cells = []
        for t in tiers:
            c = usages[t]["coverage"][i]
            n = c["tables_seeded"]
            cells.append(f"{n} table{'' if n == 1 else 's'}, {c['share_covered']:.0%}")
        cov_rows.append(f"| {pct['percent']}% | " + " | ".join(cells) + " |")
    core = [t for t in manifests[tiers[0]]["tables"] if t["role"] == "core"]
    stat_rows = ["Core tables (identical in every tier):", "", "| System | Tables | Rows |", "|---|---|---|"]
    for system in sorted({t["system"] for t in core}):
        ts = [t for t in core if t["system"] == system]
        stat_rows.append(f"| {system} | {len(ts)} | {sum(t['rows'] for t in ts):,} |")
    example = next(q for q in test if q["template"] == "erp_dept_revenue")
    c = next(c for c in world.clients if len({c["base"], c["legal"], c["erp_name"]}) == 3 and c["erp_name"].isupper() and c["cid"] in world.customers)
    fills = {
        "{{QUESTION_COUNT}}": f"{len(test):,}",
        "{{TIER_TABLE}}": "\n".join(tier_rows),
        "{{QUESTION_TABLE}}": "\n".join(q_rows),
        "{{LOG_TABLE}}": "\n".join(log_rows),
        "{{COVERAGE_TABLE}}": "\n".join(cov_rows),
        "{{STATS}}": "\n".join(stat_rows),
        "{{EXAMPLE}}": json.dumps(example, indent=2),
        "{{NAME_EXAMPLE}}": f'"{c["base"]}", "{c["legal"]}" and "{c["erp_name"]}"',
        "{{ZIPF}}": str(usages[tiers[0]]["zipf_exponent"]),
    }
    for name in ("README.md", "DATASHEET.md", "MATCHING.md", "LICENSE"):
        text = (docs / name).read_text()
        for k, v in fills.items():
            text = text.replace(k, v)
        (out / name).write_text(text)


if __name__ == "__main__":
    main()
