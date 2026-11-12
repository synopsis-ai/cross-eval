# CROSS: Cross-system Reasoning Over Scattered Sources

CROSS is a fully synthetic dataset for testing whether an AI analyst answers business questions correctly when the data lives in several separate systems. It contains the raw tables a mid-market company's CRM, ERP, payroll, ad platforms and industry software would hand you, plus 405 questions with known answers.

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
- **Names differ between systems.** "Elmstead Assurance", "Elmstead Assurance, LLC" and "ELMSTEAD ASSURANCE LLC" are the same customer.
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

| Tier | Tables | Columns | Size on disk |
|---|---|---|---|
| 1 | 67 | 1,541 | 3.0 MB |
| 2 | 92 | 3,032 | 3.9 MB |
| 3 | 218 | 10,014 | 7.6 MB |
| 4 | 700 | 35,048 | 20.5 MB |

## Layout

```
data/tier-<n>/<system>/<table>.parquet   one Parquet file per table (zstd)
schema/tier-<n>.json                     every table, column, type and row count per tier
questions/questions.jsonl                one question per line
MATCHING.md                              how answers are scored
DATASHEET.md                             how the data was made, and its limits
```

Query it directly with DuckDB:

```sql
CREATE VIEW cuewright_shows AS SELECT * FROM 'data/tier-1/cuewright/cuewright_shows.parquet';
```

## Questions

| Split | single_table | single_system_join | cross_system | Total |
|---|---|---|---|---|
| test | 101 | 48 | 61 | 210 |
| log | 92 | 46 | 57 | 195 |

Each line of `questions/questions.jsonl` looks like this:

```json
{
  "template": "erp_dept_revenue",
  "param": "RIG:2026H1",
  "split": "test",
  "question": "How much rigging revenue did we invoice in the first half of 2026, in US dollars?",
  "answer": {
    "type": "money",
    "value": 414706.04,
    "currency": "USD",
    "tolerance": 0.01,
    "min_sig_figs": 2
  },
  "systems": [
    "netsuite"
  ],
  "cross_system": false,
  "stratum": "single_system_join",
  "difficulty": "hard",
  "reference_sql": "SELECT SUM(-l.foreignamount * t.exchangerate)\nFROM netsuite_transaction_line l\nJOIN netsuite_transaction t ON t.id = l.\"transaction\"\nJOIN netsuite_department d ON d.id = l.department\nWHERE t.type = 'CustInvc' AND t.voided = 'F' AND l.mainline = 'F' AND d.name = 'Rigging'\n  AND CAST(strptime(t.trandate, '%m/%d/%Y') AS DATE) BETWEEN DATE '2026-01-01' AND DATE '2026-06-30'",
  "reference_sql_dialect": "duckdb",
  "generator_version": "0.1.0",
  "id": "cross-0074"
}
```

- **`answer` is the gold answer, plus what's needed to match it fuzzily.** That includes tolerance and precision, every name an entity goes by, and `accepted` alternatives for legitimate readings of the question.
- **Gold answers come from the simulated business, not from SQL.** The `reference_sql` query shows the question can be answered from the tables, and it reproduces every gold answer on every tier. Scoring never uses it.
- **Splits:**
  - `test` is for measurement.
  - `log` is a separate set from the same templates. Use it as a query history for systems that learn from past questions, and never score on it.
- **Strata:**
  - `single_table`
  - `single_system_join`
  - `cross_system`: needs two or more systems.

## Scoring

Score the answer a person would read, not the SQL behind it. An answer that is right but worded or rounded differently counts as correct. [MATCHING.md](MATCHING.md) defines the rules.

## License

[CC BY 4.0](LICENSE). Use it for anything, including commercially, and credit "CROSS dataset by Synopsis (getsynopsis.ai)".
