"""Builds data/heldout.json: 20 new cases for testing Setup C (Claude decides, rules fact-check).

Written and committed BEFORE the fact-checker existed, so it can't be tuned to them.
Same labels and grading as data/scenarios.json. One new input: `user_provider`, the
provider the person believes they are on (people know this; a browser can't check it).

Run: python data/build_heldout.py
"""
import json
from pathlib import Path

from build_scenarios import BASE, all_targets, make, wifi_bad

H = []


def add(sid, complaint, user_provider, m, accept, confidence, ambiguous, why, fix_mentions=None):
    truth = {"accept": accept, "confidence": confidence, "ambiguous": ambiguous, "why": why}
    if fix_mentions:
        truth["fix_mentions"] = fix_mentions
    H.append({"id": sid, "complaint": complaint, "user_provider": user_provider,
              "measurements": m, "truth": truth})


AMB = ["medium", "low"]
SIGN_IN = ["sign in", "sign-in", "log in", "login", "log-in", "captive", "portal", "accept the terms"]
OK = ["high", "medium"]

add("K01", "My game lagged badly last night.", "Comcast",
    make({"download_mbps": 288}),
    ["healthy", "local_or_isp", "local_network", "isp_problem"], AMB, True,
    "Healthy now; last night isn't visible. 'Looks fine now, test when it happens.'")
add("K02", "I think my Wi-Fi is acting up. Everything is choppy.", "Comcast",
    make(wifi_bad(dl=33, ul=5, idle=71, jit=35, loss=3.1), all_targets(55),
         radar={"outage_reported": True}),
    ["isp_problem"], OK, False,
    "User blames Wi-Fi, but every target is degraded and Radar reports a provider outage now.")
add("K03", "Is the outage I read about affecting me?", "Comcast",
    make(radar={"outage_reported": True}),
    ["healthy"], OK, False,
    "Radar shows a provider outage somewhere, but this line is perfect. Outages are regional.")
add("K04", "My Xfinity internet feels slow on my phone.", "Xfinity",
    make({"download_mbps": 118, "upload_mbps": 14, "idle_latency_ms": 38, "jitter_ms": 11,
          "loaded_latency_down_ms": 92, "loaded_latency_up_ms": 140},
         all_targets(24), {"isp": "AT&T Mobility"}),
    ["local_network"], OK, False,
    "The test ran over AT&T's cellular network, not the user's Xfinity home line. The phone isn't on home Wi-Fi.")
add("K05", "Calls freeze whenever my partner uploads videos.", "Spectrum",
    make({"upload_mbps": 10, "loaded_latency_up_ms": 512},
         radar={"isp": "Charter Communications"}),
    ["bufferbloat"], OK, False,
    "Upload bufferbloat. (Spectrum is Charter's brand, so the provider name is not a mismatch.)")
add("K06", "Nothing works at all.", "Verizon Fios",
    make({"download_mbps": 0.0, "upload_mbps": 0.0, "idle_latency_ms": None, "jitter_ms": None,
          "loaded_latency_down_ms": None, "loaded_latency_up_ms": None, "packet_loss_pct": 100.0,
          "dns_lookup_ms": None, "dns_failures": 5},
         {k: {"ok": False, "ms": None} for k in BASE["targets"]},
         radar={"isp": "Verizon Fios", "outage_reported": False}),
    ["local_or_isp", "local_network", "isp_problem"], AMB, True,
    "Total loss, no Radar outage. Router, modem or line; can't tell without a check at the router.")
add("K07", "Coffee shop Wi-Fi says connected but pages won't open.", "Coffee shop Wi-Fi",
    make({"download_mbps": 0.0, "upload_mbps": 0.0, "idle_latency_ms": None, "jitter_ms": None,
          "loaded_latency_down_ms": None, "loaded_latency_up_ms": None, "packet_loss_pct": None,
          "dns_lookup_ms": 25, "dns_failures": 0},
         {k: {"ok": False, "ms": None, "http_status": 302} for k in BASE["targets"]},
         radar={"isp": "Coffee shop Wi-Fi", "outage_reported": False}),
    ["local_network"], OK, False,
    "Every site redirects (302): the user hasn't signed in to the coffee shop's Wi-Fi yet. "
    "No verdict says exactly 'sign in', so any verdict whose fix tells them to sign in also counts "
    "(changed after Mihir's review, before any run).",
    fix_mentions=SIGN_IN)
add("K08", "Slow in the kitchen.", "Comcast",
    make(wifi_bad(dl=24, ul=6, idle=44, jit=29, loss=2.0), all_targets(30),
         retest={"where": "laptop wired to the router", "download_mbps": 302, "upload_mbps": 22,
                 "idle_latency_ms": 13, "jitter_ms": 1.8, "packet_loss_pct": 0.0}),
    ["local_network"], OK, False,
    "Wired is perfect. Wi-Fi coverage in the kitchen.")
