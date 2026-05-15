---
name: drive-efficiency-coach
description: Analyze recent driving sessions for energy efficiency (Wh/km), score each drive 0-100, identify high-consumption outliers, and render a visual coach dashboard (score, speed charts, radar, timeline, tips).
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
- `fetch_all`: `True` whenever the window is longer than ~1 month — the
  TeslaMate API returns at most 100 entries per page, and the wrapper
  will auto-paginate to give you the complete set.

If the user specifies a different period (e.g. "this year", "last week"),
use that instead. Always pass both `start_date` and `end_date`. For a
year-long window, `fetch_all=True` is mandatory or you'll undercount.

Also pull `teslamate_get_car_charges` over the same window — needed for the
timeline (Charge events) and to score the Recharge dimension.

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
- `avg_speed_kmh = distance_km / (duration_min / 60)`
- Skip drives where `distance_km < 5` or `energy_used_wh <= 0`.

### 3. Baselines (overall + per speed band)

Compute on the cleaned set:
- median Wh/km → user's normal
- p75 / p90 Wh/km → above-normal / outlier thresholds
- best drive (lowest Wh/km on ≥ 20 km)
- worst drive (highest Wh/km on ≥ 5 km)

Then bucket every drive into a **speed band** and compute median Wh/km
per band — this powers the *Consumption by speed* line chart:

| Band       | Range km/h |
|------------|------------|
| `0-25`     | < 25       |
| `25-50`    | 25–49      |
| `50-80`    | 50–79      |
| `80-110`   | 80–109     |
| `110-130`  | 110–129    |
| `130+`     | ≥ 130      |

### 4. Score each drive (0–100)

Per-drive score, used both for the timeline and to aggregate radar
dimensions:

```
ratio = wh_per_km / band_median_wh_per_km
score = clamp(round(100 - (ratio - 1) * 120), 0, 100)
```

This rewards drives that beat the band's own median (so a fast highway
drive isn't punished just for being highway), and penalises drives that
exceed it. A drive that matches the band median lands at ~88; one that
runs 25% above lands at ~58.

Letter grade for the headline:
- ≥ 90 → A · *Excellent*
- 80–89 → A- · *Very good*
- 70–79 → B+ · *Good, room to improve*
- 60–69 → B · *Decent*
- 50–59 → C · *Needs work*
- < 50 → D · *Clear room for progress*

### 5. Radar coaching — 5 dimensions

Each dimension is a 0–100 score with a one-line caption. Compute them
from the same drive set:

