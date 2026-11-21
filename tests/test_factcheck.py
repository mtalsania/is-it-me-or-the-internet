import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from factcheck import check  # noqa: E402

HELD = {h["id"]: h for h in json.loads((ROOT / "data" / "heldout.json").read_text())}


def test_wrong_network_flagged():
    assert check(HELD["K04"], "healthy")
    assert not check(HELD["K04"], "local_network")


def test_captive_portal_and_total_outage():
    assert check(HELD["K07"], "isp_problem")
    assert check(HELD["K19"], "healthy")


def test_radar_outage_on_healthy_line_flags_isp_verdict():
    assert check(HELD["K03"], "isp_problem")
    assert not check(HELD["K03"], "healthy")


class FakeClient:
    """Returns a fixed verdict first, then a revised one, without any network call."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **req):
        out = self.answers.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(out))], stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500))


def _ans(v, c="high"):
    return {"verdict": v, "confidence": c, "explanation": "x", "fix": "y", "follow_up_test": None}


def test_setup_c_revises_only_when_flagged():
    from run_eval import call_c
    fixed = call_c(FakeClient([_ans("healthy"), _ans("local_network")]), "claude-sonnet-5-5", HELD["K04"], 1)
    assert fixed["flags"] and fixed["output"]["verdict"] == "local_network"
    clean = call_c(FakeClient([_ans("dns")]), "claude-sonnet-5-5", HELD["K10"], 1)
    assert not clean["flags"] and clean["revision_cost_usd"] == 0
