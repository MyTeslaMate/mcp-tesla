---
name: drive-recommendations
description: Analyze recent drives and return 1–3 concrete recommendations to improve efficiency, range, or driving habits.
---

# Drive Recommendations

## When to use

Activate this skill when the user asks anything along the lines of:

- "Any advice on how I drive?"
- "How can I get more range?"
- "Give me recommendations on my drives."
- "What should I change in my driving habits?"
- "Tell me one thing to improve in how I drive."

If the user wants a full breakdown (median Wh/km, outliers list, baseline
analysis) instead of focused advice, prefer the `drive-efficiency-coach`
skill.

## Prerequisites

You need a TeslaMate `car_id`. If unknown:
1. Call `teslamate_get_cars` to list available cars.
2. If exactly one is returned, use it silently.
3. If multiple, ask the user which one before continuing.

## Workflow

### 1. Pull the dataset (current + previous period)

Call `teslamate_get_car_drives` **twice**:

- **Current period** — default: 30 days ago → now (RFC3339). If the user
  specifies a different period, use that instead.
- **Previous period** — same duration, immediately preceding the current
  window. For a 30-day current window, that means days -60 → -30.

Both calls use:
- `car_id`: target car
- `min_distance`: 5 (filters out parking-lot moves where Wh/km is meaningless)
- `fetch_all`: `True` whenever the window is longer than ~1 month — the
  TeslaMate API pages at 100 entries.

Always pass both `start_date` and `end_date`. Skip the previous-period
call only if the user explicitly says "just this month" / "no comparison".

### 2. Compute per-drive signals

For each drive:
- **Distance** in km (convert from miles if TeslaMate is configured that way).
- **Energy used**, from whichever field is present (`consumption_kwh`,
  range delta × nominal Wh/km, or SoC delta × usable pack capacity).
- `wh_per_km = energy_used_wh / distance_km`
- `avg_speed_kmh = distance_km / (duration_min / 60)`
- **Speed band**: city (< 50 km/h), mixed (50–90), highway (> 90).
- **Trip length**: short (< 15 km), medium (15–60), long (> 60).
- **Outside temperature** if exposed.
- Skip drives where `distance_km < 5` or `energy_used_wh <= 0`.

### 3. Compute the signals that matter

Compute the same signals on **both** periods so you can phrase recos as
deltas:

- Median Wh/km (the user's baseline).
- Wh/km by speed band — flag any band that is ≥ 15% above the baseline.
- Wh/km by trip length — flag short trips if they consume ≥ 20% more
  than medium trips (climate warm-up not amortized).
- Wh/km by temperature bucket if data is rich enough — flag cold drives
  (< 5°C) that exceed the baseline by ≥ 20%.
- Highest single-drive Wh/km on ≥ 20 km — useful as a concrete example.

For each signal, compute the **delta vs previous period** (absolute Wh/km
and %). Flag a habit as "improving" / "drifting" / "stable" based on the
direction. Stable = delta within ±3% on Wh/km (driving is noisier than
charging — keep the band tight to avoid false positives).

Be wary of confounders before phrasing a delta as a habit change:
temperature swings (winter vs summer) or a long road-trip mixed into one
period can move Wh/km by 20–30% on their own. Mention the confounder
explicitly if you can see it in the data.

### 4. Pick 1–3 recommendations

Surface only the most impactful ones, anchored in the user's own numbers.
**Prefer signals that drifted in the wrong direction vs the previous
period** — those are the strongest hooks because they show a habit
slipping. Examples — adapt the wording and the number to the actual data:

- "Highway Wh/km drifted from X to Y vs the previous 30 days (+Z%).
  Cruising at 100–110 km/h instead of 120+ would save a meaningful chunk
  on long trips."
- "Median Wh/km went from X to Y. The biggest contributor is your
  highway band — see above."
- "Short-trip Wh/km is X% above your medium-trip baseline (similar to
  last period). Combine errands when possible — cabin warm-up isn't
  amortized on short hops."
- "Cold-weather drives (< 5°C) cost you ~X% more Wh/km this period —
  precondition while plugged in to recover most of that overhead."
- "Your worst drive of the period was X Wh/km on Y km, dragging the
  average up by Z%. One outlier drive can dominate a short window."

Also call out one clear improvement when you see it — positive
reinforcement keeps the user engaged: "Median Wh/km dropped from X to Y
— keep it up."

Avoid generic platitudes. Every recommendation must reference a number
derived from this user's data.

### 5. Output format

1. **Markdown summary** (short, scannable):
   - One-line context: current period, number of drives, total km,
     median Wh/km, and the headline delta vs previous period (e.g.
     "median 168 → 182 Wh/km, +8%").
   - The 1–3 recommendations as a bulleted list, each one with:
     - a short headline (the change to make),
     - the data point that triggered it, **with the previous-period
       value for comparison whenever available**,
     - the expected benefit (% Wh/km, km of range, or kWh saved).
   - Optional one-line positive note if a habit visibly improved.

2. **Then render the recommendations as a Prefab UI Dashboard**.
   - First call `generative_search_prefab_components` to discover the
     components currently available — newer / richer ones may exist.
   - Then call `generative_generate_prefab_ui` with a **Dashboard**
     layout (outermost) wrapping the components that best illustrate
     the recommendations. Better too many components than too few.

   Lean into whatever discovery returned, prioritising:

   - `Metric` cards for the key numbers anchoring each tip (with the
     previous-period number as a delta where you have it).
   - `Progress` for ratios (e.g. share of highway km).
   - `LineChart` / `AreaChart` for the Wh/km trend by drive, day or
     week.
   - `RadarChart` for multi-axis comparisons (efficiency vs speed band
     vs trip length vs temperature, normalised).
   - `PieChart` for breakdowns (city / mixed / highway, short / medium /
     long).
   - `DataTable` for the outlier drives worth inspecting.
   - `Badge` for verdicts ("improving", "drifting", "stable") and
     `Label` for compact captions.
   - `show_map` to map outlier drives' start/end on a map — addresses
     are in `start_address` / `end_address`.

   Follow the global Prefab UI conventions from the MCP server
   instructions: Dashboard outermost, discovery-first, favourite set
   when several options fit equally.

## Pitfalls

- **Short drives mislead.** Drives < 5 km are dominated by climate/start-up
  energy. Always filter them out before computing the baseline; they're
  only useful as the basis for the "combine short trips" recommendation.
- **Energy data is sometimes missing.** TeslaMate has gaps. Skip drives
  with missing energy rather than imputing zeros.
- **Units vary per TeslaMate install.** Default to km, but if distances
  look suspicious (e.g. all values < 5 for normal commutes), inspect a
  sample drive's units field and convert.
- **Small samples kill confidence.** Under 10 valid drives, lead with a
  single recommendation and say so explicitly — don't stretch noisy data
  into three insights.
- **Don't blame habits for temperature.** A 20% Wh/km jump between two
  30-day windows that straddle the seasonal shift is mostly weather, not
  the user's foot. If the temperature buckets shifted between periods,
  say so before phrasing the delta as a recommendation.
- **Don't double up with `drive-efficiency-coach`.** This skill is
  recommendations only; if the user asked for a full breakdown, hand off
  to that skill.