- **Speed** — share of distance under 115 km/h on highway-band drives.
  `score = pct_distance_under_115_on_highway`. Highway-free periods get
  the global score (don't penalise city-only weeks).
- **Smoothness** — coefficient of variation of Wh/km within each drive's
  band. Lower variance → smoother driving. `score = clamp(100 - cv*200, 0, 100)`.
- **Temperature** — gap vs mild-weather baseline. If `outside_temp_avg`
  exists, regress Wh/km on temperature; otherwise diff median Wh/km of
  cold drives (< 5°C) vs mild (10–20°C). Express as score where 0% gap
  = 100, 30% gap = 50.
- **Regen** — regen kWh / (regen kWh + brake-mechanical proxy).
  TeslaMate exposes `start_*` / `end_*` levels; use the `power` and
  `regen_*` fields if present, else infer from negative-consumption
  segments in detailed drive endpoint.
- **Payload** — efficiency vs the car's EPA / WLTP nominal. Lets
  the user see how close to spec they live. `score = clamp(100 - (median_wh_per_km / nominal_wh_per_km - 1) * 150, 0, 100)`.

If a dimension can't be computed from available data, omit its card
rather than guessing. Don't fake a score.

### 6. Coach tips

Pick the 2–4 most actionable insights, each tagged with one of these
categories and a quantified gain estimate:

- `Highway`, `Short trips`, `Charging`, `Climate`, `Regen`, `Tires / load`.

Each tip carries:
- `category` (badge text)
- `body` (1–2 sentences, direct advice)
- `gain` (e.g. `+7 to +12%`, or `less wait time`)

Anchor each tip in a number derived from the user's own data — never
generic platitudes.

### 7. Render the dashboard

Always finish with `generative_generate_prefab_ui`. Call
`generative_search_prefab_components` first if you're unsure of
signatures. Required imports:

```python
from prefab_ui.app import App
from prefab_ui.components import (
    Page, Card, CardHeader, CardContent, CardTitle, CardDescription,
    Grid, GridItem, Row, Column, Heading, H2, H3, Text, Muted, Small,
    Metric, Ring, Progress, Badge, Separator, ForEach, ITEM,
)
from prefab_ui.components.charts import LineChart, BarChart, RadarChart, ChartSeries
```

Compose the page top-to-bottom as **one** prefab call:

**A. Hero card** — `Card` with:
- `Badge` "EFFICIENCY COACH · TESLAMATE" (subtle / green tint)
- `H2` "Visual efficiency coach"
- `Muted` one-line description naming the period and car

**B. Headline metrics row** — `Grid` with 4 `Card`s:
1. **Efficiency Score** — large `score / 100`, grade badge (`B+ · Good, room to improve`), `Progress` bar. Green tint.
2. **Average consumption** — median Wh/km, caption `— recent drives`.
3. **Best drive** — best Wh/km, caption `— energy ninja`.
4. **Worst peak** — worst Wh/km, caption `— worth investigating`. Amber tint.

**C. Two side-by-side charts** in a 2-col `Grid`:
- `LineChart` *Consumption by speed* — x: speed bands, y: median
  Wh/km per band. Subtitle: *The faster you go, the harder the aero
  wall eats your electrons.*
- `BarChart` *Score by speed zone* — x: speed bands, y: average
  per-drive score in that band. Subtitle: *Sweet spot tends to sit
  between 50 and 80 km/h on this car.*

**D. Radar coaching** — `H2` "Radar coaching", then:
- Row of 5 small `Card`s (one per dimension) showing label + `score/100`
  + thin `Progress` bar. Skip cards for dimensions you couldn't compute.
- Below them, a `RadarChart` with one `ChartSeries` plotting the 5
  scores so the shape is immediately readable.

**E. Timeline + tips** — 2-col `Grid` (timeline ≈ 2× the width of tips):

*Left column* — `H2` "Smart timeline", then `ForEach` over the
last ~8 events (drives + charges merged, newest first). Per event,
render a `Card` with:
- `Badge` `"Drive · May 06"` (blue) or `"Charge · May 03"` (amber)
- `Text` route (`"Gorge de Loup → Oullins"`) or charger name
- `Muted` 1-line commentary (`"Smooth urban trip, consumption in check."`)
- Large `score/100`
- `Progress` bar tinted by score (green ≥ 80, neutral 60–79, amber < 60)

*Right column* — `H2` "Coach tips", then `ForEach` over tips.
Per tip, a `Card` with:
- `Badge` category at top
- `Text` body
- Green `Badge` at bottom: `"gain: <gain>"`.

Pass all computed numbers via the `data=` argument so they're globals in
the sandbox (`data={"score": 78, "grade_label": "B+ · Good, room to improve",
"median_wh": 184, "best_wh": 129, "worst_wh": 339, "speed_bands": [...],
"radar": [...], "timeline": [...], "tips": [...]}`). Never return a
plain-text answer — the user invoked the coach because they want the
visual report.

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
- **Don't fake radar dimensions.** If you can't compute Regen because
  the detailed drive endpoint isn't returning regen data, drop the card
  instead of inventing a score. A 4-card radar is more honest than a
  5-card one with a bogus value.
- **Highway penalty trap.** Don't score highway drives against the
  global median — they'll all look bad. Per-band scoring (step 4) is
  what keeps the timeline meaningful.
