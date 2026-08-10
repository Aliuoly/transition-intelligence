# Master Plan: Transition Intelligence Demo

## Outcome

Deliver a projected-light Streamlit demo showing an agent retrieve, inspect, and compare historical polyethylene transitions before proposing an evidence-based recipe/SOP change. Stage 1 selected the fallback `2210 ↔ 1630` pair because it demonstrates both pressure predispositions clearly:

- `2210 → 1630`: lower density requires more comonomer and higher MFR requires more hydrogen, so both additions consume pressure headroom and can push total pressure toward its high limit.
- `1630 → 2210`: higher density and lower MFR require reducing both comonomer and hydrogen; aggressive removal/venting can erode low-pressure margin.

Generate three historical instances per direction in one continuous simulated campaign. Nitrogen remains on PI pressure control with a `50–200 kg/h` output range throughout every visible capsule; poison feed follows a bounded Ornstein–Uhlenbeck path while PDS discharge efficiency stays fixed at `80%`; and a demo-only vent controller opens on excess-hydrogen demand or at the high-pressure limit while inhibiting venting at `low limit + 30 kPa`. Derive all events after simulation. The app ends with evidence and a directional recommendation; recipe implementation, future outcomes, annual production impact, and economics are outside the app.

Treat the recipe pair as a simulation-validated demo choice, not a fixed claim. Stage 1 must prove the visible pressure story before downstream work depends on it. The retained `2210 ↔ 1630` labels use narrowed simulated density targets of `920 ↔ 918 kg/m³`, with MFR targets of `1.0 ↔ 3.0`, so the pressure problem remains sensitive to starting-pressure staging and vent timing.

## Fixed User Experience

The opening screen contains a compact start/end recipe card to the left of a four-row timing/resin viewer; that shared top strip sits above the newest three matching trends. Suggested prompts and a free-text chat input remain on the right, with no permanent left sidebar.

Suggested prompts are “Optimize transition 2210 to 1630” and “Optimize transition 1630 to 2210.”

The default synchronized layout is a 3×3 grid with a transition rail above it:

| Row | Left plot | Center plot | Right plot |
| --- | --- | --- | --- |
| 1 | Total pressure and shaded operating range | Predicted/lab density, shaded target range, and target | Predicted/lab MFR, shaded target range, and target |
| 2 | Ethylene partial pressure and setpoint | Comonomer mole ratio and setpoint | Hydrogen mole ratio and setpoint |
| 3 | Reactor vent flow | FM2 comonomer feed | Hydrogen feed |

All runs align at recipe-switch time `t=0`. Display the final two hours of pre-switch context through two hours after the longest selected transition. Hidden nitrogen preparation ends before the visible window, so the complete displayed history uses the normal `50–200 kg/h` pressure PI.

The timing/resin viewer lists every matching run by date in newest-first order. The newest three are checked by default; at most four can be compared simultaneously. Its fixed-height viewport shows four rows and scrolls when more histories are available. Each row contains a checkbox, run date, proportionally scaled duration line, hours, and transition-resin tons; a start time is omitted because every history is aligned at zero.

## Agent Contract

Use `gpt-5.6-luna` through the OpenAI Agents SDK Runner with `reasoning.effort="xhigh"`. Load `OPENAI_API_KEY` and rely on SDK tracing for model and tool spans in OpenAI's Traces dashboard. The agent controls the visible workspace through tools, begins with visual inspection, and requests cleaned CSV only for exact numerical evidence. The agent returns exactly three distinct recommendations ranked from highest to lowest confidence. Recommendations remain directional, may include an evidence-supported range, and must be framed as recipe/SOP changes requiring engineering validation.

## Stages

1. [Generate continuous-campaign transition data](01-simulation-data.md) — complete.
2. [Build the Streamlit workspace and 3×3 trends](02-workspace-trends.md) — complete.
3. [Add the multimodal agent and UI tools](03-agent-tools.md) — complete.
4. [Integrate and rehearse the demo path](04-demo-integration.md) — complete.

Later stages consume the interfaces defined by earlier stages. Do not start production hardening or additional use cases.

## Final Acceptance

- Both suggested prompts load the correct three-transition cohort.
- The exact 3×3 layout above appears with correct relative-time alignment and lab sample timing.
- Tool activity visibly updates the run viewer and plots.
- The agent distinguishes high- versus low-pressure predisposition and cites visible evidence.
- The agent writes a chronological notable-event transcript that pairs supplied evidence with its
  own operational interpretation before making a recommendation.
- Hovering a transcript claim highlights its referenced interval and trace intersections across the
  synchronized trends. Clicking a claim pins or releases the highlight.
- The complete interaction is repeatable within seven minutes.
