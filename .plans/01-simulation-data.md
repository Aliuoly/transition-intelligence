# Stage 1: Continuous-Campaign Simulation Data

**Status:** Complete and accepted. See [Stage 1 handoff notes](01-stage-handoff.md).

## Goal

Produce six non-identical, simulator-derived historical transitions without relying on checkpoint reload or repeated zero-rate startups.

## Implementation

- Export ModularSimulator commit `da3ec63` into an ignored cache directory and run it in an isolated environment. Leave the current checkout untouched.
- Start once from the model’s initial state, stabilize at Grade 2210, then run three alternating cycles of `2210 → 1630 → 2210`.
- Define 2210 as density `920 kg/m³`, MFR `1.0`; define 1630 as density `918 kg/m³`, MFR `3.0`.
- In `2210 → 1630`, command increases in both comonomer and hydrogen ratio so the cohort demonstrates high-pressure susceptibility.
- In `1630 → 2210`, command reductions in both ratios and schedule maximum vent demand during the hydrogen-removal portion so the cohort demonstrates low-pressure susceptibility.
- Keep nitrogen on PI pressure control with its manipulated output constrained to `50–200 kg/h`.
- Before each transition, temporarily place nitrogen in manual and drive toward a seeded random pressure target spanning the `2130–2270 kPa` range. Capture the current nitrogen rate as the manual schedule's bias and trim it from actual pressure error, temporarily widening the actuator range to `0–3000 kg/h`. End manual preparation 2.25 hours before the recipe switch, move the nitrogen PI setpoint to the selected pressure target, restore the actuator range, and return nitrogen bumplessly to its `50–200 kg/h` PI controller. Thus the entire exported `−2 h` window uses the same automatic nitrogen control as the transition. Use actual reactor pressure for the target and all safety logic.
- Hold PDS discharge efficiency constant at `0.80`. Do not use PDS randomness or mean changes as a campaign disturbance; this keeps the pressure/vent story attributable to staged starting pressure and visible vent action.
- Drive the native poison feed with a seeded, bounded Ornstein–Uhlenbeck process using a two-hour time constant. Use means of `40–220 g/h` with a `0–300 g/h` bound so the native kinetics and catalyst/production cascade show a visible response. Change its mean between transitions and retain the continuous realized trajectory.
- At the same hidden context changes, assign a seeded catalyst type-1 site fraction between `0.45` and `0.55` (with type 2 taking the complement). Export the active split as evidence; do not expose it as a manipulated recipe target.
- Preserve the native gas-analyzer noise (`1%` coefficient of variation on yM1, yM2, and yH2) and export analyzer-derived pM1, rM2, and rH2 rather than their noise-free process-state equivalents.
- Add one demo-specific pressure-protected controller for `F_vent`. Request `1000 kg/h` automatically when excess-hydrogen control error `(actual rH2 − rH2 SP)` exceeds `0.05`, or whenever total pressure reaches the high limit; otherwise request zero. Reset the high-pressure override `10 kPa` below the high limit. Convert mass flow to volumetric loss with the ideal-gas law and current mixture molecular weight. Force the vent closed at `low limit + 30 kPa` and permit reopening after another `10 kPa` of recovery.
- Run every native feed and property controller at its highest available cascade level. Retain native tuning except for setting both rM2 and rH2 integral times to 25 minutes and increasing their I–P proportional damping to Kp `10000` and `600`, respectively.
- Apply the destination density and MFR recipe setpoints directly at `t=0` for every transition. Do not inject transition-specific setpoint timing as a source of cohort variation.
- Constrain the hydrogen-feed actuator to `0–20 kg/h`; use the same configured limit when deriving saturation intervals.
- Set `t=0` from the recipe-switch event. Transition end is the first point at which predicted density and MFR remain inside the destination recipe limits for 30 continuous minutes.
- Preserve lab samples at their sample timestamp rather than result-availability timestamp.
- Space transitions far enough apart to export a full 24-hour pre-transition lab baseline for every
  run. Use visibly meaningful, seeded lab error and retain each sample's inferential-minus-lab error
  for guard-band analysis.
- Record raw continuous histories only during simulation. Derive transition capsules, pressure-limit intervals, saturation, venting, on-spec entry, and summary metrics afterward in the demo repository’s post-processing step.

## Output Contract

Write:

- `data/transitions.csv`: one row per sample with transition ID, relative hour, direction, pressure/limits, ethylene partial pressure/SP, predicted and lab density, density target/limits, comonomer ratio/SP, predicted and lab MFR, MFR target/limits, hydrogen ratio/SP, feeds, venting, and useful controller outputs.
- `data/transition_metadata.json`: dates, recipes, baseline conditions, perturbations, duration, predisposition, and outcome label.
- `data/events.json`: post-processed transition start/end, pressure-limit intervals, sustained saturation, venting, and estimated on-spec entry.
- `data/generation_args.json`: only the arguments needed to reproduce or retune the campaign; do not maintain commit, unit, or seed provenance.
- `data/pretransition_lab_samples.csv`: the prior 24 hours of sparse inferred and lab properties plus
  signed errors for each transition.
- `data/operating_limits.json`: the engineer-visible pressure and vent, comonomer-feed, and
  hydrogen-feed actuator envelopes used consistently by plots and summaries.

## Agile Acceptance

- Exactly three transitions exist in each direction.
- Baseline values and durations are not identical across a cohort.
- `2210 → 1630` visibly approaches or exceeds the high-pressure limit, while `1630 → 2210` visibly approaches the low-pressure limit.
- Required plotting columns are populated. Visual inspection is sufficient; do not add simulator regression coverage.

## Recipe-Pair Decision

The campaign retains the `2210 ↔ 1630` labels for downstream UI and agent copy, but narrows their simulated density targets to `920 ↔ 918 kg/m³`. This smaller density move avoids making the pressure response a foregone conclusion and leaves starting-pressure staging and vent timing visible in the comparison. Acceptance is based on inspection of the completed continuous campaign.
