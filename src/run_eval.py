"""Run Setup A (Claude decides) and/or Setup B (rules decide, Claude explains).

One API call per scenario per run. Raw outputs go to results/raw/ (git-ignored).

  python src/run_eval.py --dry-run                 # no API calls; prints prompts and rule output
  python src/run_eval.py --setup A --model sonnet --runs 3
  python src/run_eval.py --setup both --model haiku --runs 3
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from prompts import SCHEMA_A, SCHEMA_B, SYSTEM_A, SYSTEM_B, user_a, user_b  # noqa: E402
from rules import diagnose  # noqa: E402

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# USD per million tokens (input, output), Claude API list prices as of Nov 2026
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}
# Setup A gets the model's best effort; Setup B only writes text, so low is enough
EFFORT = {"A": "high", "B": "low"}
RAW = ROOT / "results" / "raw"


def load_scenarios():
    return json.loads((ROOT / "data" / "scenarios.json").read_text())


def request(setup, model_id, sc):
    if setup == "A":
        system, schema, user = SYSTEM_A, SCHEMA_A, user_a(sc)
    else:
        system, schema, user = SYSTEM_B, SCHEMA_B, user_b(sc, diagnose(sc["measurements"]))
    return dict(
        model=model_id,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": EFFORT[setup], "format": {"type": "json_schema", "schema": schema}},
    )


def call(client, setup, model_id, sc, run):
    t0 = time.time()
    resp = client.messages.create(**request(setup, model_id, sc))
    text = "".join(b.text for b in resp.content if b.type == "text")
    parsed = None
    if resp.stop_reason == "end_turn":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            pass
    pin, pout = PRICES[model_id]
    u = resp.usage
    return {
        "id": sc["id"], "setup": setup, "model": model_id, "run": run,
        "stop_reason": resp.stop_reason, "output": parsed, "raw_text": None if parsed else text,
        "rule": diagnose(sc["measurements"]) if setup == "B" else None,
        "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
        "cost_usd": round(u.input_tokens * pin / 1e6 + u.output_tokens * pout / 1e6, 6),
        "seconds": round(time.time() - t0, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", choices=["A", "B", "both"], default="both")
    ap.add_argument("--model", choices=list(MODELS), default="sonnet")
    ap.add_argument("--runs", type=int, default=3, help="repeats for Setup A")
    ap.add_argument("--b-runs", type=int, default=1,
                    help="repeats for Setup B (its verdict comes from the rules, so 1 is enough)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N scenarios")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    scenarios = load_scenarios()[: args.limit]
    setups = ["A", "B"] if args.setup == "both" else [args.setup]
    model_id = MODELS[args.model]

    if args.dry_run:
        sc = scenarios[0]
        for s in setups:
            r = request(s, model_id, sc)
            print(f"=== Setup {s} / {model_id} / {sc['id']} ===\nSYSTEM:\n{r['system']}\n\nUSER:\n{r['messages'][0]['content']}\n")
        for sc in scenarios:
            d = diagnose(sc["measurements"])
            print(f"{sc['id']}: rules -> {d['verdict']} ({d['confidence']})")
        n = len(scenarios) * sum(args.runs if s == "A" else args.b_runs for s in setups)
        print(f"\nWould make {n} calls to {model_id}.")
        return

    import anthropic
    client = anthropic.Anthropic(max_retries=4)
    RAW.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for s in setups:
        for run in range(1, (args.runs if s == "A" else args.b_runs) + 1):
            out = RAW / f"{s}_{args.model}_run{run}.jsonl"
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda sc: call(client, s, model_id, sc, run), scenarios))
            out.write_text("".join(json.dumps(r) + "\n" for r in rows))
            cost = sum(r["cost_usd"] for r in rows)
            total += cost
            bad = sum(r["output"] is None for r in rows)
            print(f"Setup {s} {args.model} run {run}: {len(rows)} calls, ${cost:.4f}, {bad} unparsed -> {out.name}")
    print(f"Total ${total:.4f}")


if __name__ == "__main__":
    main()
