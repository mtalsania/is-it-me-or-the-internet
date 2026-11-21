"""Run the setups. Raw outputs go to results/raw/ (git-ignored).

  A: Claude decides alone (one call per case)
  B: rules decide, Claude only explains (one call per case)
  C: Claude decides, then src/factcheck.py checks hard facts; only if a fact contradicts the
     verdict does Claude get one more call to re-examine (it may keep its answer)

  python src/run_eval.py --dry-run
  python src/run_eval.py --setup both --model sonnet --runs 3
  python src/run_eval.py --setup C --model sonnet --runs 3 --reuse-a      # reuse saved Setup A answers
  python src/run_eval.py --data heldout --setup C --model sonnet --runs 3
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from factcheck import check  # noqa: E402
from prompts import SCHEMA_A, SCHEMA_B, SYSTEM_A, SYSTEM_B, revise_c, user_a, user_b  # noqa: E402
from rules import diagnose  # noqa: E402

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# USD per million tokens (input, output), Claude API list prices as of Nov 2026
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}
# Setup A gets the model's best effort; Setup B only writes text, so low is enough
EFFORT = {"A": "high", "B": "low"}
RAW = ROOT / "results" / "raw"


def load_dotenv():
    """Read ANTHROPIC_API_KEY from a git-ignored .env in the repo root, if present.
    Kept out of the shell profile so Claude Code itself doesn't pick up the key."""
    import os
    f = ROOT / ".env"
    if f.exists() and not os.environ.get("ANTHROPIC_API_KEY"):
        for line in f.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"')


def load_scenarios(data="scenarios"):
    return json.loads((ROOT / "data" / f"{data}.json").read_text())


def raw_dir(data):
    return RAW if data == "scenarios" else RAW / data


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


def call(client, setup, model_id, sc, run, req=None):
    t0 = time.time()
    resp = client.messages.create(**(req or request(setup, model_id, sc)))
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


def call_c(client, model_id, sc, run, first=None):
    """Setup C for one case: decide (or reuse a saved Setup A answer), fact-check, maybe revise."""
    if first is None:
        first = call(client, "A", model_id, sc, run)
    out = first["output"]
    flags = check(sc, out["verdict"]) if out else []
    final, rev_cost = out, 0.0
    if flags:
        req = request("A", model_id, sc)
        req["messages"] += [{"role": "assistant", "content": json.dumps(out)},
                            {"role": "user", "content": revise_c(flags)}]
        rev = call(client, "A", model_id, sc, run, req)
        final, rev_cost = rev["output"] or out, rev["cost_usd"]
    return {"id": sc["id"], "setup": "C", "model": model_id, "run": run,
            "first": out, "flags": flags, "output": final,
            "first_cost_usd": first["cost_usd"], "revision_cost_usd": rev_cost,
            "cost_usd": round(first["cost_usd"] + rev_cost, 6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", choices=["A", "B", "C", "both"], default="both")
    ap.add_argument("--data", choices=["scenarios", "heldout"], default="scenarios")
    ap.add_argument("--reuse-a", action="store_true",
                    help="Setup C: reuse saved Setup A answers instead of asking again")
    ap.add_argument("--model", choices=list(MODELS), default="sonnet")
    ap.add_argument("--runs", type=int, default=3, help="repeats for Setup A")
    ap.add_argument("--b-runs", type=int, default=1,
                    help="repeats for Setup B (its verdict comes from the rules, so 1 is enough)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N scenarios")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    scenarios = load_scenarios(args.data)[: args.limit]
    setups = ["A", "B"] if args.setup == "both" else [args.setup]
    model_id = MODELS[args.model]

    if args.dry_run:
        sc = scenarios[0]
        for s in setups:
            r = request("A" if s == "C" else s, model_id, sc)
            print(f"=== Setup {s} / {model_id} / {sc['id']} ===\nSYSTEM:\n{r['system']}\n\nUSER:\n{r['messages'][0]['content']}\n")
        for sc in scenarios:
            d = diagnose(sc["measurements"])
            print(f"{sc['id']}: rules -> {d['verdict']} ({d['confidence']})")
        n = len(scenarios) * sum(args.b_runs if s == "B" else args.runs for s in setups)
        print(f"\nWould make {n} calls to {model_id}.")
        return

    load_dotenv()
    import anthropic
    client = anthropic.Anthropic(max_retries=4)
    raw = raw_dir(args.data)
    raw.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for s in setups:
        for run in range(1, (args.b_runs if s == "B" else args.runs) + 1):
            out = raw / f"{s}_{args.model}_run{run}.jsonl"
            if s == "C":
                saved = {}
                fa = raw / f"A_{args.model}_run{run}.jsonl"
                if args.reuse_a and fa.exists():
                    saved = {r["id"]: r for r in map(json.loads, fa.read_text().splitlines())}
                with ThreadPoolExecutor(max_workers=4) as pool:
                    rows = list(pool.map(lambda sc: call_c(client, model_id, sc, run, saved.get(sc["id"])), scenarios))
                if saved:  # the decide step was already paid for in Setup A
                    for r in rows:
                        r["cost_usd"] = r["revision_cost_usd"]
                flagged = sum(bool(r["flags"]) for r in rows)
                print(f"  fact-check flagged {flagged} of {len(rows)}")
            else:
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
