# Stage 1 Handoff: Simulation Data

## Status

Stage 1 is accepted and frozen for the demo. The six histories were generated from one continuous 156-hour ModularSimulator campaign using isolated commit `da3ec63`; the user's simulator checkout was not modified. Runtime UI code must consume the static exports and must not invoke the simulator.

Validation at handoff:

- `uv run pytest -q`: 6 passed.
- `uv run ruff check .`: passed.
- All six native diagnostic trends were regenerated in `assets/`.

## Locked Simulation Contract

- Cohorts: TR-01/TR-03/TR-05 are `2210 → 1630`; TR-02/TR-04/TR-06 are `1630 → 2210`.
- Synthetic recipe targets retain the sales-demo labels: 2210 is density `920 kg/m³`, MFR `1.0`; 1630 is density `918 kg/m³`, MFR `3.0`.
- Pressure limits are `2100–2300 kPa`. Seeded starting-pressure targets span `2130–2270 kPa`.
- Every exported capsule starts at `−2 h`. Hidden manual nitrogen preparation ends 2.25 hours earlier, so all visible nitrogen history uses the normal `50–200 kg/h` PI controller.
- Hydrogen feed is limited to `20 kg/h`. Both composition and property loops remain at their highest native cascade levels.
- Vent flow is mass flow, limited to `1000 kg/h`, and converted internally with the ideal-gas law. Demand comes from rH2 error above `0.05` or pressure at `2300 kPa`; low-pressure inhibition closes it at `2130 kPa` and reopens at `2140 kPa`.
- PDS discharge efficiency is constant at `80%` and is not a disturbance.
- Poison is a continuous, bounded OU disturbance with two-hour mean reversion, `40–220 g/h` context means, and a `0–300 g/h` bound.
- Catalyst type-1 site fraction changes between hidden contexts within `45–55%`; type 2 is the complement.
- pM1, rM2, and rH2 are analyzer-derived and retain the native `1%` analyzer noise. Lab density and MFR remain sparse and sample-time aligned.

## Validated Demo Evidence

| Run | Direction | Start kPa | Min kPa | Max kPa | Actual vent | On-spec h |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TR-01 | 2210 → 1630 | 2131 | 2118 | 2230 | 0 min | 5.57 |
| TR-03 | 2210 → 1630 | 2161 | 2148 | 2259 | 0 min | 5.60 |
| TR-05 | 2210 → 1630 | 2263 | 2260 | 2302 | 76 min | 5.83 |
| TR-02 | 1630 → 2210 | 2154 | 2070 | 2155 | 6 min | 9.17 |
| TR-04 | 1630 → 2210 | 2254 | 2106 | 2254 | 68 min | 8.53 |
| TR-06 | 1630 → 2210 | 2127 | 2058 | 2137 | 0 min | 9.37 |

The high-side story is pressure staging: TR-01 and TR-03 remain below the high limit without venting, while high-start TR-05 crosses 2300 kPa and vents. The low-side story is usable gas inventory: high-start TR-04 can vent hydrogen materially and remain above the low limit, while lower-start TR-02 rapidly loses margin and TR-06 is pressure-inhibited from venting.

Recommended Stage 2 focal runs:

- TR-05 for the `2210 → 1630` prompt.
- TR-04 for the `1630 → 2210` prompt.

## Static Exports

- `data/transitions.csv`: 48 plotting/evidence columns at two-minute resolution.
- `data/transition_metadata.json`: one summary record per run, including baseline, duration, perturbations, predisposition, and outcome.
- `data/events.json`: transition, pressure-limit, saturation, and vent intervals in relative hours.
- `data/generation_args.json`: reproducible campaign arguments.
- `assets/TR-01_native_trends.png` through `TR-06_native_trends.png`: diagnostic review figures only.

Stage 2 should use the static CSV/JSON interfaces as-is. The default 3×3 Plotly workspace should not expose auxiliary simulator diagnostics unless the agent requests a focused layout.

## Demo-Specific Assumptions

- Grade labels are retained for narrative continuity even though their simulated density targets were narrowed to 920/918 kg/m³.
- Pressure preparation is deliberate offline scenario staging, not a recommended plant operating procedure.
- Recommendations remain engineering-reviewed recipe/SOP guidance and never write plant controller targets.
- Pressure-limit intervals can be short or fragmented at two-minute resolution; shade them sparingly rather than presenting every fragment as a separate major event.
