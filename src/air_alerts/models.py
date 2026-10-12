"""Conditional survival and seven-day workload forecasting models."""
from datetime import datetime, timedelta
import math

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import KYIV, stamp


def night(hour):
    return hour >= 22 or hour < 6


def hazard_features(start, age):
    current = datetime.fromtimestamp(start + age * 60, KYIV)
    initial = datetime.fromtimestamp(start, KYIV)
    return [math.log1p(age), age / 120,
            math.sin(initial.hour * math.pi / 12), math.cos(initial.hour * math.pi / 12),
            math.sin(current.hour * math.pi / 12), math.cos(current.hour * math.pi / 12),
            math.sin(current.weekday() * 2 * math.pi / 7), math.cos(current.weekday() * 2 * math.pi / 7),
            math.sin(current.month * 2 * math.pi / 12), math.cos(current.month * 2 * math.pi / 12)]


class DurationModel:
    def __init__(self, name):
        self.name = name

    def fit(self, alerts, cutoff):
        self.cutoff = cutoff
        days = int(''.join(c for c in self.name if c.isdigit()) or 365)
        earliest = cutoff - days * 86400 if self.name != "seasonal" else stamp("2023-01-01")
        self.alerts = [a for a in alerts if a.end is not None and a.end < cutoff and a.start >= earliest]
        if not self.alerts:
            raise ValueError("No completed training episodes")
        self.durations = np.array([a.duration for a in self.alerts])
        self.hours = np.array([a.local.hour for a in self.alerts])
        self.months = np.array([a.local.month for a in self.alerts])
        self.years = np.array([a.local.year for a in self.alerts])
        self.hazard = None
        if self.name.startswith("hazard"):
            x, y = [], []
            for a in self.alerts:
                for age in range(0, min(1440, int(math.ceil(a.duration / 5)) * 5), 5):
                    x.append(hazard_features(a.start, age))
                    y.append(int(a.duration <= age + 5))
            self.hazard = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=1000))
            self.hazard.fit(x, y)
        return self

    def residuals(self, start, elapsed, phase="all"):
        dt = datetime.fromtimestamp(start, KYIV)
        mask = np.ones(len(self.durations), dtype=bool)
        if self.name == "seasonal":
            selected = (self.years == dt.year-1) & (self.months == dt.month)
            if selected.sum() >= 20:
                mask &= selected
        if self.name.startswith("daynight") or phase != "all":
            n = night(dt.hour) if phase == "all" else phase == "night"
            selected = mask & (((self.hours >= 22) | (self.hours < 6)) == n)
            if selected.sum() >= 20:
                mask = selected
        return self.durations[mask & (self.durations > elapsed)] - elapsed

    def predict(self, start, elapsed, horizons=(15, 30, 60, 120), phase="all"):
        r = self.residuals(start, elapsed, phase)
        if self.hazard is None:
            return {"probabilities": [float(np.mean(r <= h)) if len(r) else None for h in horizons],
                    "q10": float(np.quantile(r, .1)) if len(r) else None,
                    "median": float(np.quantile(r, .5)) if len(r) else None,
                    "q90": float(np.quantile(r, .9)) if len(r) else None, "support": len(r)}
        ages = np.arange(elapsed, elapsed + 1440, 5)
        hazards = self.hazard.predict_proba([hazard_features(start, age) for age in ages])[:, 1]
        cdf = 1 - np.cumprod(1 - hazards)
        def quantile(q):
            indices = np.flatnonzero(cdf >= q)
            return float((indices[0] + 1) * 5) if len(indices) else None
        return {"probabilities": [float(cdf[min(len(cdf)-1, max(0, int(math.ceil(h/5))-1))]) for h in horizons],
                "q10": quantile(.1), "median": quantile(.5), "q90": quantile(.9), "support": len(r)}

    def export(self):
        result = {"name": self.name, "training_cutoff": self.cutoff,
                  "durations": [{"duration": a.duration, "start": a.start,
                                 "hour": a.local.hour, "month": a.local.month, "year": a.local.year}
                                for a in self.alerts]}
        if self.hazard is not None:
            scaler, classifier = self.hazard.steps[0][1], self.hazard.steps[1][1]
            result["hazard"] = {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                                "coef": classifier.coef_[0].tolist(), "intercept": float(classifier.intercept_[0])}
        return result


def planner_features(days, loads, origin_index, target_index):
    """All load features end at origin; target calendar is known in advance."""
    history = loads[max(0, origin_index - 89):origin_index + 1]
    d = days[target_index]
    recent7, recent30 = history[-7:], history[-30:]
    weekday = [loads[i] for i in range(max(0, origin_index - 89), origin_index + 1)
               if days[i].weekday() == d.weekday()]
    year = [loads[i] for i in range(origin_index + 1)
            if days[i].year == d.year-1 and days[i].month == d.month]
    return [float(np.mean(recent7)), float(np.std(recent7)), float(np.max(recent7)),
            float(np.mean(recent30)), float(np.mean(weekday)) if weekday else float(np.mean(recent30)),
            float(np.mean(year)) if year else float(np.mean(recent30)),
            (target_index-origin_index)/7,
            math.sin(d.month*math.pi/6), math.cos(d.month*math.pi/6),
            *[int(d.weekday() == i) for i in range(7)]]


class PlannerModel:
    def __init__(self, name):
        self.name = name
        self.model = None

    def fit(self, days, loads, cutoff):
        if self.name in ("recent30", "weekday90", "seasonal"):
            return self
        x, y = [], []
        for i, d in enumerate(days):
            if d.weekday() != 6 or i < 90 or i + 7 >= len(days) or days[i+7] >= cutoff:
                continue
            for h in range(1, 8):
                x.append(planner_features(days, loads, i, i+h))
                y.append(loads[i+h])
        if self.name == "ridge":
            self.model = make_pipeline(StandardScaler(), Ridge(alpha=30))
        elif self.name == "boosting":
            self.model = HistGradientBoostingRegressor(loss="absolute_error", max_iter=80,
                                                       max_leaf_nodes=7, l2_regularization=10,
                                                       learning_rate=.06, random_state=42)
        if self.model:
            self.model.fit(x, y)
        return self

    def predict_week(self, days, loads, origin_index, length):
        x = np.array([planner_features(days, loads, origin_index, origin_index+h) for h in range(1, 8)])
        if self.model:
            point = self.model.predict(x)
        else:
            point = x[:, {"recent30": 3, "weekday90": 4, "seasonal": 5}[self.name]]
        return np.clip(point, 0, length)


def conformal_upper(scores, alpha=.05):
    """Finite-sample 'higher' rank, never interpolated or silently capped."""
    values = np.sort(np.asarray(scores, dtype=float))
    rank = math.ceil((len(values) + 1) * (1-alpha))
    return float(values[rank-1]) if rank <= len(values) and len(values) else float("inf")


def booking_budget(length, upper, existing=0, reserve=0):
    return max(0., length - upper - existing - reserve)
