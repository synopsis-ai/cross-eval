# Scoring answers

CROSS scores the answer a person would read, not the query behind it. An answer that's right but worded or rounded differently counts as correct. An answer built from several separate queries, combined in the text, counts the same as one built from a single query.

Scoring has two steps.

## 1. Extract

Something reads the final reply and writes down what it claims. That can be a person or an LLM; an LLM works well.

- **Put each claimed value in the question's answer type.** "About $1.2M" becomes `1200000`, and "23%" becomes `0.23`.
- **Record the precision the reply used,** in significant figures. "$1.2M" has 2; "$1,234,567.89" has 9.
- **Record every final value the reply gives.** If it hedges between two numbers, record both.
- **Mark the reply as clarifying** if it asks a question instead of answering.

The extractor must never see the gold answer. It transcribes; it doesn't judge.

A claim looks like this:

```json
{"values": [1200000], "sig_figs": 2, "clarifying": false}
```

## 2. Match

Compare the claim to the question's `answer` with these rules. A question's own `answer` fields override the defaults.

| Answer type | Correct when |
|---|---|
| `money`, `number` | The claim is within `tolerance` of the gold value (default 1%). It also counts if it equals the gold value rounded to the claim's own precision and that precision is at least `min_sig_figs` (default 2). So "$1.2M" matches 1,234,567, but "$1M" doesn't match 1,450,000. |
| `count` | Exactly equal, unless the question sets a `tolerance`. |
| `percent` | 0.234, 23.4% and "23%" are the same value; then the number rules apply. |
| `date` | Same date at the question's `granularity` (day, month or year), in any format. |
| `entity` | After lowercasing and dropping punctuation and legal suffixes (Inc, LLC, Corp, Co, Ltd, Group, Holdings), the claim equals or closely resembles the gold value or any of its `aliases` (string similarity at least 0.88). |
| `entity_list` | Every gold item is matched by some claimed item, and the reply adds no extra items. |
| `ranked_list` | Same items in the same order. |
| `yes_no` | The reply's stated conclusion. |

More rules:

- **Alternative readings.** A claim matching any value in `accepted` is also correct. Report which reading it matched.
- **Conflicting values.** If the reply gives more than one final value, it's correct only if every one of them matches.
- **Clarifying questions.** A reply that only asks a question is wrong. Count these separately, and report the clarification rate alongside accuracy. When re-asking after a clarification, reply once with "Use your best judgment and answer."
- **Partial credit.** Report it separately if you want it; the headline number is right or wrong.

Freeze your extractor and these rules before your first scored run. If you use an LLM extractor, hand-label a sample of replies and report how often the extractor agrees with you.
