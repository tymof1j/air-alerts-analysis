from datetime import date, timedelta
import numpy as np
from air_alerts.data import Alert, stamp
from air_alerts.models import DurationModel, booking_budget, conformal_upper, planner_features


def test_future_durations_cannot_change_fitted_survival():
    cutoff = stamp("2026-09-14")
    a = [Alert("old", cutoff-86400, cutoff-84600), Alert("ongoing", cutoff-600, cutoff+600)]
    m1 = DurationModel("recent90").fit(a, cutoff).export()
    a[-1].end = cutoff+999999
    m2 = DurationModel("recent90").fit(a, cutoff).export()
    assert m1 == m2


def test_conditioning_is_not_mean_minus_elapsed():
    cutoff = stamp("2026-09-14")
    a = [Alert(str(i), cutoff-86400*(i+1), cutoff-86400*(i+1)+d*60)
         for i, d in enumerate([10, 20, 100])]
    pred = DurationModel("recent90").fit(a, cutoff).predict(cutoff, 30)
    assert pred["median"] == 70
    assert pred["support"] == 1


def test_week_features_ignore_future_labels():
    days = [date(2025, 1, 1)+timedelta(days=i) for i in range(500)]
    loads = np.arange(500, dtype=float)
    f1 = planner_features(days, loads, 400, 407)
    loads[401:] = 999999
    assert f1 == planner_features(days, loads, 400, 407)


def test_conformal_rank_and_small_sample_abstention():
    assert np.isinf(conformal_upper(range(14)))
    assert conformal_upper(range(20)) == 19
    assert conformal_upper(range(99)) == 94


def test_booking_uses_minutes_not_number_of_alerts():
    assert booking_budget(600, 120, 180, 60) == 240
    assert booking_budget(600, 700) == 0
