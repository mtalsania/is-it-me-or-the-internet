"""Grade every raw run against the locked ground truth. Writes results/summary.json and
results/summary.md, and prints the table.

Definitions (per diagnosis):
  right verdict   verdict is in the scenario's accepted list
  right overall   right verdict AND confidence is one the truth allows
  confidently wrong   confidence "high" AND (wrong verdict OR the case is ambiguous)
  follow-up given (ambiguous cases)   a non-empty follow_up_test
  stable          for a scenario, all runs gave the same verdict and confidence
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from rules import diagnose  # noqa: E402

RAW = ROOT / "results" / "raw"


def _fix_ok(r, t):
    """A case like 'sign in to the Wi-Fi' has no exact verdict; any verdict whose fix says so counts."""
    words = t.get("fix_mentions")
    text = ((r.get("fix") or "") + " " + (r.get("explanation") or "")).lower()
    return bool(words) and any(w in text for w in words)


def score(rows, truth):
    n = len(rows)
    amb_rows = [r for r in rows if truth[r["id"]]["ambiguous"]]
    right_v = right_all = conf_wrong = parse_fail = 0
    follow = 0
    misses = []
    for r in rows:
        t = truth[r["id"]]
        v, c, f = r["verdict"], r["confidence"], r.get("follow_up_test")
        if v is None:
            parse_fail += 1
            misses.append((r["id"], "no answer"))
            continue
        ok_v = v in t["accept"] or _fix_ok(r, t)
        right_v += ok_v
        ok_all = ok_v and c in t["confidence"]
        right_all += ok_all
        if c == "high" and (not ok_v or t["ambiguous"]):
            conf_wrong += 1
        if t["ambiguous"] and f:
            follow += 1
        if not ok_all:
            misses.append((r["id"], f"{v}/{c}"))
    by_sc = defaultdict(set)
    for r in rows:
        by_sc[r["id"]].add((r["verdict"], r["confidence"]))
    stable = sum(len(s) == 1 for s in by_sc.values())
    return {
        "diagnoses": n,
        "right_overall_pct": round(100 * right_all / n, 1),
        "right_verdict_pct": round(100 * right_v / n, 1),
        "confidently_wrong": conf_wrong,
        "confidently_wrong_pct": round(100 * conf_wrong / n, 1),
        "ambiguous_right_pct": round(100 * sum(
            1 for r in amb_rows if r["verdict"] in truth[r["id"]]["accept"]
            and r["confidence"] in truth[r["id"]]["confidence"]) / max(1, len(amb_rows)), 1),
        "ambiguous_follow_up_pct": round(100 * follow / max(1, len(amb_rows)), 1),
        "stable_scenarios": f"{stable}/{len(by_sc)}",
        "unparsed": parse_fail,
        "misses": misses,
    }


def row_from(r, setup, which="output"):
    o = r.get(which) or {}
    if setup == "B":  # verdict and confidence come from the rules; the model only wrote text
        return {"id": r["id"], "verdict": r["rule"]["verdict"] if r["output"] else None,
                "confidence": r["rule"]["confidence"], "follow_up_test": o.get("follow_up_test")}
    return {"id": r["id"], "verdict": o.get("verdict"), "confidence": o.get("confidence"),
            "follow_up_test": o.get("follow_up_test"), "fix": o.get("fix"),
            "explanation": o.get("explanation")}


def factcheck_stats(rows_c, truth):
    """How often the fact-checker fired, and whether the revision fixed or broke an answer."""
    def right(i, o):
        return o and o["verdict"] in truth[i]["accept"] and o["confidence"] in truth[i]["confidence"]
    flagged = [r for r in rows_c if r["flags"]]
    changed = [r for r in flagged if (r["first"]["verdict"], r["first"]["confidence"])
               != (r["output"]["verdict"], r["output"]["confidence"])]
    fixed = [r["id"] for r in flagged if not right(r["id"], r["first"]) and right(r["id"], r["output"])]
    broke = [r["id"] for r in flagged if right(r["id"], r["first"]) and not right(r["id"], r["output"])]
    return {"flagged": len(flagged), "changed": len(changed), "fixed": fixed, "broke": broke,
            "flagged_ids": sorted({r["id"] for r in flagged})}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", choices=["scenarios", "heldout"], default="scenarios")
    data = ap.parse_args().data
    raw = RAW if data == "scenarios" else RAW / data
    scenarios = json.loads((ROOT / "data" / f"{data}.json").read_text())
    truth = {s["id"]: s["truth"] for s in scenarios}
    configs = {}

    # Rules alone (deterministic, no model): what Setup B's verdicts will be
    rule_rows = []
    for s in scenarios:
        d = diagnose(s["measurements"])
        rule_rows.append({"id": s["id"], "verdict": d["verdict"], "confidence": d["confidence"],
                          "follow_up_test": d["follow_up_test"]})
    configs["Rules only (no model)"] = (score(rule_rows, truth), None)

    fc = {}
    files = sorted(raw.glob("*.jsonl")) if raw.exists() else []
    have_a = {f.stem.split("_")[1] for f in files if f.stem.startswith("A_")}
    for f in files:
        setup, model, _ = f.stem.split("_")
        recs = [json.loads(line) for line in f.read_text().splitlines()]
        if setup == "C" and model not in have_a:  # held-out: Setup A = Setup C's first answer
            configs.setdefault(f"Setup A - {model}", ([], []))
            for r in recs:
                configs[f"Setup A - {model}"][0].append(row_from(r, "A", "first"))
                configs[f"Setup A - {model}"][1].append(r["first_cost_usd"])
        key = f"Setup {setup} - {model}"
        configs.setdefault(key, ([], []))
        rows, costs = configs[key]
        for r in recs:
            rows.append(row_from(r, setup))
            # Setup C's cost per diagnosis includes the decide step even when it was reused
            costs.append(r.get("first_cost_usd", 0) + r.get("revision_cost_usd", 0) if setup == "C" else r["cost_usd"])
        if setup == "C":
            fc.setdefault(model, []).extend(recs)

    summary = {}
    for key, val in configs.items():
        if key.startswith("Rules"):
            summary[key] = {**val[0], "cost_per_1000_usd": 0.0}
            continue
        rows, costs = val
        s = score(rows, truth)
        s["cost_per_1000_usd"] = round(1000 * sum(costs) / len(costs), 2)
        s["total_cost_usd"] = round(sum(costs), 4)
        summary[key] = s

    for model, recs in fc.items():
        summary[f"Setup C - {model}"]["fact_check"] = factcheck_stats(recs, truth)
    (ROOT / "results").mkdir(exist_ok=True)
    suffix = "" if data == "scenarios" else f"_{data}"
    (ROOT / "results" / f"summary{suffix}.json").write_text(json.dumps(summary, indent=2) + "\n")
    head = ("| Setup | Diagnoses | Right | Confidently wrong | Ambiguous cases right | "
            "Follow-up on ambiguous | Stable | Cost per 1,000 |")
    lines = [head, "|" + "---|" * 8]
    for k, s in summary.items():
        lines.append(f"| {k} | {s['diagnoses']} | {s['right_overall_pct']}% | "
                     f"{s['confidently_wrong']} ({s['confidently_wrong_pct']}%) | "
                     f"{s['ambiguous_right_pct']}% | {s['ambiguous_follow_up_pct']}% | "
                     f"{s['stable_scenarios']} | ${s['cost_per_1000_usd']} |")
    table = "\n".join(lines)
    miss_txt = "\n".join(f"- {k}: " + ", ".join(f"{i} ({w})" for i, w in s["misses"]) or "none"
                         for k, s in summary.items())
    fc_txt = "\n".join(f"- Setup C - {m}: flagged {v['fact_check']['flagged']}, changed {v['fact_check']['changed']}, "
                        f"fixed {v['fact_check']['fixed']}, broke {v['fact_check']['broke']}"
                        for m, v in ((k.split(' - ')[1], s) for k, s in summary.items() if 'fact_check' in s))
    (ROOT / "results" / f"summary{suffix}.md").write_text(
        table + "\n\nMisses:\n" + miss_txt + ("\n\nFact-check:\n" + fc_txt if fc_txt else "") + "\n")
    print(table)
    print("\nMisses:\n" + miss_txt)
    if fc_txt:
        print("\nFact-check:\n" + fc_txt)


if __name__ == "__main__":
    main()