add("K09", "Slow everywhere, even with a cable.", "Comcast",
    make(wifi_bad(dl=31, ul=5, idle=92, jit=31, loss=2.6), all_targets(78),
         retest={"where": "laptop wired to the router", "download_mbps": 33, "upload_mbps": 5,
                 "idle_latency_ms": 90, "jitter_ms": 30, "packet_loss_pct": 2.4}),
    ["isp_problem", "local_or_isp"], OK, False,
    "Bad even when wired, so not Wi-Fi. Most likely the line or provider; the modem is possible.")
add("K10", "Websites hang for a second before loading.", "Comcast",
    make({"dns_lookup_ms": 910}),
    ["dns"], OK, False, "Slow DNS, everything else fine.")
add("K11", "Zoom freezes when the cloud backup runs.", "Comcast",
    make({"loaded_latency_up_ms": 603}),
    ["bufferbloat"], OK, False, "Upload bufferbloat.")
add("K12", "Netflix buffers, YouTube is fine.", "Comcast",
    make(targets={"netflix": {"ms": 243}}),
    ["service_route"], OK, False, "Only the Netflix path is slow.")
add("K13", "Zoom shows an error page.", "Comcast",
    make(targets={"zoom": {"ok": False, "ms": None, "http_status": 503}}),
    ["service_down"], OK, False, "Zoom returns 503; the rest is fine.")
add("K14", "Calls keep cutting out.", "Comcast",
    make(wifi_bad(dl=160, ul=15, idle=29, jit=33, loss=2.9), all_targets(14)),
    ["local_or_isp", "local_network", "isp_problem"], AMB, True,
    "Jitter and loss everywhere, no outage, no retest. Wi-Fi vs line can't be separated.")
add("K15", "Downloads are slow.", "AT&T",
    make({"download_mbps": 15, "upload_mbps": 14, "loaded_latency_down_ms": 46}, radar={"isp": "AT&T"}),
    ["local_or_isp", "local_network", "isp_problem", "healthy"], AMB, True,
    "Only download is low. Weak Wi-Fi rate, a cheap plan, or throttling.")
add("K16", "Our smart speaker keeps dropping off.", "Comcast",
    make(),
    ["healthy", "local_network", "local_or_isp"], AMB, True,
    "The laptop test is healthy; the speaker wasn't measured.")
add("K17", "We have Starlink. Is this normal?", "Starlink",
    make({"download_mbps": 163, "upload_mbps": 17, "idle_latency_ms": 38, "jitter_ms": 14,
          "loaded_latency_down_ms": 86, "loaded_latency_up_ms": 97, "packet_loss_pct": 0.8},
         all_targets(26), {"isp": "SpaceX Starlink"}),
    ["healthy"], OK, False,
    "Normal for low-orbit satellite internet: some jitter and minor loss, no fault.")
add("K18", "My 5G home internet stutters on video calls.", "T-Mobile Home Internet",
    make({"download_mbps": 196, "upload_mbps": 21, "idle_latency_ms": 36, "jitter_ms": 24,
          "loaded_latency_down_ms": 98, "loaded_latency_up_ms": 113, "packet_loss_pct": 0.6},
         all_targets(22), {"isp": "T-Mobile Home Internet"}),
    ["local_or_isp", "isp_problem", "local_network", "healthy"], AMB, True,
    "Jitter is on the high side even for 5G home. Could be the 5G signal at the window or the home Wi-Fi.")
add("K19", "Internet is completely down.", "Spectrum",
    make({"download_mbps": 0.0, "upload_mbps": 0.0, "idle_latency_ms": None, "jitter_ms": None,
          "loaded_latency_down_ms": None, "loaded_latency_up_ms": None, "packet_loss_pct": 100.0,
          "dns_lookup_ms": None, "dns_failures": 5},
         {k: {"ok": False, "ms": None} for k in BASE["targets"]},
         radar={"isp": "Charter Communications", "outage_reported": True}),
    ["isp_problem"], OK, False, "Nothing reachable and Radar reports a provider outage.")
add("K20", "Sites are slow to start and Zoom won't connect.", "Comcast",
    make({"dns_lookup_ms": 640},
         targets={"zoom": {"ok": False, "ms": None, "error": "connection timed out"}}),
    ["dns", "service_down", "service_route"], OK, False,
    "Two separate problems: slow DNS and Zoom unreachable. Naming either is right.")


def main():
    out = Path(__file__).parent / "heldout.json"
    out.write_text(json.dumps(H, indent=2) + "\n")
    print(f"wrote {len(H)} held-out cases ({sum(h['truth']['ambiguous'] for h in H)} ambiguous) to {out}")


if __name__ == "__main__":
    main()
