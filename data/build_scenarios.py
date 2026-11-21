"""Builds data/scenarios.json: 30 synthetic "my internet is bad" cases plus 2 real ones, each with a locked answer.

Every number is something a browser page can measure (the same things speed.cloudflare.com
shows), plus one outside signal: whether Cloudflare Radar reports an outage for the user's
provider. The ground truth was written from how home networks actually fail, before the
rules in src/rules.py existed and before any model saw the cases.

Labels
  healthy        nothing wrong that this data can see
  local_network  the problem is inside the home: Wi-Fi, the router, or the device
  isp_problem    the provider's network is degraded or down
  local_or_isp   it is one of the two above, and browser data can't tell which
  bufferbloat    fine when idle, latency explodes when the line is busy
  dns            name lookups are slow or failing, the connection itself is fine
  service_route  one service is slow while the rest of the internet is fine
  service_down   one service is failing while the rest of the internet is fine

A scenario is "ambiguous" when a careful network engineer, looking only at this data, could
not separate the causes. For those, any of `accept` is right, but only at medium or low
confidence, and a good answer names a follow-up test.

Run: python data/build_scenarios.py
"""
import copy
import json
from pathlib import Path

BASE = {
    # cable plan around 300/20, measured from a laptop
    "download_mbps": 305,
    "upload_mbps": 21,
    "idle_latency_ms": 14,
    "jitter_ms": 2.1,
    "loaded_latency_down_ms": 36,
    "loaded_latency_up_ms": 44,
    "packet_loss_pct": 0.0,
    "dns_lookup_ms": 19,
    "dns_failures": 0,  # out of 5 fresh hostnames
    "targets": {
        "cloudflare_edge": {"ok": True, "ms": 15},
        "google": {"ok": True, "ms": 21},
        "netflix": {"ok": True, "ms": 24},
        "zoom": {"ok": True, "ms": 43},
    },
    "radar": {"isp": "Comcast", "outage_reported": False},
}


def make(over=None, targets=None, radar=None, retest=None):
    m = copy.deepcopy(BASE)
    m.update(over or {})
    for name, vals in (targets or {}).items():
        m["targets"][name].update(vals)
    if radar:
        m["radar"].update(radar)
    if retest:
        m["retest"] = retest
    return m


def wifi_bad(dl=38, ul=9, idle=48, jit=34, loss=2.5):
    """Numbers typical of a weak or crowded Wi-Fi link (or a sick provider line)."""
    return {
        "download_mbps": dl, "upload_mbps": ul, "idle_latency_ms": idle,
        "jitter_ms": jit, "loaded_latency_down_ms": idle + 70,
        "loaded_latency_up_ms": idle + 85, "packet_loss_pct": loss,
    }


def all_targets(ms_add):
    return {k: {"ms": v["ms"] + ms_add} for k, v in BASE["targets"].items()}


S = []


def add(sid, complaint, measurements, accept, confidence, ambiguous, why):
    S.append({
        "id": sid,
        "complaint": complaint,
        "measurements": measurements,
        "truth": {
            "accept": accept,            # any of these verdicts is right
            "confidence": confidence,    # confidence levels that count as right
            "ambiguous": ambiguous,
            "why": why,
        },
    })


# ---------- healthy (4 clear + 1 ambiguous below) ----------
add("H01", "Netflix was buffering last night.", make(),
    ["healthy"], ["high", "medium"], False,
    "Everything is normal right now. Last night isn't visible in this data, but nothing here is broken.")
add("H02", "The speed test says 900 but it still feels slow.",
    make({"download_mbps": 912, "upload_mbps": 884, "idle_latency_ms": 6, "jitter_ms": 0.8,
          "loaded_latency_down_ms": 11, "loaded_latency_up_ms": 13, "dns_lookup_ms": 9},
         all_targets(-8)),
    ["healthy"], ["high", "medium"], False,
    "Gigabit fiber with low latency. Nothing in the network is slow.")
add("H03", "Is my internet slow?",
    make({"download_mbps": 48, "upload_mbps": 4.6, "idle_latency_ms": 27, "jitter_ms": 3.0,
          "loaded_latency_down_ms": 58, "loaded_latency_up_ms": 71, "dns_lookup_ms": 24},
         all_targets(12), {"isp": "AT&T"}),
    ["healthy"], ["high", "medium"], False,
    "A modest DSL-class plan working as designed: steady latency, no loss, no bloat.")
