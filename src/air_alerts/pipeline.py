"""Two-stage build: select on development data, then evaluate the frozen choice."""
import argparse
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from .data import ROOT, SNAPSHOT, KYIV, daily_profiles, load_regions, stamp, working_load
from .models import DurationModel, PlannerModel, conformal_upper

PROTOCOL = json.loads((ROOT / "config/protocol.json").read_text())


def fingerprint():
    paths = [ROOT / "config/protocol.json", ROOT / "src/air_alerts/models.py", ROOT / "src/air_alerts/data.py", ROOT / "src/air_alerts/pipeline.py"]
    paths += sorted(SNAPSHOT.glob("*.json")) + sorted(SNAPSHOT.glob("*.csv"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(x) for x in value]
    if isinstance(value, (float, np.floating)):
        return round(float(value), 6) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def duration_eval(model, alerts, start, end):
    result = []
    for a in alerts:
        if a.start < start or a.start >= end or a.end is None:
            continue
        entries = []
        for age in PROTOCOL["duration_landmarks"]:
            origin = a.start + age * 60
            if origin >= a.end or origin >= end:
                continue
            pred = model.predict(a.start, age)
            p = pred["probabilities"]
            if any(x is None for x in p):
                continue
            remaining = a.duration-age
            brier = np.mean([(prob - int(remaining <= h))**2
                             for prob, h in zip(p, PROTOCOL["duration_probability_horizons"])])
            entries.append({"elapsed": age, "brier": brier,
                            "absolute_error": abs(pred["median"]-remaining) if pred["median"] is not None else None,
                            "covered80": int(pred["q10"] <= remaining <= pred["q90"])
                            if pred["q10"] is not None and pred["q90"] is not None else None,
                            "remaining": remaining})
        if entries:
            result.append({"id": a.id, "start": a.start, "level": a.level,
                           "night": a.local.hour >=22 or a.local.hour <6,
                           "brier": float(np.mean([r["brier"] for r in entries])),
                           "mae": float(np.mean([r["absolute_error"] for r in entries if r["absolute_error"] is not None])),
                           "entries": entries})
    return result


def duration_summary(rows):
    if not rows:
        return {"episodes": 0, "brier": None, "mae": None, "coverage80": None}
    cover = [np.mean([e["covered80"] for e in row["entries"] if e["covered80"] is not None]) for row in rows]
    return {"episodes": len(rows), "brier": np.mean([r["brier"] for r in rows]),
            "mae": np.mean([r["mae"] for r in rows]), "coverage80": np.mean(cover)}


def weekly_origins(days, start, end):
    return [i for i, d in enumerate(days) if d.weekday() == 6 and i >= 90 and i+7 < len(days)
            and start <= days[i+1] < end and days[i+7] < end]


def planner_eval(model, days, loads, start, end, length):
    rows = []
    for i in weekly_origins(days, start, end):
        pred = model.predict_week(days, loads, i, length)
        for h, p in enumerate(pred, 1):
            rows.append({"week": days[i+1].isoformat(), "date": days[i+h].isoformat(),
                         "horizon": h, "point": float(p), "actual": float(loads[i+h])})
    return rows


def select():
    regions, _ = load_regions()
    cutoff = max(a.start for a in regions["Kyiv City"])
    choices = {"fingerprint": fingerprint(), "protocol": PROTOCOL, "regions": {}}
    for region, alerts in regions.items():
        print("development:", region, flush=True)
        scores = {}
        candidates = PROTOCOL["duration_candidates"] if region == "Kyiv City" else PROTOCOL["duration_candidates"][:5]
        for name in candidates:
            folds = []
            for value in PROTOCOL["duration_validation_starts"]:
                begin = stamp(value)
                try:
                    m = DurationModel(name).fit(alerts, begin)
                    summary = duration_summary(duration_eval(m, alerts, begin, begin+14*86400))
                    if summary["brier"] is not None:
                        folds.append(summary["brier"])
                except ValueError:
                    pass
            scores[name] = float(np.mean(folds)) if folds else 1.
        duration_choice = min(scores, key=scores.get)
        days, profile = daily_profiles(alerts, cutoff)
        shifts = {}
        for sh, eh in PROTOCOL["planner_shifts"]:
            loads, length = working_load(profile, sh, eh), (eh-sh)*60
            results = {}
            candidates = PROTOCOL["planner_candidates"] if region == "Kyiv City" else PROTOCOL["planner_candidates"][:3]
            for name in candidates:
                folds = []
                for value in PROTOCOL["planner_validation_starts"]:
                    begin = date.fromisoformat(value)
                    model = PlannerModel(name).fit(days, loads, begin)
                    rows = planner_eval(model, days, loads, begin, begin+timedelta(days=14), length)
                    if rows:
                        folds.append(np.mean([abs(r["actual"]-r["point"]) for r in rows]))
                results[name] = float(np.mean(folds))
            shifts[f"{sh}-{eh}"] = {"selected": min(results, key=results.get), "validation_mae": results}
        choices["regions"][region] = {"duration": duration_choice, "duration_validation_brier": scores,
                                       "shifts": shifts, "secondary": region != "Kyiv City"}
    write(ROOT / "reports/selection.json", choices)
    print("Model selection written. No final holdout errors computed.", flush=True)


def coverage_interval(successes, total):
    if not total:
        return [None, None]
    c = binomtest(successes, total).proportion_ci(confidence_level=.95, method="exact")
    return [float(c.low), float(c.high)]


def calibrate_week(rows):
    scores = [max(0, r["actual"] - r["point"]) for r in rows]
    grouped = {}
    for r, s in zip(rows, scores):
        grouped.setdefault(r["week"], []).append(s)
    weeks = [max(values) for values in grouped.values() if len(values) == 7]
    return {"daily_radius": conformal_upper(scores), "weekly_radius": conformal_upper(weeks),
            "days": len(scores), "weeks": len(weeks)}


def evaluate():
    selection = json.loads((ROOT / "reports/selection.json").read_text())
    if selection["fingerprint"] != fingerprint():
        raise ValueError("Data, model or protocol changed after selection; regenerate selection before final evaluation")
    regions, audit = load_regions()
    snapshot_time = max(a.start for a in regions["Kyiv City"])
    start, end = stamp(PROTOCOL["holdout_start"]), stamp(PROTOCOL["holdout_end_exclusive"])
    forecast_rows, duration_models, report, histories, replay_rows = [], [], {}, [], []
    for region, alerts in regions.items():
        print("frozen evaluation:", region, flush=True)
        choice = selection["regions"][region]
        duration = DurationModel(choice["duration"]).fit(alerts, stamp(PROTOCOL["duration_fit_end"]))
        duration_models.append({"region": region, "model": json.dumps(clean(duration.export())), "secondary": region != "Kyiv City"})
        baselines = {}
        selected_rows = []
        for name in choice["duration_validation_brier"]:
            try:
                m = duration if name == choice["duration"] else DurationModel(name).fit(alerts, stamp(PROTOCOL["duration_fit_end"]))
            except ValueError:
                baselines[name] = {**duration_summary([]), "status": "insufficient recent training events"}
                continue
            rows = duration_eval(m, alerts, start, end)
            baselines[name] = duration_summary(rows)
            if name == choice["duration"]:
                selected_rows = rows
        days, profile = daily_profiles(alerts, snapshot_time)
        real_length = len(days)
        for j in range(1, 8):
            days.append(days[real_length-1]+timedelta(days=j))
        profile = np.concatenate([profile, np.zeros((7, 96))])
        shift_report = {}
        for sh, eh in PROTOCOL["planner_shifts"]:
            key, length = f"{sh}-{eh}", (eh-sh)*60
            loads = working_load(profile, sh, eh)
            chosen = choice["shifts"][key]["selected"]
            model = PlannerModel(chosen).fit(days, loads, date.fromisoformat(PROTOCOL["planner_fit_end"]))
            calibration = planner_eval(model, days, loads, date.fromisoformat(PROTOCOL["planner_calibration_start"]),
                                       date.fromisoformat(PROTOCOL["planner_calibration_end_exclusive"]), length)
            radii = calibrate_week(calibration)
            test_rows = planner_eval(model, days, loads, date.fromisoformat(PROTOCOL["holdout_start"]),
                                     date.fromisoformat(PROTOCOL["holdout_end_exclusive"]), length)
            week_hits = {}
            for row in test_rows:
                row["upper95_daily"] = min(length, row["point"] + radii["daily_radius"])
                row["upper95_week"] = min(length, row["point"] + radii["weekly_radius"])
                week_hits.setdefault(row["week"], []).append(row["actual"] <= row["upper95_week"])
            hits = sum(row["actual"] <= row["upper95_daily"] for row in test_rows)
            comparator = {}
            for name in choice["shifts"][key]["validation_mae"]:
                alt = model if name == chosen else PlannerModel(name).fit(days, loads, date.fromisoformat(PROTOCOL["planner_fit_end"]))
                rs = planner_eval(alt, days, loads, date.fromisoformat(PROTOCOL["holdout_start"]),
                                  date.fromisoformat(PROTOCOL["holdout_end_exclusive"]), length)
                comparator[name] = float(np.mean([abs(r["actual"]-r["point"]) for r in rs]))
            shift_report[key] = {"model": chosen, "mae": comparator[chosen], "baseline_mae": comparator,
                                 "coverage95_daily": hits/len(test_rows), "coverage95_daily_ci": coverage_interval(hits, len(test_rows)),
                                 "coverage95_week": np.mean([all(v) for v in week_hits.values()]),
                                 "test_days": len(test_rows), "test_weeks": len(week_hits), "calibration": radii,
                                 "rows": test_rows}
            # Kyiv has a complete daytime window on Oct 12; volunteer snapshots stop in the morning.
            origin_index = real_length-1 if region == "Kyiv City" else real_length-2
            prediction = model.predict_week(days, loads, origin_index, length)
            for h, point in enumerate(prediction, 1):
                forecast_rows.append({"region": region, "shift": key, "date": days[origin_index+h].isoformat(),
                                      "horizon": h, "point": float(point), "upper95_daily": min(length, point+radii["daily_radius"]),
                                      "upper95_week": min(length, point+radii["weekly_radius"]), "length": length,
                                      "origin_date": days[origin_index].isoformat(), "model": chosen,
                                      "secondary": region != "Kyiv City"})
            for i in range(max(0, real_length-90), real_length-1):
                histories.append({"region": region, "shift": key, "date": days[i].isoformat(), "minutes": float(loads[i])})
        recent = [a for a in alerts if a.end is not None and a.start >= start]
        for a in recent:
            replay_rows.append({"region": region, "id": a.id, "start": a.start, "end": a.end,
                                "duration": a.duration, "level": a.level, "causes": ", ".join(a.causes)})
        report[region] = {"duration_model": choice["duration"], "duration": baselines,
                          "duration_slices": {s: duration_summary([r for r in selected_rows if
                             (r["night"] if s == "night" else not r["night"])]) for s in ["day", "night"]},
                          "level_counts_holdout": {level: sum(r["level"] == level for r in selected_rows) for level in ["yellow", "red", "unknown"]},
                          "planner": shift_report,
                          "latest_event": datetime.fromtimestamp(max(a.start for a in alerts), KYIV).isoformat(),
                          "completed_episodes": sum(a.end is not None for a in alerts)}
    write(ROOT / "reports/holdout.json", {"protocol": PROTOCOL, "regions": report})
    source = {"provider": "Kyiv Digital and eTryvoga volunteer archive", "files": list(selection["fingerprint"]),
              "links": [{"label": "Київ: офіційні дані", "url": "https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a"},
                        {"label": "Історія Київ Цифровий", "url": "https://kyiv.digital/open-api/air-alert/history"},
                        {"label": "Волонтерський архів областей", "url": "https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset"}],
              "evidenceFlow": [{"title": "Raw snapshots", "detail": "Immutable JSON/CSV snapshots and SHA-256 manifests in repository."},
                               {"title": "Python analysis", "detail": "python -m air_alerts.pipeline select; freeze selection in Git; python -m air_alerts.pipeline evaluate"}],
              "limitations": [audit["geography"], audit["coverage_assumption"], "95% is nominal under calibration assumptions, not a guaranteed conditional or safety probability."]}
    metric_rows = []
    for region, r in report.items():
        for model, summary in r["duration"].items():
            metric_rows.append({"region": region, "task": "duration", "model": model, "selected": model == r["duration_model"], **summary})
        for shift, rs in r["planner"].items():
            for model, mae in rs["baseline_mae"].items():
                metric_rows.append({"region": region, "task": "planner", "shift": shift, "model": model,
                                    "selected": model == rs["model"], "mae": mae})
    queries = {"duration_models": {"rows": duration_models, "payloadColumns": ["model"], "source": source},
               "weekly_forecasts": {"rows": forecast_rows, "source": source},
               "history": {"rows": histories, "source": source}, "replay": {"rows": replay_rows, "source": source},
               "metrics": {"rows": metric_rows, "source": source}}
    current = json.loads((ROOT / "dashboard/src/data.json").read_text())
    snapshot = {"id": current["id"], "surface": "dashboard", "title": "Тривоги · прогноз і планування",
                "status": "reviewed", "buildStatus": "creating", "generatedAt": datetime.fromtimestamp(snapshot_time).astimezone().isoformat(),
                "filters": [], "queries": queries, "analysis": clean(report), "protocol": PROTOCOL,
                "sourcePreview": explicit_preview(), "forecastAsOf": datetime.fromtimestamp(snapshot_time, KYIV).isoformat()}
    write(ROOT / "dashboard/src/data.json", snapshot)
    print("Holdout and dashboard data written.", flush=True)


def explicit_preview():
    rows = json.loads((SNAPSHOT / "kyiv_official_alert_intervals.json").read_text())
    return [{"start": r["dateTimeStart"], "end": r["dateTimeEnd"], "level": r["level"], "cause": r["cause"]} for r in rows[-5:]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["select", "evaluate"])
    args = parser.parse_args()
    (select if args.phase == "select" else evaluate)()
