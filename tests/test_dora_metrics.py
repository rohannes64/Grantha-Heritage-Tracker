"""DORA metric arithmetic on made-up deployments (no GitHub calls)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dora_metrics import compute, markdown  # noqa: E402

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


def dep(day, hour, state, lead_h=2.0, took_min=5):
    created = T0 + timedelta(days=day, hours=hour)
    return {"created": created, "finished": created + timedelta(minutes=took_min), "state": state,
            "commit_time": created - timedelta(hours=lead_h)}


def test_four_metrics():
    deploys = [dep(0, 9, "success", lead_h=1), dep(1, 9, "failure"), dep(1, 12, "success", lead_h=3),
               dep(2, 9, "success", lead_h=5), dep(3, 9, "pending")]          # pending is not finished: ignored
    m = compute(deploys, days=7)
    assert m["deploys"] == 4
    assert m["per_week"] == 3.0
    assert m["change_failure_rate"] == 0.25
    # median lead over successes: (1 h + 5 min), (3 h + 5 min), (5 h + 5 min) -> 3.08 h
    assert m["lead_time_h"] == 3.08
    # failure at day 1 09:00, next success finished day 1 12:05 -> 3.08 h
    assert m["time_to_restore_h"] == 3.08


def test_consecutive_failures_restore_from_the_first():
    m = compute([dep(0, 0, "failure"), dep(0, 1, "error"), dep(0, 2, "success")], days=7)
    assert m["change_failure_rate"] == round(2 / 3, 3)
    assert m["time_to_restore_h"] == round((2 * 60 + 5) / 60, 2)


def test_no_deployments():
    m = compute([], days=30)
    assert m == {"deploys": 0, "per_week": 0.0, "lead_time_h": None,
                 "change_failure_rate": None, "time_to_restore_h": None}
    assert "no data" in markdown(m, 30, "production")
