---
name: drive-efficiency-coach
description: Analyze recent driving sessions for energy efficiency (Wh/km), identify high-consumption outliers, and suggest concrete habits to improve range.
---

# Drive Efficiency Coach

## When to use

Activate this skill when the user asks anything along the lines of:

- "Am I driving efficiently?"
- "Why does my range vary so much?"
- "How can I improve my Wh/km?"
- "Was my last trip efficient?"
- "Show me my efficiency over the last month."

If the user only asks for a charge cost summary or battery health, prefer
the `charge_review` or `battery_health_report` MCP prompts instead.

## Prerequisites

You need a TeslaMate `car_id`. If unknown:
1. Call `teslamate_get_cars` to list available cars.
2. If exactly one is returned, use it silently.
3. If multiple, ask the user which one before continuing.

## Workflow

### 1. Pull the dataset

Call `teslamate_get_car_drives` with:
- `car_id`: target car
- `start_date`: 30 days ago in RFC3339 (e.g. `2026-04-06T00:00:00Z`)
- `end_date`: now in RFC3339
- `min_distance`: 5 (filters out parking-lot moves where Wh/km is meaningless)

If the user specifies a different period (e.g. "this year", "last week"),
use that instead. Always pass both `start_date` and `end_date` since the
TeslaMate API filters by date only — no `limit`/`offset` are accepted.

### 2. Compute per-drive efficiency

For each drive in the response:
- Distance: prefer the field expressed in km. If TeslaMate is configured
  for miles, convert (1 mi = 1.609 km).
- Energy used: derive from whichever field is present —
  typically `consumption_kwh`, or `start_ideal_range_km - end_ideal_range_km`
  multiplied by the car's nominal Wh/km, or `start_battery_level - end_battery_level`
  multiplied by usable pack capacity. Use whichever yields the cleanest
  number; document the source in the answer.
- `wh_per_km = energy_used_wh / distance_km`
- Skip drives where `distance_km < 5` or `energy_used_wh <= 0`.

### 3. Establish a baseline

From the cleaned set of drives:
- median Wh/km → user's normal
- p75 Wh/km → "above normal"
- p90 Wh/km → "outlier"
- best drive (lowest Wh/km on a meaningful distance, ≥ 20 km)

### 4. Identify outliers

Flag drives with `wh_per_km > p90`. For each, surface:
- date and time
- distance
- duration (min)
- average speed (`distance / duration`)
- Wh/km
- outside temperature if exposed
- start/end SoC if useful

### 5. Cross-reference patterns

Group outliers by:
- **Speed band** derived from average speed:
  - city: < 50 km/h
  - mixed: 50–90 km/h
  - highway: > 90 km/h
- **Temperature** (if available): cold (< 5°C), mild (5–25°C), hot (> 25°C)
- **Trip length**: short (< 15 km), medium (15–60), long (> 60)

### 6. Coach

Pick the 1–3 most actionable insights, written as direct advice:
- "Highway drives above 110 km/h average ~X% more Wh/km than your baseline.
  Cruising at 100–110 saves a meaningful chunk."
- "Cold mornings push your consumption up by ~X%. Precondition while
  plugged in to recover most of it."
- "Short trips under 10 km show high Wh/km because cabin warm-up isn't
  amortized — combine errands when you can."

Avoid generic platitudes. Anchor each insight in a concrete number derived
from the user's own data.

### 7. Render (when asked)

If the user asks for a "report", "visual", "chart", or similar, call
`generative_generate_prefab_ui` with Python code that produces:

- A `Heading` with the period.
- Three `Metric` cards: median Wh/km, best Wh/km, worst Wh/km.
- A `DataTable` of the top 5 outliers (date, distance, Wh/km, avg speed).
- A `Text` block with the 1–3 coaching insights you derived.

Pass the computed numbers via the `data=` argument so they're available
as globals in the sandbox.

If the user just asked a conversational question, return a plain text
answer instead — don't render UI unsolicited.

## Pitfalls

- **Short drives mislead.** Drives < 5 km are dominated by climate/start-up
  energy, not driving style. Always filter them out before computing
  baselines.
- **Energy data is sometimes missing.** TeslaMate has gaps. Skip drives
  with missing energy rather than imputing zeros.
- **Units vary per TeslaMate install.** Default to km, but if distances
  look suspicious (e.g. all values < 5 for normal commutes), inspect a
  sample drive's units field and convert.
- **Don't compare across very different periods.** A "winter month vs
  summer month" comparison needs explicit framing — temperature alone
  swings Wh/km by 20–30%.
