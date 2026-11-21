# Is it me or the internet?

**Assumption tested:** "Don't let an LLM diagnose. Let deterministic rules decide, and use the LLM only to explain."

**Result:** on 50 home-internet cases, the rules were **confidently wrong 7 times more often** than Claude Sonnet working alone (14% vs 2%). That flips the assumption, but only for a capable model: the small model (Haiku) alone was less accurate than the rules.

Total API cost of the experiment: **$1.33**.

## The problem

When the internet feels slow, people can't tell whether the cause is their Wi-Fi, their device, their provider, or one website. Speed tests give numbers, not answers. The question is whether an LLM can turn those numbers into a correct, honestly hedged diagnosis, or whether the safer design is rules that decide plus an LLM that only explains.

## What was built

- **50 cases** (`data/build_scenarios.py`). Each one has what a person says, numbers a browser can measure (speed, idle and loaded latency, jitter, loss, DNS time, timings to four sites) and a Cloudflare Radar-style outage flag for the provider. Each case has a locked answer: the accepted verdicts and the confidence levels that count as right.
- **8 verdicts:** healthy, local network, provider problem, "local or provider (can't tell)", bufferbloat, DNS, one service slow, one service down.
- **Rules** (`src/rules.py`): thresholds taken from common guidance (jitter over 20 ms, loss of 1% or more, latency rising 80 to 150 ms under load, DNS over 300 ms). They were frozen before any model call and never tuned.
- **Setup A:** Claude gets the complaint and the numbers and returns a verdict, confidence, explanation, one fix and a follow-up test when unsure. It uses a fixed JSON format, one call per case.
- **Setup B:** the rules decide the verdict and confidence, and Claude only writes the explanation, fix and follow-up test.
- **Models:** Claude Sonnet 5.5 and Claude Haiku 5.5. Setup A ran 3 times per model; Setup B ran once, because its verdict comes from the rules.

Order of work, visible in the git history: answers committed first, then rules, then model runs.

## What "healthy" looks like

These are the reference numbers behind every case. The healthy baseline is a typical US cable line. The "bad" lines are the thresholds the rules use, taken from common guidance and never tuned to the cases.

| Measure | What it means | Healthy baseline | Starts to hurt | Clearly bad |
|---|---|---|---|---|
| Download speed | How fast things arrive | 305 Mbps | under 100 for a busy home | under 25 Mbps (the FCC broadband floor) |
| Upload speed | How fast you send (calls, backups) | 21 Mbps | under 10 for video calls | under 3 Mbps |
| Idle ping | Round-trip time when nothing else is running | 14 ms | 40+ ms | 80+ ms |
| Jitter | How much the ping wobbles | 2 ms | 10+ ms | 20+ ms (calls and games stutter) |
| Packet loss | Share of data that never arrives | 0% | 0.5% | 1% or more |
| Ping under load | Ping while the line is busy downloading or uploading | 36 / 44 ms (+22 to +30 over idle) | +80 ms over idle (mild bufferbloat) | +150 ms over idle (severe bufferbloat) |
| DNS lookup | Time to turn a site name into an address | 19 ms | 100+ ms | 300+ ms (every new site feels slow) |
| One service vs. the rest | Ping to Netflix or Zoom compared with the Cloudflare edge | within 30 ms of the edge | — | 150+ ms slower while the others are fine |

Two notes. First, speed is the least useful number: a 50 Mbps line with clean ping beats a 500 Mbps line with 300 ms of bufferbloat for calls and games. Second, some connections are normal outside these ranges. Satellite and 5G home internet always carry more ping and jitter, and that alone doesn't mean they're broken. The "starts to hurt" column is a rule of thumb for people reading the cases. The rules only use the "clearly bad" column.

## The data and its problems

