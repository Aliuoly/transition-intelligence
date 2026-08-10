# Stage 4: Demo Integration and Rehearsal

**Status:** Complete. The low-pressure path passed a two-turn live analysis through the native OpenAI runtime in Playwright at 1920×1080, and the full 3×3 overview was visually inspected. A separate offline candidate experiment can now consume a bounded scenario file without replacing the historical app exports.

## Goal

Make the ideal sales-demo path fast, legible, and repeatable without broad hardening.

## Integration Sequence

1. Start the app with empty plots and suggested prompts.
2. Submit either “Optimize transition 2210 to 1630” or its reverse.
3. Show the agent load the latest three matching histories into the timing/resin viewer and 3×3 layout.
4. Keep the full 3×3 overview visible while the agent privately inspects focused images and cleaned CSV as useful for its analysis.
5. End on a concise finding, cited evidence, directional recipe/SOP recommendation, mechanism, and validation caution.
6. Hover an AI-generated event-transcript claim to highlight its time window and trace intersections
   across the visible trends; click the claim to pin or release the highlight.
7. Hand back to the separate simulator demonstration for recipe implementation and observed outcome.

The simulator handoff accepts an isolated `--scenario` JSON and `--output-dir`. Any ramp-rate
experiment must leave the density/MFR destination targets and APC operation unchanged, keep the
composition controllers in cascade, and apply ramp limits only to the working setpoints of the
receiving `rM2` and/or `rH2` concentration PIDs as they follow their live cascade requests.

The earlier offline candidate based on density/MFR supervisory target ramps is invalid and must not
be presented as an optimized transition. Its results do not validate concentration-controller ramp
limits. A replacement candidate requires simulator support for `rM2`/`rH2` working-setpoint rate
limits and a fresh matched comparison.

The retained `2210 → 1630` offline candidate is
`scripts/scenarios/final_optimized_2210_to_1630.json`. It applies a 2180 kPa pre-transition pressure
cap and activates a `0.020 (mol/mol)/h` ramp limit only on the `rM2` concentration PID working
setpoint when that cap is invoked. Density/MFR targets still step to the destination recipe, `rM2`
remains in cascade following the live APC request, and `rH2` remains unrestricted. Across nine
matched cases from three disturbance seeds, no case worsened materially, every active case reduced
transition resin, and the candidate eliminated high-pressure exposure and venting in the simulated
cohort. This remains simulation evidence for engineering review, not an automatic recipe deployment.

## Demo Polish

- Prewarm the app and Kaleido renderer before presenting.
- Keep data local and load it at startup.
- Stream or progressively reveal the compact tool trace so `xhigh` reasoning latency feels intentional.
- Provide a visible reset control that clears conversation, selection, and plots.
- Preserve a presenter-only reference response outside the primary UI as an emergency speaking aid; do not automatically present it as a live model answer.
- Optimize for the presentation machine and browser size rather than general responsive coverage.

## Minimal Checks

- Run one lightweight data-contract check for required columns and both directions.
- Rehearse each suggested prompt once against the live API.
- Confirm the free-text chat input accepts both an initial question and a follow-up without clearing the conversation.
- Confirm relative time range, complete row 2 density plot, sample-aligned labs, transition end markers, and correct terminology.
- Confirm no UI text implies closed-loop control or customer-specific economics.
- Stop once both happy paths fit within seven minutes. Do not add comprehensive tests, deployment automation, telemetry, or production error handling.