add("H04", "I saw on X that Comcast is down. Is mine affected?",
    make({"download_mbps": 297}, radar={"outage_reported": True}),
    ["healthy"], ["high", "medium"], False,
    "Radar shows a Comcast outage somewhere, but this connection measures perfectly. Outages are regional.")

# ---------- bufferbloat (3) ----------
add("B01", "Zoom freezes whenever my kid is gaming or downloading.",
    make({"loaded_latency_down_ms": 486, "loaded_latency_up_ms": 212}),
    ["bufferbloat"], ["high", "medium"], False,
    "Idle latency 14 ms jumps to 486 ms under download. Classic bufferbloat in the router or modem.")
add("B02", "Video calls break up when I upload files to Google Drive.",
    make({"upload_mbps": 11, "loaded_latency_down_ms": 52, "loaded_latency_up_ms": 917}),
    ["bufferbloat"], ["high", "medium"], False,
    "Upload saturation pushes latency to ~900 ms. Upload-side bufferbloat, common on cable.")
add("B03", "Games lag only in the evening when everyone is home.",
    make({"download_mbps": 141, "upload_mbps": 19, "idle_latency_ms": 19, "jitter_ms": 4.2,
          "loaded_latency_down_ms": 344, "loaded_latency_up_ms": 389}),
    ["bufferbloat"], ["high", "medium"], False,
    "Healthy at idle, 300+ ms once the line is busy. Busy household plus bufferbloat.")

# ---------- dns (3) ----------
add("D01", "Websites take forever to start loading, then load fast.",
    make({"dns_lookup_ms": 1840}),
    ["dns"], ["high", "medium"], False,
    "Lookups take ~1.8 s while speed and latency are perfect. The DNS resolver is the bottleneck.")
add("D02", "Some sites just don't open. Others are fine.",
    make({"dns_lookup_ms": 410, "dns_failures": 2}),
    ["dns"], ["high", "medium"], False,
    "2 of 5 fresh names fail to resolve; the line itself is clean. DNS problem.")
add("D03", "Everything feels sluggish when I click a link.",
    make({"dns_lookup_ms": 690, "download_mbps": 88, "upload_mbps": 11, "idle_latency_ms": 22,
          "loaded_latency_down_ms": 61, "loaded_latency_up_ms": 70}, all_targets(7)),
    ["dns"], ["high", "medium"], False,
    "A slower but healthy plan with ~700 ms lookups. The click-to-load delay is DNS.")

# ---------- isp_problem, clear (3) ----------
add("I01", "Everything is slow and Zoom keeps dropping.",
    make(wifi_bad(dl=21, ul=4, idle=96, jit=41, loss=4.1), all_targets(85),
         radar={"outage_reported": True}),
    ["isp_problem"], ["high", "medium"], False,
    "Every target is slow and lossy, and Radar reports an outage for this provider right now.")
add("I02", "Nothing loads at all.",
    make({"download_mbps": 0.0, "upload_mbps": 0.0, "idle_latency_ms": None, "jitter_ms": None,
          "loaded_latency_down_ms": None, "loaded_latency_up_ms": None, "packet_loss_pct": 100.0,
          "dns_lookup_ms": None, "dns_failures": 5},
         {k: {"ok": False, "ms": None} for k in BASE["targets"]},
         radar={"isp": "Spectrum", "outage_reported": True}),
    ["isp_problem"], ["high", "medium"], False,
    "Total loss of connectivity, confirmed by a Radar outage for the provider. (Radar is checked by our server, so it still loads.)")
add("I03", "Slow on Wi-Fi, so I plugged in a cable. Still slow.",
    make(wifi_bad(dl=34, ul=6, idle=88, jit=29, loss=3.0), all_targets(70),
         retest={"where": "laptop wired to the router", "download_mbps": 36, "upload_mbps": 6,
                 "idle_latency_ms": 85, "jitter_ms": 27, "packet_loss_pct": 2.8}),
    ["isp_problem"], ["high", "medium"], False,
    "Bad on Wi-Fi and equally bad on a cable. Wi-Fi is ruled out. It's the line or the provider, with modem/router a distant second.")

