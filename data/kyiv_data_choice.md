# Detailed Kyiv dataset: source decision

Checked on 12 October 2026. For Kyiv yellow/red analysis, use the municipal
interval export as the primary explicit classification source and Kyiv Digital's
event history as its companion. Preserve both raw snapshots.

## Selected sources

- Municipal interval export: <https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75>
- Kyiv Digital history API: <https://kyiv.digital/open-api/air-alert/history>
- API documentation: <https://kyiv.digital/open-api/docs/air-alert.html>
- Municipal field descriptions: <https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a/resource/cbf3758e-031c-42b0-a477-e731cd79b261>

Raw inputs and checksums are in `raw/snapshots/2026-10-12T191154Z/`.
The export contains 2,641 completed intervals, through 12 October at 06:14:33
Kyiv local time. Explicit levels begin on 7 September 2026 at 17:39:50:
225 yellow intervals, 16 red intervals and 2,400 earlier intervals without levels.
The source's labels are retained rather than inferred from message icons.
Observed cause categories are drone danger, missile threat, ballistic threat
and massive drone threat. Massive drone threat is explicitly red in this export.

The companion API snapshot contains 5,344 events, through 12 October at 22:10:06
Kyiv local time, including the most recent alert start. All 2,641 exported starts
match an API start event exactly. The API preserves multiple simultaneous cause
labels; the export has one cause string per interval. Both representations are kept.

## Prepared files

- `processed/kyiv_detailed/kyiv_alert_intervals_detailed.csv`: all original export
  columns, explicit normalized `level_code`, and matching API cause arrays.
- `processed/kyiv_detailed/kyiv_alert_events_detailed.csv`: all historical
  start/all-clear events and their original cause arrays, including newer events
  absent from the weekly interval export.
- `processed/kyiv_detailed/metadata.json`: lineage, counts and limitations.

Rebuild from the project root:

```bash
python3 scripts/prepare_kyiv_detailed.py data/raw/snapshots/2026-10-12T191154Z
```

## Important limits

- This is Kyiv city, not Kyiv oblast or all Ukraine.
- Before explicit classifications begin, levels remain `unknown`. The literal
  source string `null` is preserved in original columns.
- Source timestamps omit UTC offsets. Convert with `Europe/Kyiv` and handle the
  ambiguous autumn daylight-saving hour explicitly when building model inputs.
- These records do not establish a complete timeline of yellow/red changes
  within an ongoing alert. An episode attribute is not a timestamped phase.
- Historical cause lists and episode labels are not proven to be the values
  available at the alert's start. Audit availability before using them as forecast
  inputs; do not backfill later knowledge into earlier predictions.
- Only 16 explicit red episodes are available in this snapshot. Report this
  sample size when evaluating a separate red-alert model.

## Alternatives

The volunteer national CSV is useful for broader historical context, but lacks
level and cause fields. It cannot answer this classification question.

Alerts.in.ua has the richer documented schema: explicit alert levels, per-threat
levels, ten threat categories, threat start timestamps and source messages,
with oblast/raion/city/hromada geography. Its history endpoint requires a personal
API token and exposes the last month. Documentation describes `threats` as
currently open threats, so it does not by itself establish a complete historical
threat-change log. No authenticated response was available in this task;
historical completeness of those fields is therefore unverified.
Documentation: <https://devs.alerts.in.ua/>.

The Kyiv HTML statistics page uses a red icon for recent events explicitly
labelled yellow in the municipal export. Do not derive levels from those icons.
