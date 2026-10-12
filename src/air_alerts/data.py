"""Canonical intervals, exact overlap arithmetic and local-day exposure."""
import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

KYIV = ZoneInfo("Europe/Kyiv")
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data/raw/snapshots/2026-10-12T191154Z"


@dataclass
class Alert:
    id: str
    start: float
    end: float | None
    level: str = "unknown"
    causes: tuple = ()
    source: str = "kyiv_digital"

    @property
    def duration(self):
        return None if self.end is None else (self.end - self.start) / 60

    @property
    def local(self):
        return datetime.fromtimestamp(self.start, KYIV)


def stamp(value):
    dt = datetime.fromisoformat(value)
    return (dt if dt.tzinfo else dt.replace(tzinfo=KYIV)).timestamp()


def local_timestamp(value, previous=None):
    """Select the earliest UTC occurrence compatible with source ordering."""
    dt = datetime.fromisoformat(value)
    choices = sorted({dt.replace(tzinfo=KYIV, fold=f).timestamp() for f in (0, 1)})
    valid = [t for t in choices if previous is None or t >= previous]
    if not valid:
        raise ValueError(f"Non-monotone source time: {value}")
    return valid[0], len(choices) > 1


def canonical_kyiv(events, explicit):
    attrs = {x["dateTimeStart"].replace("T", " "): x for x in explicit}
    pending = None
    alerts, unpaired = [], []
    audit = Counter()
    previous = None
    for i, event in enumerate(sorted(events, key=lambda x: x["created_at"])):
        t, ambiguous = local_timestamp(event["created_at"], previous)
        previous = t
        audit["ambiguous_wall_times"] += ambiguous
        if event["state"] == 1:
            if pending:
                unpaired.append(pending)
                audit["start_without_observed_end"] += 1
            attr = attrs.get(event["created_at"], {})
            pending = Alert(f"kyiv-{i}", t, None,
                            {"Жовтий рівень": "yellow", "Червоний рівень": "red"}.get(attr.get("level"), "unknown"),
                            tuple(event.get("causes", [])))
        elif event["state"] == 0 and pending:
            if t <= pending.start:
                raise ValueError("Nonpositive interval")
            pending.end = t
            alerts.append(pending)
            pending = None
        else:
            audit["unmatched_all_clear"] += 1
    if pending:
        alerts.append(pending)
        audit["open_at_snapshot"] += 1
    audit["completed_intervals"] = sum(a.end is not None for a in alerts)
    audit["unpaired_early_starts_excluded"] = len(unpaired)
    audit["municipal_starts_matched"] = sum(a.local.strftime("%Y-%m-%d %H:%M:%S") in attrs for a in alerts)
    return alerts, dict(audit)


def load_regions():
    events = json.loads((SNAPSHOT / "kyiv_air_alert_history.json").read_text())["items"]
    explicit = json.loads((SNAPSHOT / "kyiv_official_alert_intervals.json").read_text())
    kyiv, audit = canonical_kyiv(events, explicit)
    regions = {"Kyiv City": kyiv}
    imputed = Counter()
    nonpositive = Counter()
    with (SNAPSHOT / "volunteer_data_en.csv").open() as file:
        for i, row in enumerate(csv.DictReader(file)):
            if row["region"] in ("Kyiv City", "Luhanska oblast"):
                continue
            if row["naive"] == "True":
                imputed[row["region"]] += 1
                continue
            start, end = stamp(row["started_at"]), stamp(row["finished_at"])
            if end <= start:
                nonpositive[row["region"]] += 1
                continue
            regions.setdefault(row["region"], []).append(Alert(f"volunteer-{i}", start, end, source="etryvoga"))
    audit["volunteer_imputed_ends_excluded"] = dict(imputed)
    audit["volunteer_nonpositive_intervals_excluded"] = dict(nonpositive)
    audit["geography"] = "Kyiv city has no municipal-district field. Kyiv oblast raions in the older national official CSV are not Kyiv city districts and stop in September."
    audit["coverage_assumption"] = "Closed, apparently chronological feed treated as an archive; historical ingestion uptime is unavailable. Early unpaired starts and imputed volunteer intervals are excluded, not assigned artificial ends."
    return {k: sorted(v, key=lambda a: a.start) for k, v in regions.items()}, audit


def union_intervals(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def overlap_minutes(intervals, start, end):
    return sum(max(0, min(b, end) - max(a, start)) for a, b in union_intervals(intervals)) / 60


def daily_profiles(alerts, cutoff):
    """UTC 15-minute segments mapped to local bins, preserving DST duration."""
    first = date(2023, 1, 1)
    last = datetime.fromtimestamp(cutoff, KYIV).date()
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    index = {d: i for i, d in enumerate(days)}
    profile = np.zeros((len(days), 96))
    intervals = [(a.start, min(a.end if a.end is not None else cutoff, cutoff))
                 for a in alerts if a.start < cutoff]
    for start, end in union_intervals(intervals):
        cursor = start
        while cursor < end:
            boundary = min(end, (int(cursor // 900) + 1) * 900)
            dt = datetime.fromtimestamp(cursor, KYIV)
            if dt.date() in index:
                profile[index[dt.date()], dt.hour * 4 + dt.minute // 15] += (boundary - cursor) / 60
            cursor = boundary
    return days, profile


def working_load(profile, start_hour, end_hour):
    if end_hour <= start_hour:
        raise ValueError("Workday must end after it starts")
    return profile[:, start_hour * 4:end_hour * 4].sum(axis=1)


def save_canonical():
    regions, audit = load_regions()
    output = ROOT / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    (output / "canonical.json").write_text(json.dumps({k: [asdict(a) for a in v] for k, v in regions.items()}))
    (ROOT / "reports/data_quality.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps({"regions": len(regions), **audit}, indent=2))


if __name__ == "__main__":
    save_canonical()