# ---------- local_network, clear (3) ----------
add("L01", "Upstairs bedroom is unusable for calls.",
    make(wifi_bad(), all_targets(35),
         retest={"where": "laptop next to the router", "download_mbps": 296, "upload_mbps": 21,
                 "idle_latency_ms": 15, "jitter_ms": 2.4, "packet_loss_pct": 0.0}),
    ["local_network"], ["high", "medium"], False,
    "Bad upstairs, perfect next to the router, same device. Wi-Fi coverage.")
add("L02", "My laptop is slow but my phone seems fine.",
    make(wifi_bad(dl=12, ul=3, idle=31, jit=22, loss=1.2), all_targets(20),
         retest={"where": "phone in the same room", "download_mbps": 284, "upload_mbps": 20,
                 "idle_latency_ms": 16, "jitter_ms": 2.9, "packet_loss_pct": 0.0}),
    ["local_network"], ["high", "medium"], False,
    "Same room, same Wi-Fi, other device is fine. The laptop (driver, VPN, old Wi-Fi card) is the problem.")
add("L03", "Wi-Fi drops constantly since we got a new microwave.",
    make(wifi_bad(dl=55, ul=12, idle=39, jit=47, loss=5.5), all_targets(28),
         retest={"where": "laptop wired to the router", "download_mbps": 310, "upload_mbps": 22,
                 "idle_latency_ms": 13, "jitter_ms": 1.9, "packet_loss_pct": 0.0}),
    ["local_network"], ["high", "medium"], False,
    "Wired is perfect, Wi-Fi is lossy. 2.4 GHz interference inside the home.")

# ---------- service_route (2) ----------
add("R01", "Only Zoom is laggy. Everything else is fine.",
    make(targets={"zoom": {"ms": 312}}),
    ["service_route"], ["high", "medium"], False,
    "Zoom takes 312 ms while the Cloudflare edge takes 15 ms and Google 21 ms. The path to Zoom is the problem, not the home line.")
add("R02", "Netflix buffers but YouTube is perfect.",
    make(targets={"netflix": {"ms": 268}}),
    ["service_route"], ["high", "medium"], False,
    "Only the Netflix server is slow to reach. A routing or peering issue between the provider and Netflix.")

# ---------- service_down (2) ----------
add("X01", "Netflix shows an error page.",
    make(targets={"netflix": {"ok": False, "ms": None, "http_status": 503}}),
    ["service_down"], ["high", "medium"], False,
    "Netflix returns 503 while everything else is fast. Netflix is having a problem.")
add("X02", "Can't join my Zoom meeting.",
    make(targets={"zoom": {"ok": False, "ms": None, "http_status": None, "error": "connection timed out"}}),
    ["service_down", "service_route"], ["high", "medium"], False,
    "Zoom times out while the rest of the internet is fine. Zoom-side failure, or the path to it.")

# ---------- ambiguous: Wi-Fi vs provider can't be separated (8) ----------
amb_accept = ["local_or_isp", "local_network", "isp_problem"]
amb_conf = ["medium", "low"]
add("A01", "Everything is slow tonight.",
    make(wifi_bad(), all_targets(35)),
    amb_accept, amb_conf, True,
    "Slow, jittery and lossy to every target, no Radar outage, no retest. Weak Wi-Fi and a sick line look identical from a browser.")
add("A02", "Calls keep cutting out.",
    make(wifi_bad(dl=190, ul=17, idle=24, jit=38, loss=3.4), all_targets(10)),
    amb_accept, amb_conf, True,
    "Speed is fine but jitter and loss are high everywhere. Could be Wi-Fi interference or line noise.")
add("A03", "The internet randomly freezes for a few seconds.",
    make({"jitter_ms": 27, "packet_loss_pct": 1.6, "idle_latency_ms": 21}, all_targets(6)),
    amb_accept, amb_conf, True,
    "Short freezes with loss but good speed. Wi-Fi roaming, router, or line, can't tell.")
add("A04", "Downloads are really slow.",
    make({"download_mbps": 17, "upload_mbps": 15, "loaded_latency_down_ms": 49}),
    amb_accept + ["healthy"], amb_conf, True,
    "Low download, everything else clean. Could be a weak Wi-Fi link rate, a cheap plan, or provider throttling.")
