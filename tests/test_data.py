from datetime import datetime
import numpy as np

from air_alerts.data import Alert, KYIV, canonical_kyiv, daily_profiles, overlap_minutes, stamp


def test_union_and_clipping():
    assert overlap_minutes([(0, 120), (60, 180), (300, 360)], 60, 330) == 2.5


def test_repeated_start_is_not_an_invented_all_clear():
    alerts, audit = canonical_kyiv([
        {"state": 1, "created_at": "2026-01-01 10:00:00"},
        {"state": 1, "created_at": "2026-01-01 11:00:00"},
        {"state": 0, "created_at": "2026-01-01 11:30:00"},
    ], [])
    assert len(alerts) == 1 and alerts[0].duration == 30
    assert audit["start_without_observed_end"] == 1


def test_daily_duration_across_dst():
    a = Alert("dst", stamp("2025-10-26T00:00:00+03:00"), stamp("2025-10-27T00:00:00+02:00"))
    days, profile = daily_profiles([a], a.end)
    assert profile[days.index(datetime(2025, 10, 26).date())].sum() == 1500


def test_profiles_do_not_use_future_ends():
    start = stamp("2026-01-01T10:00:00+02:00")
    cutoff = start + 1800
    _, p1 = daily_profiles([Alert("x", start, start + 3600)], cutoff)
    _, p2 = daily_profiles([Alert("x", start, start + 90000), Alert("future", cutoff + 1, cutoff + 600)], cutoff)
    assert np.array_equal(p1, p2)
    assert p1.sum() == 30
