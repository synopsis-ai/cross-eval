# CROSS generator

Builds the CROSS dataset in this repo: a fictional event production company across Salesforce-, NetSuite-, ADP-, Google Ads- and Meta-shaped systems plus the fictional Cuewright production system. The code is licensed under [Apache-2.0](LICENSE); the generated data under CC BY 4.0.

```sh
uv sync
uv run python -m cross_eval.build --out ..   # rebuilds data/, schema/, questions/ and the docs at the repo root
uv run python -m unittest tests.test_match                          # answer matcher
```

The build fails if any question's reference SQL doesn't reproduce its gold answer on the smallest and largest tier. Output is byte-identical for a given seed and lockfile.

- `world.py` simulates the business; it is the source of truth for gold answers.
- `render.py` renders each system's tables from it, with that system's IDs, naming, types and mess.
- `width.py` pads tiers to ~1.5k / 3k / 10k / 35k columns; lower tiers are prefixes of higher ones.
- `questions.py` holds the question templates (gold from the simulation, reference SQL from the tables).
- `match.py` is the fuzzy answer matcher described in `dataset_docs/MATCHING.md`.
- `dataset_docs/` holds the published README, datasheet, matching spec and license.
