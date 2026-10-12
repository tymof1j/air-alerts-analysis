# Air Alerts Analysis

Python project for analysing air-raid alerts, with an initial focus on Kyiv city's yellow/red alert levels and threat causes.

## Selected data

The initial repository includes immutable raw snapshots retrieved on **12 October 2026**:

- **Official municipal interval export:** 2,641 completed Kyiv alerts, with original administrative identifiers, start/end timestamps, level and cause fields. Explicit classifications begin on 7 September 2026: 225 yellow and 16 red alerts. Earlier levels remain unknown.
- **Kyiv Digital event history:** 5,344 start/all-clear events through 12 October 2026 at 22:10:06 Kyiv time, retaining arrays of simultaneous threat causes.
- API schema, municipal dataset catalogue and metadata recording source URLs, retrieval times, SHA-256 checksums and basic quality checks.

Raw files are in [`data/raw/snapshots/2026-10-12T191154Z/`](data/raw/snapshots/2026-10-12T191154Z/). See [source selection and limitations](data/kyiv_data_choice.md) and the [snapshot metadata](data/raw/snapshots/2026-10-12T191154Z/metadata.json).

## Original sources

- [Municipal alert dataset](https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a)
- [Municipal interval export resource](https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75)
- [Original interval JSON download](https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/download/airalerts.json)
- [Kyiv Digital history API](https://kyiv.digital/open-api/air-alert/history) — request with `Accept: application/json`
- [Kyiv Digital API documentation](https://kyiv.digital/open-api/docs/air-alert.html)
- [API schema](https://kyiv.digital/open-api/docs/air-alert.yaml)
- [Municipal catalogue API](https://data.kyivcity.gov.ua/api/action/package_show?id=bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a)

Data attribution: Kyiv Digital and Kyiv's Department of Municipal Security. The municipal resource page describes reuse under the Open Data Licence; the source's own terms govern the data.

## Prepare detailed CSVs

Requires Python 3 and only its standard library:

```bash
python3 scripts/prepare_kyiv_detailed.py data/raw/snapshots/2026-10-12T191154Z
```

This creates interval and event CSVs under `data/processed/kyiv_detailed/`, retaining explicit levels and multiple API cause labels. Generated outputs are ignored by Git.

## Interpretation limits

The selected data covers **Kyiv city**, not Kyiv oblast or all Ukraine. Source timestamps are local wall-clock values without UTC offsets. The interval export ends at 06:14:33 on 12 October; the companion event API is more recent. Episode labels do not provide a complete timeline of level changes within an alert, nor prove when each classification became available. Do not use final episode attributes as forecasting inputs without checking historical availability. Unknown classifications must not be filled in retrospectively.

This project is for analysis; official alerts and all-clear notices remain authoritative.
