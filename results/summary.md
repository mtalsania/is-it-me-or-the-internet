| Setup | Diagnoses | Right | Confidently wrong | Ambiguous cases right | Follow-up on ambiguous | Stable | Cost per 1,000 |
|---|---|---|---|---|---|---|---|
| Rules only (no model) | 50 | 80.0% | 7 (14.0%) | 57.1% | 57.1% | 50/50 | $0.0 |
| Setup A - haiku | 150 | 73.3% | 10 (6.7%) | 47.6% | 83.3% | 40/50 | $0.5 |
| Setup A - sonnet | 150 | 90.7% | 3 (2.0%) | 90.5% | 100.0% | 46/50 | $6.68 |
| Setup B - haiku | 50 | 80.0% | 7 (14.0%) | 57.1% | 57.1% | 50/50 | $0.24 |
| Setup B - sonnet | 50 | 80.0% | 7 (14.0%) | 57.1% | 57.1% | 50/50 | $4.82 |
| Setup C - sonnet | 150 | 91.3% | 3 (2.0%) | 90.5% | 100.0% | 46/50 | $6.74 |

Misses:
- Rules only (no model): A08 (healthy/high), A09 (healthy/high), A10 (healthy/high), M02 (bufferbloat/high), O01 (dns/medium), O04 (bufferbloat/high), O05 (local_or_isp/medium), U02 (healthy/high), U03 (healthy/high), U04 (local_or_isp/medium)
- Setup A - haiku: H03 (bufferbloat/medium), I03 (local_or_isp/medium), A01 (bufferbloat/medium), A02 (bufferbloat/medium), A04 (bufferbloat/medium), A06 (bufferbloat/high), A07 (bufferbloat/medium), A08 (bufferbloat/high), M02 (bufferbloat/medium), O01 (bufferbloat/medium), O04 (bufferbloat/high), U04 (healthy/medium), P01 (bufferbloat/medium), H03 (bufferbloat/high), I03 (local_or_isp/medium), A01 (bufferbloat/medium), A02 (bufferbloat/medium), A04 (bufferbloat/medium), A06 (bufferbloat/medium), A07 (bufferbloat/medium), A08 (bufferbloat/high), M02 (bufferbloat/medium), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium), P01 (bufferbloat/medium), H03 (bufferbloat/medium), I03 (bufferbloat/medium), A01 (bufferbloat/medium), A02 (bufferbloat/medium), A04 (bufferbloat/medium), A06 (bufferbloat/high), A07 (bufferbloat/medium), A08 (bufferbloat/high), A10 (bufferbloat/medium), M02 (bufferbloat/medium), O01 (healthy/high), O04 (bufferbloat/high), U04 (healthy/medium), P01 (bufferbloat/medium)
- Setup A - sonnet: I03 (local_or_isp/medium), A08 (healthy/low), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium), I03 (local_or_isp/medium), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium), I03 (local_or_isp/medium), C04 (local_or_isp/medium), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium)
- Setup B - haiku: A08 (healthy/high), A09 (healthy/high), A10 (healthy/high), M02 (bufferbloat/high), O01 (dns/medium), O04 (bufferbloat/high), O05 (local_or_isp/medium), U02 (healthy/high), U03 (healthy/high), U04 (local_or_isp/medium)
- Setup B - sonnet: A08 (healthy/high), A09 (healthy/high), A10 (healthy/high), M02 (bufferbloat/high), O01 (dns/medium), O04 (bufferbloat/high), O05 (local_or_isp/medium), U02 (healthy/high), U03 (healthy/high), U04 (local_or_isp/medium)
- Setup C - sonnet: I03 (local_or_isp/medium), A08 (healthy/low), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium), I03 (local_or_isp/medium), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium), I03 (local_or_isp/medium), O01 (healthy/high), O04 (bufferbloat/medium), U04 (healthy/medium)

Fact-check:
- Setup C - sonnet: flagged 1, changed 1, fixed ['C04'], broke []
