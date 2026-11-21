"""Fact-checker for Setup C: Claude decides, code checks a few hard facts.

Written after data/heldout.json was committed. Each check looks only at facts code can know
for certain, and only speaks up when Claude's verdict contradicts one. It never decides by
itself: a flag sends Claude one more call to re-examine, and Claude may keep its answer.

Deliberately NOT included: the old speed/jitter thresholds. Those are judgment calls, which
is where the rules lost to the model.
"""
from rules import degraded

LINE_FAULT_VERDICTS = {"healthy", "bufferbloat", "dns", "service_route", "service_down"}


def _norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def check(scenario, verdict):
    """Return a list of plain-English facts that contradict `verdict` (empty = no flag)."""
    m = scenario["measurements"]
    t = m["targets"]
    radar = m.get("radar", {})
    flags = []

    # F1: the test may not have measured the connection the person is asking about
    up = scenario.get("user_provider")
    measured = radar.get("isp")
    if up and measured and _norm(up) not in _norm(measured) and _norm(measured) not in _norm(up):
        if verdict != "local_network":
            flags.append(f"The person says their provider is {up}, but this test ran over "
                         f"{measured}. The test may not have measured their home connection at all.")

    all_failed = all(not v["ok"] for v in t.values())
    redirects = all(v.get("http_status") in (301, 302, 303, 307, 308) for v in t.values())

    # F2: a login page answers every request
    if all_failed and redirects and verdict != "local_network":
        flags.append("Every site answered with a redirect (HTTP 302). That is the signature of a "
                     "sign-in page on the local network, not an outage.")
    # F3: nothing reachable cannot be a healthy line or a single-service problem
    elif all_failed and verdict in LINE_FAULT_VERDICTS:
        flags.append("No site could be reached at all, including the nearest Cloudflare server.")

    # F4: Radar outage for this provider
    bad = degraded(m) or all_failed
    if radar.get("outage_reported"):
        if bad and verdict != "isp_problem":
            flags.append(f"Cloudflare Radar reports an outage for {measured} right now, and this "
                         f"line is degraded ({', '.join(degraded(m)) or 'nothing reachable'}).")
        if not bad and verdict == "isp_problem":
            flags.append(f"Radar reports an outage for {measured}, but this line measures normal: "
                         f"outages are regional and this one may not affect this home.")

    # F5: the person already ran a second test somewhere else
    rt = m.get("retest")
    if rt and degraded(m):
        rt_bad = degraded(rt)
        if not rt_bad and verdict != "local_network":
            flags.append(f"A retest ({rt['where']}) was healthy while the first test was not. "
                         f"The difference is local to the home or device.")
        if rt_bad and "wired" in rt["where"] and verdict == "local_network":
            flags.append(f"The retest {rt['where']} was just as bad ({', '.join(rt_bad)}), so "
                         f"Wi-Fi is ruled out.")
    return flags
