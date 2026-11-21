"""Prompts and output schemas for both setups. The model never sees scenario ids or ground truth."""
import json

VERDICTS = ["healthy", "local_network", "isp_problem", "local_or_isp",
            "bufferbloat", "dns", "service_route", "service_down"]
CONFIDENCE = ["high", "medium", "low"]

FIELDS = """Measurement fields (all taken from the user's browser, like speed.cloudflare.com):
- download_mbps, upload_mbps: throughput
- idle_latency_ms, jitter_ms: round trip to the nearest Cloudflare edge with the line idle
- loaded_latency_down_ms / loaded_latency_up_ms: the same round trip while downloading / uploading
- packet_loss_pct: share of test packets lost
- dns_lookup_ms: median time to resolve 5 fresh hostnames; dns_failures: how many of the 5 failed
- targets: time for a small request to each site (ok=false means it failed)
- radar.outage_reported: whether Cloudflare Radar currently reports an outage for the user's provider
- retest (optional): a second test the user already ran somewhere else
null means the value could not be measured."""

LABELS = """Verdicts:
- healthy: nothing wrong that this data can see
- local_network: the problem is inside the home (Wi-Fi, router, or the device)
- isp_problem: the provider's network is degraded or down
- local_or_isp: it is one of the two above and this data cannot tell which
- bufferbloat: fine when idle, latency jumps when the line is busy
- dns: name lookups are slow or failing while the connection itself is fine
- service_route: one service is slow while the rest of the internet is fine
- service_down: one service is failing while the rest of the internet is fine"""

SYSTEM_A = f"""You diagnose home internet problems for ordinary people from browser speed-test data.

{LABELS}

{FIELDS}

Give one verdict and a confidence (high, medium or low). Use high only when the data clearly
points to one cause. If the data fits more than one cause, say so with medium or low
confidence and give one follow-up test the person can run that would tell the causes apart.
Write the explanation in two or three plain sentences a non-technical person understands,
and give one concrete fix. follow_up_test is null when confidence is high."""

SCHEMA_A = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": VERDICTS},
        "confidence": {"type": "string", "enum": CONFIDENCE},
        "explanation": {"type": "string"},
        "fix": {"type": "string"},
        "follow_up_test": {"type": ["string", "null"]},
    },
    "required": ["verdict", "confidence", "explanation", "fix", "follow_up_test"],
    "additionalProperties": False,
}

SYSTEM_B = f"""You explain home internet problems to ordinary people.

A rules engine has already measured the connection and decided the verdict and confidence.
Do not change or second-guess them. Your job is only the wording:
- explanation: two or three plain sentences a non-technical person understands, based on the
  numbers and the rule reasons
- fix: one concrete thing to do
- follow_up_test: when confidence is medium or low, one test that would settle the question
  (you may reword the suggested one); null when confidence is high

{LABELS}

{FIELDS}"""

SCHEMA_B = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "fix": {"type": "string"},
        "follow_up_test": {"type": ["string", "null"]},
    },
    "required": ["explanation", "fix", "follow_up_test"],
    "additionalProperties": False,
}


def user_a(scenario):
    return (f"The person says: \"{scenario['complaint']}\"\n\nMeasurements:\n"
            + json.dumps(scenario["measurements"], indent=2))


def user_b(scenario, rule_out):
    return (user_a(scenario) + "\n\nRules engine result:\n" + json.dumps(rule_out, indent=2))
