# Is it me or the internet?

An eval of one assumption: **"Let the LLM diagnose your slow internet."**

50 synthetic home-internet problems, each made only of numbers a browser can measure
(the kind speed.cloudflare.com shows) plus a Cloudflare Radar outage flag. Each has a
locked answer. Two setups are compared:

- **Setup A:** Claude reads the raw numbers and decides the cause and its confidence.
- **Setup B:** plain rules in code decide the cause and confidence; Claude only explains it
  in plain English, gives one fix, and suggests a follow-up test when the rules aren't sure.

See [WRITEUP.md](WRITEUP.md) for results.

## Run it

```bash
pip install -r requirements.txt
python data/build_scenarios.py          # regenerate data/scenarios.json
python -m pytest -q                     # rule and fact-check tests, no API calls
python src/run_eval.py --dry-run        # show prompts and rule verdicts, no API calls
# put ANTHROPIC_API_KEY=... in a .env file here (git-ignored); run_eval.py reads it
python src/run_eval.py --setup both --model sonnet --runs 3
python src/run_eval.py --setup both --model haiku --runs 3
python src/grade.py                     # writes results/summary.md
```

The full run is 400 calls (50 scenarios: Setup A x3 and Setup B x1, on Sonnet and Haiku) and should cost about $2 to $4.

## Order of work (check the git history)

1. Scenarios and ground truth committed first.
2. Rules written and frozen next, without changing the scenarios.
3. Only then any model call.

## Setup C: Claude decides, rules fact-check

```bash
python src/run_eval.py --setup C --model sonnet --runs 3 --reuse-a        # original 50, reuses saved Setup A answers
python src/run_eval.py --data heldout --setup C --model sonnet --runs 3   # 20 new held-out cases
python src/grade.py && python src/grade.py --data heldout
```
