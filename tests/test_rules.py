import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))
from build_scenarios import BASE  # noqa: E402
from rules import diagnose  # noqa: E402


def m(**over):
    x = copy.deepcopy(BASE)
    x.update(over)
    return x


def test_healthy_line_is_healthy_high():
    assert diagnose(m())["verdict"] == "healthy"
    assert diagnose(m())["follow_up_test"] is None


def test_bloat_thresholds():
    assert diagnose(m(loaded_latency_down_ms=14 + 150))["verdict"] == "bufferbloat"
    assert diagnose(m(loaded_latency_down_ms=14 + 100))["confidence"] == "medium"
    assert diagnose(m(loaded_latency_down_ms=14 + 79))["verdict"] == "healthy"


def test_degraded_without_radar_is_ambiguous_with_follow_up():
    d = diagnose(m(jitter_ms=30))
    assert (d["verdict"], d["confidence"]) == ("local_or_isp", "medium")
    assert d["follow_up_test"]


def test_degraded_with_radar_is_isp():
    x = m(jitter_ms=30)
    x["radar"] = {"isp": "X", "outage_reported": True}
    assert diagnose(x)["verdict"] == "isp_problem"


def test_dns_beats_everything_but_outage():
    assert diagnose(m(dns_lookup_ms=301))["verdict"] == "dns"


def test_model_never_sees_ids_or_truth():
    from prompts import user_a
    sc = json.loads((ROOT / "data" / "scenarios.json").read_text())
    for s in sc:
        text = user_a(s)
        assert s["id"] not in text and "accept" not in text and "ambiguous" not in text
