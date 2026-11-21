| Setup | Diagnoses | Right | Confidently wrong | Ambiguous cases right | Follow-up on ambiguous | Stable | Cost per 1,000 |
|---|---|---|---|---|---|---|---|
| Rules only (no model) | 20 | 80.0% | 2 (10.0%) | 66.7% | 66.7% | 20/20 | $0.0 |
| Setup A - sonnet | 60 | 95.0% | 0 (0.0%) | 100.0% | 100.0% | 18/20 | $6.74 |
| Setup C - sonnet | 60 | 95.0% | 0 (0.0%) | 100.0% | 100.0% | 17/20 | $8.13 |

Misses:
- Rules only (no model): K01 (healthy/high), K04 (bufferbloat/medium), K07 (local_or_isp/medium), K16 (healthy/high)
- Setup A - sonnet: K04 (healthy/low), K04 (healthy/low), K04 (healthy/low)
- Setup C - sonnet: K04 (healthy/low), K04 (healthy/low), K04 (local_or_isp/low)

Fact-check:
- Setup C - sonnet: flagged 9, changed 1, fixed [], broke []
