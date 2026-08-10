# Stage 2: Workspace and Trend Experience

**Status:** Complete. Stage 1 data and interfaces remain frozen in [the handoff notes](01-stage-handoff.md).

## Goal

Build the industrial time-series workspace that the agent can manipulate during the demo.

## Implementation

- Use Streamlit wide mode with custom CSS, a projected-light palette, and the label **Transition Intelligence**.
- Main column: a compact start/end recipe card to the left of a four-row scrollable timing/resin viewer, with both above the synchronized 3×3 layout. Default to the newest three matching runs and cap active comparisons at four.
- Right column: an agent pane with the two suggested prompts before the first turn, persistent chat history, and a free-text input for initial and follow-up questions.
- Use consistent transition colors across every subplot and metadata row. Emphasize the focal/typical run; render peers with lower opacity.
- Use relative hours. Compute the visible domain dynamically as `−2 h` to `max(selected transition end) + 2 h`.
- Each run-viewer row contains a checkbox, run date, proportionally scaled colored duration line, transition hours, and integrated transition-resin production in metric tons. Omit the start label because every history begins at relative hour zero.
- Use the run-viewer checkboxes as the only run-level visibility controls. Unchecking a run removes it across every subplot; checking it restores the comparison.
- Give vent flow, FM2 comonomer feed, and hydrogen feed dedicated bottom-row subplots so flow scales never compete with pressure or property signals.
- Show the explicit actuator limit on each flow subplot and shade intervals at or above 98% of that
  limit with pale red background coverage. Do not apply actuator-saturation shading to non-flow lanes.
- Render pressure and property specification envelopes as translucent bands rather than pairs of dashed limit lines; retain the property target lines. Plot both the live APC-requested and constrained working setpoint for each composition controller. The `−2 h` property context uses the source-grade density and MFR target ranges, switching to the destination-grade ranges at `t=0`.
- Plot lab density and MFR at sample time. Use the term **MFR (melt flow rate)** everywhere; do not display “melt index.”
- Provide a focused pressure/ethylene/vent layout, but keep the 3×3 overview as the default.
- Keep the visible Plotly figure fully interactive. Default drag behavior is rectangular zoom; retain modebar controls for zoom, pan, autoscale, and reset. Enable scroll-wheel zoom.
- Use unified x-axis hover so the cursor shows relative hour and values from aligned traces. Include transition ID, tag name, value, and unit in hover labels.
- Put a compact vertical interactive legend inside each corresponding subplot so it cannot overflow narrow panels. Show only the focal transition there, plus applicable target/range references; peer transition IDs appear only in the timing-rail controls. Preserve the user’s zoom and legend state across ordinary Streamlit reruns when practical.

## Public Interface

Expose figure builders that accept selected transition IDs, focal ID, relative time window, and layout name, and return a Plotly figure. Render it in Streamlit with `config={"scrollZoom": true, "displaylogo": false, "responsive": true}` and a stable UI revision key. A separate backend renderer exports the same evidence as a simplified VLM PNG through Kaleido; Kaleido is not involved in the browser interaction.

## Stage 1 Handoff

- Read `data/transitions.csv` directly; simulation is offline and must not run from Streamlit.
- Use `transition_metadata.json` for run-viewer dates and `events.json` for duration, resin-volume context, and sparse pressure/vent interval shading.
- Default cohort mappings are `2210 → 1630`: TR-01, TR-03, TR-05; `1630 → 2210`: TR-02, TR-04, TR-06.
- Use TR-05 as the focal high-pressure run and TR-04 as the focal low-pressure/venting run. These make the staged-pressure contrast clearest while retaining both peers as evidence.
- The visible data already spans `−2 h`; do not expose hidden manual nitrogen preparation. `nitrogen_preconditioning_active` is false throughout exported capsules.
- Build the nine required lanes from pressure, pM1, vent flow, predicted/lab density, rM2, FM2 feed, predicted/lab MFR, rH2, and hydrogen feed. Auxiliary poison and nitrogen diagnostics remain Stage 1 review assets, not default workspace traces.

## Agile Acceptance

- The opening workspace loads the newest three matching histories and suggested prompts.
- Selecting runs manually renders all nine required lanes, including the complete density row and three dedicated flow plots.
- Start/end indicators remain legible for three overlaid runs.
- Hover, box zoom, pan, reset, and legend show/hide work in the visible figure.
- A 1600×1000 exported PNG has readable labels and units.
- Validate manually at presentation resolution and retain one narrow Playwright happy-path script for live-agent visual inspection; skip broad browser automation and pixel-perfect tests.
