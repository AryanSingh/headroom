# KPI schema

KPIs support a named decision and include enough calculation detail to reproduce
the value and recognize distorted incentives. KPI records live in front matter
under a `kpis` list in an asset whose `kind` is `kpi-catalog`.

## Identifier

Use `KPI-DOMAIN-NNN`, for example `KPI-REL-001`. IDs remain stable across
editions even when thresholds change; material definition changes create a new
ID and migration note.

## Required fields

| Field | Type | Contract |
| --- | --- | --- |
| `id` | string | Globally unique KPI identifier. |
| `name` | string | Short, unambiguous metric name. |
| `decision` | string | Operational or governance decision the KPI supports. |
| `calculation` | string or mapping | Formula, units, population, exclusions, and zero-denominator behavior. |
| `source` | string or list | Authoritative systems and query/report references. |
| `frequency` | string | Collection and review cadence. |
| `owner` | string | Role accountable for definition and review. |
| `target` | number or string | Desired range with units and time window. |
| `warning` | number or string | Early-warning threshold with units and time window. |
| `distortions` | list | Known biases, blind spots, and interpretation limits. |
| `anti_gaming` | list | Countermeasures and balancing signals. |
| `interpretation` | string | Worked interpretation of a representative result. |

## Catalog front matter

```yaml
id: KPI-CATALOG-RELIABILITY
kind: kpi-catalog
kpis:
  - id: KPI-OPS-001
    name: Change failure rate
    decision: Whether release risk controls need tightening
    calculation: failed production changes divided by all production changes in 30 days
    source:
      - deployment ledger
      - incident register
    frequency: weekly collection and monthly review
    owner: Reliability lead
    target: below 10 percent over 30 days
    warning: at or above 15 percent over 30 days
    distortions:
      - inconsistent change classification
      - incidents attributed outside the review window
    anti_gaming:
      - reconcile deployment and incident ledgers
      - review alongside deployment frequency
    interpretation: A rising rate with stable volume triggers release-process review.
```

## Calculation discipline

Catalog authors state numerator, denominator, time window, units, missing-data
behavior, and inclusion rules. Scorecards preserve the raw value and source
timestamp; presentation rounding does not alter gate calculations.
