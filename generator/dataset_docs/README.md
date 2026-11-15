# CROSS: Cross-system Reasoning Over Scattered Sources

CROSS is a fully synthetic dataset for testing whether an AI analyst answers business questions correctly when the data lives in several separate systems. It contains the raw tables a mid-market company's CRM, ERP, payroll, ad platforms and industry software would hand you, plus {{QUESTION_COUNT}} questions with known answers.

It's made by [Synopsis](https://getsynopsis.ai). Everything in it is generated, and no real company, person or customer record is in it.

## The company

**Bloom Productions** is a fictional corporate event production company. It provides the AV, staging and crews for conferences, sales kickoffs, product launches, trade shows and galas.

- **Offices:** Chicago, Nashville, Denver and Toronto. Toronto bills in Canadian dollars.
- **Window:** two years of history, July 1, 2024 to **June 30, 2026**. "Today" is June 30, 2026.

It runs on six systems. Each one has its own copy of the business, with its own IDs, naming, data types and gaps:

| System | Table prefix | What it holds | Modeled on |
|---|---|---|---|
| CRM | `salesforce_` | Accounts, contacts, leads, deals, campaigns, activities | Salesforce |
| ERP | `netsuite_` | Customers, vendors, invoices, deposits, payments, bills, GL lines | NetSuite |
| Payroll | `adp_` | Workers, pay rates, pay statements, earnings | ADP Workforce Now |
| Ads | `google_ads_`, `meta_ads_` | Campaigns and daily performance | Google Ads, Meta |
| Production system | `cuewright_` | Shows, quotes, change orders, crew shifts, gear, repairs | **Cuewright**, a fictional system invented for this dataset |

Table and column names are shaped the way a typical data pipeline lands each vendor's API. Salesforce, NetSuite, ADP, Google Ads and Meta are trademarks of their owners. This dataset isn't affiliated with any of them, and none of its data came from their products.

## Why it's hard

Answering takes the same work real company data takes:

- **Joining across systems.**
  - A show in Cuewright points at its CRM deal by an ID that's sometimes 15 characters and sometimes 18.
  - Invoices name the show in a custom field or only in the memo.
  - Crew are `E-412` in Cuewright and `000412` in payroll.
- **Names differ between systems.** {{NAME_EXAMPLE}} are the same customer.
- **Values that need handling:**
  - Dates stored as text in three formats.
  - Money as text ("$1,250.00", "-$500.00").
  - Meta's numbers as strings, and its results inside JSON.
  - NetSuite's sign conventions and summary lines.
  - Amounts in two currencies.
- **Records to exclude:**
  - Soft-deleted CRM rows.
  - Voided invoices.
  - Superseded quote versions.
  - Voided change orders.
  - Duplicate accounts and client records.
  - Two Meta lead counts that double-count each other.
- **Systems that disagree.** CRM deal amounts differ from final invoices, and ad platforms report more leads than the CRM received. Each question says which system it means, or asks about the difference.
- **Width.** Real company schemas are mostly columns and tables nobody queries. Each tier pads the core tables the way real accounts are padded: sparse custom fields and rarely-used tables.

## Tiers

The same business, and the same questions, at four schema sizes. Each tier is self-contained.

{{TIER_TABLE}}

## Layout

```
data/tier-<n>/<system>/<table>.parquet   one Parquet file per table (zstd)
schema/tier-<n>.json                     every table, column, type and row count per tier
questions/test.jsonl                     the test questions, one per line (the same for every tier)
questions/log-tier-<n>.jsonl             the tier's query log: past questions, never scored
usage/tier-<n>.json                      the tier's table-usage ranking and seeding coverage
MATCHING.md                              how answers are scored
DATASHEET.md                             how the data was made, and its limits
generator/                               the code that builds all of the above
```

Query it directly with DuckDB:

```sql
CREATE VIEW cuewright_shows AS SELECT * FROM 'data/tier-1/cuewright/cuewright_shows.parquet';
```

## Questions

{{QUESTION_TABLE}}

Each line of `questions/test.jsonl` looks like this:

```json
{{EXAMPLE}}
```

- **`answer` is the gold answer, plus what's needed to match it fuzzily.** That includes tolerance and precision, every name an entity goes by, and `accepted` alternatives for legitimate readings of the question.
- **Gold answers come from the simulated business, not from SQL.** The `reference_sql` query shows the question can be answered from the tables, and it reproduces every gold answer on every tier. Scoring never uses it.
- **Test and log:**
  - `questions/test.jsonl` is for measurement.
  - `questions/log-tier-<n>.jsonl` is the tier's query history: a month of earlier questions. Use it for systems that learn from past questions, and never score on it.
- **Strata:**
  - `single_table`
  - `single_system_join`
  - `cross_system`: needs two or more systems.

## Query log and seeding

Some systems give the AI a "seed" up front: the schemas of the tables the company queries most. The rest it has to look up. Each tier ships what you need to test how many tables to seed.

**The log.** Each tier has a realistic query log. Usage falls off steeply (Zipf, exponent {{ZIPF}}): a few tables are queried constantly, and most are queried once or never.

- The core business tables get the same usage in every tier, because it's the same company and the same people asking.
- Bigger tiers add more rarely-used padding tables to the log, so those compete for seed slots.
- A few core tables never appear in the log, and some test questions need them. A seed built from history can't contain them.

{{LOG_TABLE}}

**The ranking.** `usage/tier-<n>.json` ranks every table the log touches by how many log questions use it. To seed the top P% of a tier, take the first `ceil(P% × tables in the tier)` entries of `ranking`, then build their schema text from `schema/tier-<n>.json`. If P% asks for more tables than the log touches, the seed is every ranked table.

Systems that learn usage from their own history can replay the log instead. The ranking is what that replay should produce, give or take the tables an AI explores along the way.

**Coverage.** A test question is covered when every table it needs is in the seed. `test_question_rank_needed` gives, for each test question, the rank a seed must reach to cover it, or `null` if the log never touches one of its tables. The share of test questions covered at each seed size:

{{COVERAGE_TABLE}}

Coverage shows how much of the schema the seed hands over, not accuracy. To measure accuracy at a given seed size, run the test questions with that seed and score the answers.

## Scoring

Score the answer a person would read, not the SQL behind it. An answer that is right but worded or rounded differently counts as correct. [MATCHING.md](MATCHING.md) defines the rules.

## License

The data and questions are [CC BY 4.0](LICENSE): use them for anything, including commercially, and credit "CROSS dataset by Synopsis (getsynopsis.ai)". The generator code in `generator/` is [Apache-2.0](generator/LICENSE).
