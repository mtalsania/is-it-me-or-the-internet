"""Varied copies of the hand-written scenarios: same fault, different internet plan, new noise.

Why: writing more cases by hand adds more of one author's judgment. Copies test something
else: does a diagnosis stay the same when only the plan (fiber, DSL, 5G home, gigabit cable)
and measurement noise change? The answer is inherited from the original case.

How a copy is made (deterministic, seed 7):
  - values that look "normal for the original 300/20 cable plan" are swapped for the new plan's
    normal values (download/upload within 20% of 305/21, idle latency within 10 ms of 14,
    jitter <= 5 ms)
  - values that carry the fault (low speed, high jitter, loss, slow DNS, a slow or failed
    site) are kept, with +-10% noise
  - latency under load keeps its rise over idle (x0.9-1.1), so bufferbloat stays bufferbloat
  - the provider name changes; a Radar outage flag is kept
Excluded: the two real cases, the cellular case (U04 depends on the provider name), satellite
(O01), and cases with nothing measured (I02, O05).
"""
import copy
import random

PLANS = {
    "fiber": {"isp": "Verizon Fios", "dl": 940, "ul": 880, "idle": 6, "jit": 1.0},
    "dsl": {"isp": "AT&T", "dl": 45, "ul": 5, "idle": 28, "jit": 3.0},
    "5g_home": {"isp": "T-Mobile Home Internet", "dl": 230, "ul": 28, "idle": 34, "jit": 8.0},
    "gig_cable": {"isp": "Xfinity", "dl": 1020, "ul": 41, "idle": 13, "jit": 2.0},
}
BASE_DL, BASE_UL, BASE_IDLE = 305, 21, 14
EXCLUDE = {"M01", "M02", "U04", "O01", "I02", "O05"}


def _n(rng, x, pct=0.10):
    return x * rng.uniform(1 - pct, 1 + pct)


def _r(x):
    return None if x is None else (round(x, 1) if x < 10 else round(x))


def _speeds(m, plan, rng):
    for key, base, new in (("download_mbps", BASE_DL, plan["dl"]), ("upload_mbps", BASE_UL, plan["ul"])):
        v = m.get(key)
        if v is None:
            continue
        m[key] = _r(_n(rng, new) if abs(v - base) <= 0.2 * base else _n(rng, v))


def transform(m, plan, rng):
    m = copy.deepcopy(m)
    old_idle = m.get("idle_latency_ms")
    _speeds(m, plan, rng)
    if old_idle is not None:
        new_idle = _n(rng, plan["idle"]) if abs(old_idle - BASE_IDLE) <= 10 else _n(rng, old_idle + plan["idle"] - BASE_IDLE)
        shift = new_idle - old_idle
        m["idle_latency_ms"] = _r(new_idle)
        for k in ("loaded_latency_down_ms", "loaded_latency_up_ms"):
            if m.get(k) is not None:
                m[k] = _r(new_idle + (m[k] - old_idle) * rng.uniform(0.9, 1.1))
        if m.get("jitter_ms") is not None:
            m["jitter_ms"] = _r(_n(rng, plan["jit"]) if m["jitter_ms"] <= 5 else _n(rng, m["jitter_ms"]))
        if m.get("packet_loss_pct"):
            m["packet_loss_pct"] = round(_n(rng, m["packet_loss_pct"]), 1)
        for t in m["targets"].values():
            if t["ok"] and t["ms"] is not None:
                t["ms"] = _r(max(1, t["ms"] + shift) * rng.uniform(0.95, 1.05))
    if m.get("dns_lookup_ms") is not None:
        m["dns_lookup_ms"] = _r(_n(rng, m["dns_lookup_ms"]))
    m["radar"]["isp"] = plan["isp"]
    if "retest" in m:
        rt = m["retest"]
        _speeds(rt, plan, rng)
        if rt.get("idle_latency_ms") is not None and abs(rt["idle_latency_ms"] - BASE_IDLE) <= 10:
            rt["idle_latency_ms"] = _r(_n(rng, plan["idle"]))
        if rt.get("jitter_ms") is not None and rt["jitter_ms"] <= 5:
            rt["jitter_ms"] = _r(_n(rng, plan["jit"]))
    return m


def make_variants(scenarios, total_needed, seed=7):
    rng = random.Random(seed)
    eligible = [s for s in scenarios if s["id"] not in EXCLUDE]
    names = list(PLANS)
    out = []
    i = 0
    while len(out) < total_needed:
        s = eligible[i % len(eligible)]
        plan_name = names[(i + i // len(eligible)) % len(names)]
        v = copy.deepcopy(s)
        v["id"] = f"V{len(out) + 1:02d}-{s['id']}-{plan_name}"
        v["variant_of"] = s["id"]
        v["measurements"] = transform(s["measurements"], PLANS[plan_name], rng)
        out.append(v)
        i += 1
    return out
