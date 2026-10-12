"""Preserve explicit Kyiv alert levels and all API cause labels in CSV form."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def prepare(snapshot: Path, output: Path) -> dict:
    interval_path = snapshot / "kyiv_official_alert_intervals.json"
    history_path = snapshot / "kyiv_air_alert_history.json"
    intervals = json.loads(interval_path.read_text())
    events = json.loads(history_path.read_text())["items"]
    active_events = {}
    for event in events:
        if event["state"] == 1:
            key = event["created_at"].replace(" ", "T")
            if key in active_events:
                raise ValueError(f"Ambiguous API event at {key}")
            active_events[key] = event

    output.mkdir(parents=True, exist_ok=True)
    level_codes = {"Жовтий рівень": "yellow", "Червоний рівень": "red"}
    original_fields = list(intervals[0])
    added_fields = ["level_code", "history_causes_json", "history_start_matched",
                    "source_timezone", "classification_scope"]
    interval_csv = output / "kyiv_alert_intervals_detailed.csv"
    matched = 0
    with interval_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=original_fields + added_fields)
        writer.writeheader()
        for interval in sorted(intervals, key=lambda row: row["dateTimeStart"]):
            event = active_events.get(interval["dateTimeStart"])
            matched += event is not None
            writer.writerow({
                **interval,
                "level_code": level_codes.get(interval["level"], "unknown"),
                "history_causes_json": json.dumps(event.get("causes", [])) if event else "",
                "history_start_matched": event is not None,
                "source_timezone": "Europe/Kyiv",
                "classification_scope": "episode_attribute_not_level_transition_log",
            })

    event_csv = output / "kyiv_alert_events_detailed.csv"
    with event_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["created_at", "state", "causes_json",
                                                  "source_timezone"])
        writer.writeheader()
        for event in sorted(events, key=lambda row: row["created_at"]):
            writer.writerow({"created_at": event["created_at"], "state": event["state"],
                             "causes_json": json.dumps(event.get("causes", [])),
                             "source_timezone": "Europe/Kyiv"})

    summary = {
        "raw_snapshot": str(snapshot.resolve()),
        "interval_rows": len(intervals), "event_rows": len(events),
        "history_start_matches": matched,
        "explicit_levels": dict(Counter(level_codes.get(row["level"], "unknown")
                                        for row in intervals)),
        "source_checksums": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (interval_path, history_path)},
        "limitations": [
            "Kyiv city only; timestamps are local wall-clock times without offsets.",
            "Literal source null values are retained; unknown levels are not imputed.",
            "API causes are matched by exact start timestamp and retained as arrays.",
            "Episode labels do not establish when a cause or level became known.",
            "These sources do not establish a complete within-alert level-change timeline.",
            "Do not use final episode attributes as forecast inputs without an availability audit.",
            "Interval export ends earlier than the event API; no levels are invented for later events.",
        ],
    }
    (output / "metadata.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/processed/kyiv_detailed"))
    args = parser.parse_args()
    print(json.dumps(prepare(args.snapshot, args.output), indent=2))