- **48 synthetic cases, all written by one author.** Only the first 30 had answers locked before the rules existed. The other 18 synthetic cases and the 2 real ones were added after the rules were frozen, by someone who knew where the rules were weak. That is a source of bias against the rules, so it gets its own check below.
- **2 real cases** from Mihir's own connection (M01, M02). A laptop stuck on 2.4 GHz Wi-Fi showed 741 ms of latency under load while a phone at the same desk showed 26 ms.
- **14 of 50 cases are deliberately ambiguous.** Browser data can't separate the causes, so the right answer is medium or low confidence plus a follow-up test. A "high confidence" answer there counts as confidently wrong.
- **The "bad Wi-Fi" template has a built-in latency rise under load of 70 to 85 ms.** That is in mild bufferbloat territory, and it probably explains part of Haiku's habit of answering "bufferbloat".
- **The answer key has debatable labels.** Examples: satellite internet (O01) is labeled "provider problem", where "normal for satellite" is defensible; wired-still-bad (I03) is labeled "provider, high confidence", where "could be the modem" is defensible.
- **The models see the complaint text and the rules don't.** This is deliberate, because real users describe their problem, but it is part of why the models win.

## Results

| Setup | Diagnoses | Right | Confidently wrong | Ambiguous cases right | Same answer on all 3 runs | Cost per 1,000 |
|---|---|---|---|---|---|---|
| Rules decide (B, any model) | 50 | 80.0% | 7 (14.0%) | 57.1% | 50/50 | $0.24 (Haiku explains) / $4.82 (Sonnet explains) |
| Sonnet alone (A) | 150 | 90.7% | 3 (2.0%) | 90.5% | 46/50 | $6.68 |
| Haiku alone (A) | 150 | 73.3% | 10 (6.7%) | 47.6% | 40/50 | $0.50 |

Checks on the headline:

- **First 30 cases only** (answers locked before the rules existed): Sonnet got 86 of 90 right with **0 confidently wrong**. The rules got 27 of 30 right with 3 confidently wrong. The result does not depend on the later cases.
- **Where Sonnet and the rules disagree** (24 of 150): Sonnet was right 14 times, the rules 7 times.
- **Sonnet gave a follow-up test on 100% of ambiguous cases.** The rules did so on 57%.

## How each setup fails

- **Rules:** they can't read the complaint. "It drops every few hours" plus a healthy snapshot gets "healthy, high confidence" (A09, A10, U03). They also miss patterns their author didn't write a rule for: a hotel login page (O05), two services failing together (U02), and the laptop-specific case (M02), where they say "bufferbloat", which would send the person to fix the router.
- **Sonnet:** all 3 confident misses are the satellite case, where its answer is arguably right. Its other misses are mostly label disagreements. In the cellular case (U04) it *noticed* the test ran on T-Mobile instead of the user's Verizon line, but it filed that under "healthy".
- **Haiku:** it answered "bufferbloat" 57 times out of 150, against about a dozen true bufferbloat cases, and it is less consistent across runs (40 of 50 stable).

## What I'd do in production

Not tested here; this is the design the results point to:

1. **Use a capable model to decide, not a small one.** At $6.68 per 1,000 diagnoses, the cost is small next to one support call.
2. **Keep rules as a fact-checker, not the decider.** Hard facts include a Radar outage, the provider differing from what the user expects, every site failing, and a retest result. When the model and a hard fact disagree, lower the confidence and ask for the follow-up test.
3. **Always show which network was tested.** One of the real tests silently measured cellular instead of home Wi-Fi.
4. **Grade the explanations too.** This eval graded only the verdict and confidence.

## Limits

- 50 cases, mostly synthetic and written by one author. The two real cases come from one home.
- 3 runs per model, which is enough to see stability but not to separate small differences.
- Radar is simulated as a single yes/no flag. The live version would query Cloudflare Radar.
- Explanation quality (Setup B's actual job) was not scored.
- Results are for Sonnet 5.5 and Haiku 5.5 with this prompt. Other models or prompts may differ.

## Reproduce

See [README.md](README.md). Running `python src/grade.py` on the raw results regenerates every number in this file.