add("A05", "Pages load slowly everywhere.",
    make({"idle_latency_ms": 118, "jitter_ms": 9, "loaded_latency_down_ms": 160,
          "loaded_latency_up_ms": 171}, all_targets(104)),
    amb_accept, amb_conf, True,
    "High latency to every target including the nearby edge, low jitter, no loss. Bad routing at the provider, or a VPN/proxy on the device.")
add("A06", "My video calls are choppy and my partner's are too.",
    make(wifi_bad(dl=62, ul=5, idle=57, jit=31, loss=2.2), all_targets(42), {"isp": "Verizon Fios"}),
    amb_accept, amb_conf, True,
    "Two devices affected points away from one device, but both could be on the same bad Wi-Fi.")
add("A07", "Everything is slow and I think Comcast is down.",
    make(wifi_bad(dl=44, ul=8, idle=52, jit=30, loss=2.0), all_targets(38)),
    amb_accept, amb_conf, True,
    "User blames Comcast, but Radar shows no outage. The data fits Wi-Fi just as well as the provider.")
add("A08", "Slow in the evenings, fine in the morning.",
    make({"download_mbps": 64, "idle_latency_ms": 33, "jitter_ms": 14,
          "loaded_latency_down_ms": 98, "loaded_latency_up_ms": 104, "packet_loss_pct": 0.4},
         all_targets(18)),
    amb_accept + ["bufferbloat"], amb_conf, True,
    "Evening slowdowns fit provider congestion, but a busy home Wi-Fi does the same. One snapshot can't tell.")

# ---------- ambiguous: the problem isn't visible right now (2) ----------
add("A09", "The internet drops for a minute every few hours.",
    make(),
    ["healthy", "local_or_isp", "local_network", "isp_problem"], amb_conf, True,
    "A healthy snapshot can't rule out an intermittent drop. The honest answer is 'looks fine now, test when it happens'.")
add("A10", "Zoom froze for everyone in my meeting earlier.",
    make({"download_mbps": 288}),
    ["healthy", "service_down", "service_route"], amb_conf, True,
    "Everyone froze, so it was likely Zoom, but it's over and this data can't confirm it. Any of these with honest hedging is fine.")


# ---------- real case (Mihir's home connection, 2026-11-21) ----------
# Laptop on Verizon Wi-Fi. fast.com: 84/64 Mbps, 10 ms unloaded, 741 ms loaded.
# Waveform on the same laptop: 13 ms idle, jitter 3.8, +44 ms while downloading, and its
# upload-latency step never finished. So the 741 ms is assigned to the upload side.
# Two tools were combined; target and DNS timings were not measured and use healthy values.
add("M01", "My Zoom calls freeze for a few seconds at random.",
    make({"download_mbps": 84, "upload_mbps": 64, "idle_latency_ms": 10, "jitter_ms": 3.8,
          "loaded_latency_down_ms": 54, "loaded_latency_up_ms": 741},
         radar={"isp": "Verizon Fios"}),
    ["bufferbloat"], ["high", "medium"], False,
    "Real measurement: 10 ms idle, 741 ms while uploading. Severe upload bufferbloat; calls freeze whenever a backup or sync uploads.")
add("M02", "My Zoom calls freeze for a few seconds at random. My phone at the same desk seems fine.",
    make({"download_mbps": 84, "upload_mbps": 64, "idle_latency_ms": 10, "jitter_ms": 3.8,
          "loaded_latency_down_ms": 54, "loaded_latency_up_ms": 741},
         radar={"isp": "Verizon Fios"},
         retest={"where": "phone at the same desk, same Wi-Fi", "download_mbps": 310,
                 "upload_mbps": 180, "idle_latency_ms": 6, "jitter_ms": None,
                 "packet_loss_pct": None, "loaded_latency_ms": 26}),
    ["local_network"], ["high", "medium"], False,
    "Real measurement, with the phone retest (fast.com, 00:39 ET): same spot, same Wi-Fi, 310/180 Mbps and 26 ms loaded. The line and the router are fine; the laptop's Wi-Fi link is the bottleneck. A router fix (SQM) would be the wrong advice.")

def main():
    out = Path(__file__).parent / "scenarios.json"
    out.write_text(json.dumps(S, indent=2) + "\n")
    amb = sum(s["truth"]["ambiguous"] for s in S)
    print(f"wrote {len(S)} scenarios ({amb} ambiguous) to {out}")


if __name__ == "__main__":
    main()
