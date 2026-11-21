"""Deterministic diagnosis rules (Setup B decides with these; Claude only explains).

Written after the ground truth in data/scenarios.json was committed, and frozen before any
model run. Thresholds come from common guidance, not from tuning on the scenarios:
  - jitter > 20 ms or loss >= 1% hurts calls and games (ITU-T G.114 / VoIP rules of thumb)
  - latency rising 80+ ms under load is noticeable bufferbloat, 150+ ms is severe
    (roughly the C-to-F range of the Waveform bufferbloat grade)
  - a DNS lookup over 300 ms is slow enough to feel on every new site
  - under 25 Mbps download is below the FCC broadband floor
If a rule misses a scenario, the miss stays in the results. Do not tune these to the data.
"""

JITTER_BAD_MS = 20
LOSS_BAD_PCT = 1.0
IDLE_BAD_MS = 80
DOWNLOAD_BAD_MBPS = 25
BLOAT_SEVERE_MS = 150
BLOAT_MILD_MS = 80
DNS_SLOW_MS = 300
SERVICE_SLOW_EXTRA_MS = 150   # one target this much slower than the Cloudflare edge
OTHERS_OK_EXTRA_MS = 100      # while every other target stays within this of the edge

FOLLOW_UP = {
    "local_or_isp": "Run the test again with the laptop plugged into the router by cable "
                    "(or right next to it). Good there means Wi-Fi; still bad means the provider.",
    "local_network": "Restart the router and retest next to it.",
    "isp_problem": "Restart the modem; if it is still bad, call the provider with these numbers.",
    "bufferbloat": "Turn on SQM or Smart Queue in the router settings and retest under load.",
    "dns": "Switch the DNS server to 1.1.1.1 and retest.",
    "healthy": "Run the test again at the moment the problem happens.",
    "service_route": "Try the service on mobile data; if it is fine there, the path from your provider is the issue.",
    "service_down": "Check the service's status page.",
}


def degraded(m):
    """True when the line itself looks unhealthy (any one sign is enough)."""
    reasons = []
    if m.get("jitter_ms") is not None and m["jitter_ms"] > JITTER_BAD_MS:
        reasons.append(f"jitter {m['jitter_ms']} ms > {JITTER_BAD_MS}")
    if m.get("packet_loss_pct") is not None and m["packet_loss_pct"] >= LOSS_BAD_PCT:
        reasons.append(f"loss {m['packet_loss_pct']}% >= {LOSS_BAD_PCT}")
    if m.get("idle_latency_ms") is not None and m["idle_latency_ms"] >= IDLE_BAD_MS:
        reasons.append(f"idle latency {m['idle_latency_ms']} ms >= {IDLE_BAD_MS}")
    if m.get("download_mbps") is not None and m["download_mbps"] < DOWNLOAD_BAD_MBPS:
        reasons.append(f"download {m['download_mbps']} Mbps < {DOWNLOAD_BAD_MBPS}")
    return reasons


def _out(verdict, confidence, reasons):
    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons,
        "follow_up_test": FOLLOW_UP[verdict] if confidence != "high" else None,
    }


def diagnose(m):
    t = m["targets"]
    edge = t["cloudflare_edge"]
    radar = m.get("radar", {}).get("outage_reported", False)
    bad = degraded(m)

    # 1. Nothing reachable at all
    if not edge["ok"] and all(not v["ok"] for v in t.values()):
        if radar:
            return _out("isp_problem", "high", ["no target reachable", "Radar reports a provider outage"])
        return _out("local_or_isp", "medium", ["no target reachable", "no Radar outage"])

    # 2. User already ran a second test somewhere else
    rt = m.get("retest")
    if rt and bad:
        rt_bad = degraded(rt)
        if not rt_bad:
            return _out("local_network", "high", bad + [f"retest ({rt['where']}) is healthy"])
        if "wired" in rt["where"]:
            return _out("isp_problem", "high", bad + [f"still bad when wired: {', '.join(rt_bad)}"])
        return _out("local_or_isp", "medium", bad + [f"still bad on retest ({rt['where']})"])

    # 3. DNS
    if m.get("dns_failures", 0) > 0 or (m.get("dns_lookup_ms") or 0) > DNS_SLOW_MS:
        why = [f"DNS {m['dns_lookup_ms']} ms, {m['dns_failures']}/5 failed"]
        return _out("dns", "medium" if bad else "high", why + bad)

    # 4/5. One service failing or slow while the edge is fine
    if edge["ok"] and edge["ms"] is not None:
        others = {k: v for k, v in t.items() if k != "cloudflare_edge"}
        failing = [k for k, v in others.items() if not v["ok"]]
        if len(failing) == 1:
            return _out("service_down", "high", [f"{failing[0]} unreachable, everything else answers"])
        slow = [k for k, v in others.items() if v["ok"] and v["ms"] - edge["ms"] > SERVICE_SLOW_EXTRA_MS]
        fine = [k for k, v in others.items() if v["ok"] and v["ms"] - edge["ms"] <= OTHERS_OK_EXTRA_MS]
        if len(slow) == 1 and len(fine) == len(others) - 1:
            s = slow[0]
            return _out("service_route", "high", [f"{s} {t[s]['ms']} ms vs edge {edge['ms']} ms"])

    # 6. Whole line degraded
    if bad:
        if radar:
            return _out("isp_problem", "high", bad + ["Radar reports a provider outage"])
        return _out("local_or_isp", "medium", bad + ["no Radar outage; Wi-Fi and provider look the same here"])

    # 7. Bufferbloat
    idle = m["idle_latency_ms"]
    rise = max(m["loaded_latency_down_ms"], m["loaded_latency_up_ms"]) - idle
    if rise >= BLOAT_SEVERE_MS:
        return _out("bufferbloat", "high", [f"latency rises {rise} ms under load"])
    if rise >= BLOAT_MILD_MS:
        return _out("bufferbloat", "medium", [f"latency rises {rise} ms under load"])

    # 8/9. Healthy
    note = ["all measurements normal"]
    if radar:
        note.append("Radar reports an outage for the provider, but not affecting this line")
    return _out("healthy", "high", note)
