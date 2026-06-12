---
name: charge-recommendations
description: Analyze recent charging sessions and return 1–3 concrete recommendations to lower cost, preserve battery, or improve charging habits.
---

# Charge Recommendations

## When to use

Activate this skill when the user asks anything along the lines of:

- "Any advice on how I charge?"
- "How can I lower my charging cost?"
- "Am I charging the right way for battery health?"
- "Give me recommendations on my charges."
- "What should I change in my charging routine?"

For a full cost summary or a deep dive on a specific session, prefer the
`charge_review` MCP prompt. For battery degradation specifically, use
`battery_health_report`.

## Prerequisites

You need a TeslaMate `car_id`. If unknown:
1. Call `teslamate_get_cars` to list available cars.
2. If exactly one is returned, use it silently.
3. If multiple, ask the user which one before continuing.

## Workflow

### 1. Pull the dataset (current + previous period)

Call `teslamate_get_car_charges` **twice**:

- **Current period** — default: 30 days ago → now (RFC3339). If the user
  specifies a different period, use that instead.
- **Previous period** — same duration, immediately preceding the current
  window. For a 30-day current window, that means days -60 → -30.

Always pass both `start_date` and `end_date`. Use `fetch_all=True` on any
window longer than ~1 month — the TeslaMate API pages at 100 entries.

Skip the previous-period call only if the user explicitly says "just this
month" / "no comparison".

### 2. Classify each session

For each charge:
- **Location**: home / supercharger / other. Use `address`, `geofence`, or
  the fast-charging flag if present. If unclear, treat unnamed sessions
  above ~50 kW peak as fast-charging.
- **kWh added** (`charge_energy_added` or equivalent).
- **Start/end SoC** (`start_battery_level`, `end_battery_level`).
- **Cost** if exposed (`cost`, currency).
- **Time bucket** from `start_date`: night (22h–06h), off-peak day,
  peak day. Adjust if the user told you their utility's windows.
- **Peak power** if available (kW).
- Skip sessions with `kwh_added <= 0` or duration < 5 min.

### 3. Compute the signals that matter

Compute the same signals on **both** periods so you can phrase recos as
deltas:

- Share of kWh by location (home % / supercharger % / other %).
- Average and max `end_battery_level` — flag if frequently ≥ 90% on
  daily charges (battery wear) or if often left near 100% for hours.
- Average and min `start_battery_level` — flag if frequently ≤ 10%
  (battery wear, slower DC charging due to taper).
- Cost per kWh by location (when cost is exposed).
- Share of home kWh charged during night vs peak windows.
- Count of supercharger sessions that started above 50% SoC (slow taper —
  expensive per kWh).

For each signal, compute the **delta vs previous period** (absolute and %
where it makes sense). Flag a habit as "improving" / "drifting" /
"stable" based on the direction. Stable = delta within ±5%.

### 4. Pick 1–3 recommendations

Surface only the most impactful ones, anchored in the user's own numbers.
**Prefer signals that drifted in the wrong direction vs the previous
period** — those are the strongest hooks because they show a habit
slipping. Examples — adapt the wording and the number to the actual data:

- "Peak-hour home charging went from X% to Y% of your kWh vs the previous
  30 days. Schedule charging to start after 22h to push that back down."
- "Your average end-of-charge SoC drifted from 85% to 92% this period.
  Lower the daily limit to 80% — calendar aging accelerates above 90%."
- "Supercharger share doubled (X% → Y%). Even occasional home AC top-ups
  would bring your cost per kWh back down from A to B."
- "Z supercharger sessions started above 50% SoC (vs N last period). DC
  fast charging tapers hard past 50% — start lower or use AC at home."
- "You dropped below 10% on N occasions (vs M previously). Repeated deep
  discharges accelerate wear; aim to plug in by 20%."

Also call out one clear improvement when you see it — positive
reinforcement keeps the user engaged: "Night-charging share went from X%
to Y% — keep it up."

Avoid generic advice. Every recommendation must reference a number
derived from this user's data.

### 5. Output format

1. **Markdown summary** (short, scannable):
   - One-line context: current period, number of sessions, total kWh,
     and the headline delta vs previous period (e.g. "+12% kWh,
     supercharger share 18% → 31%").
   - The 1–3 recommendations as a bulleted list, each one with:
     - a short headline (the change to make),
     - the data point that triggered it, **with the previous-period
       value for comparison whenever available**,
     - the expected benefit (cost, battery, or time).
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
   - `Progress` for ratios (e.g. "night-charging share").
   - `AreaChart` / `LineChart` for cost / kWh trends supporting the tip.
   - `PieChart` for breakdowns (home / supercharger / other, peak /
     off-peak, …).
   - `RadarChart` for multi-axis habit comparisons (cost, SoC range,
     night share, fast-charging share — normalised).
   - `DataTable` for the underlying sessions if useful.
   - `Badge` for verdicts ("improving", "drifting", "stable") and
     `Label` for compact captions.
   - `show_map` if you want to map home vs supercharger stops —
     addresses are in `address` / `geofence`.

   Follow the global Prefab UI conventions from the MCP server
   instructions: Dashboard outermost, discovery-first, favourite set
   when several options fit equally.

## Pitfalls

- **Cost may be missing.** TeslaMate's cost column is only populated when
  the user enters tariffs. Don't fabricate currency amounts; phrase cost
  recommendations in kWh shifted or % share instead.
- **Location heuristics are noisy.** A "home" geofence may include
  workplaces with chargers. If the dataset is small, downgrade confidence
  rather than ranking the location signal first.
- **Short windows mislead.** Under 10 sessions, skip location/time-bucket
  recommendations — too little signal. Focus on SoC habits instead.
- **Don't over-read deltas on tiny samples.** If either period has under
  10 sessions, mention the delta but downgrade its weight in the
  recommendations — small absolute counts swing percentages wildly.
- **Don't double up with `charge_review`.** This skill is recommendations
  only; if the user asked for a full review, hand off to that prompt.
