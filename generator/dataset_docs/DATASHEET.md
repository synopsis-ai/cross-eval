# Datasheet

## Motivation

AI analysts are increasingly asked business questions over a company's own systems. Existing text-to-SQL benchmarks mostly use clean, academic schemas, one database at a time, and score the SQL. CROSS tests the setting businesses actually have:

- several systems that each hold part of the truth;
- raw, wide and messy tables;
- answers judged on whether they're right.

## Composition

- **One fictional company,** Bloom Productions, over two years (July 1, 2024 to June 30, 2026).
- **Six systems:** a CRM, an ERP, payroll, two ad platforms, and a fictional production-management system called Cuewright.
- **Four tiers** of the same data at increasing schema width. A lower tier's tables and columns are a subset of every higher tier's, and the core rows are identical in all four.
- **Questions:** single-system and cross-system, with gold answers, matching rules and a reference query each. They're split into `test` and `log`.

{{STATS}}

## How it was made

- **The business is simulated first.**
  - A seeded, deterministic generator simulates clients, deals, shows, crews, gear, invoices, payments, bills, payroll and advertising.
  - Each system then renders its own view of that history.
  - Errors and inconsistencies are added during rendering, so the true answer stays defined even where the data is messy.
- **Gold answers come from the simulation.** They aren't computed from the rendered tables.
- **Every question is checked.** Its reference query is run on every tier and must reproduce the gold answer, which shows the answer is recoverable from the data. Questions that fail are dropped.
- **Schema shapes** follow the vendors' public API documentation and common connector conventions. Cuewright's schema was designed from the business process and isn't modeled on any real product.
- **Fully synthetic.** No real person, company or customer record was used. Names are drawn from generic first- and last-name lists and invented company stems; any resemblance to a real organization is coincidental. Every email address and website uses the reserved `.example` domain, so none can belong to a real person or company.

The generator is in [`generator/`](generator/). Rebuilding with the same seed and lockfile reproduces a release byte for byte, and its `generator_version` is recorded on every question.

## Deliberate messiness

| Kind | Examples |
|---|---|
| Text types | Cuewright dates as `MM/DD/YYYY`, NetSuite dates as `M/D/YYYY`; money as `"$1,250.00"`; Meta spend and counts as strings |
| Nested data | Meta `actions` JSON, Cuewright `custom_fields` and venue `details` JSON, ADP addresses |
| Records to exclude | Soft-deleted Salesforce rows, voided invoices, superseded quote versions, voided change orders |
| Duplicates | A few duplicate CRM accounts and duplicate Cuewright client records |
| Partial links | Customer-to-CRM IDs filled for some records only; Salesforce IDs in 15- and 18-character forms; show numbers in a custom field or only in a memo |
| Disagreeing systems | CRM deal amount vs final invoice; ad-platform leads vs CRM leads; ad conversions vs CRM leads |
| Accounting conventions | NetSuite summary lines (`mainline = 'T'`) beside detail lines, and revenue lines stored as negative amounts |
| Currency | Toronto shows invoiced in CAD, with the transaction's exchange rate to USD |
| Width | Sparse custom fields on core objects, plus many rarely-queried tables, increasing by tier |

## Known limits

- One company in one industry. Industries with very different data, such as healthcare or manufacturing, aren't represented.
- Tables are flat files. There's no change history beyond what a few tables carry, and no deletes beyond soft-delete flags.
- The vertical system is fictional, so results on it say nothing about any real product's schema.
- Questions are single-turn and use explicit dates. "Last quarter" style questions would need the data shifted to the date of each run.
- `reference_sql` is written for DuckDB. Other engines may need small dialect changes, mostly in date parsing and JSON functions.

## Maintenance

Versions are tagged in the repository. A new version may change rows, questions or both, so compare scores only within one `generator_version`.
