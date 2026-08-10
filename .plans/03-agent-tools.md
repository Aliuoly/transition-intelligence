# Stage 3: Multimodal Agent and Tools

**Status:** Complete. Both suggested prompts passed live rehearsal with the correct cohorts, focal runs, focused trends, pressure predispositions, and engineering-reviewed recommendations. The runtime uses the OpenAI Agents SDK Runner and its native tracing.

## Goal

Let a live agent retrieve transitions, change the visible trend workspace, inspect VLM-ready plots, and request exact values when needed.

## Runtime

Use the OpenAI Agents SDK Runner with model `gpt-5.6-luna`, `reasoning={"effort": "xhigh", "summary": "auto"}`, image input, and local function tools. Load `OPENAI_API_KEY` from `.env` and allow `OPENAI_MODEL` to override the model for troubleshooting only. Keep replaying `result.to_input_list()` on every request so the demo's local history remains explicit and portable. Configure each prompt run as the `Transition Intelligence Demo` workflow and rely on SDK tracing for model and function spans.

Runner owns model turns, function invocation, tool-result replay, stopping conditions, and the eight-turn limit. The local runtime retains only the transition context, strict tool adapters, and UI-neutral stream-event translation. Streamlit consumes raw reasoning/text deltas and semantic `tool_called`/`tool_output` events chronologically.

Stream reasoning summaries and tool activity into one chronological compact `st.status` trace. Keep the status expanded and running while the agent is analyzing or using tools, including between tool calls, then mark it complete and collapse it when final-answer text begins streaming; it remains user-expandable afterward.

Append all three Markdown references in `agent/`—the transition-agent system prompt, gas-phase polyethylene process knowledge, and optimization-direction selection knowledge—verbatim to the demo-specific runtime instructions. Together they are small enough for direct prompt inclusion; do not add retrieval infrastructure unless these references grow materially.

## Tools

- `load_transitions(start_recipe, end_recipe, count=3)` filters the latest matching cohort, selects it in UI state, renders the default overview, and returns the VLM PNG plus an allowlisted summary containing only transition ID, date, start recipe, end recipe, duration, and transition resin tons. Hidden simulator context, derived classifications, outcome labels, and event records must not enter agent context.
- `summarize_transitions(transition_ids)` returns deterministic evidence derived from the visible
  histories and an explicit engineer-visible operating-envelope export: property-entry timing,
  pressure exposure, actuator saturation, requested-versus-constrained composition setpoints, and
  prior-24-hour lab-error variability. This is evidence for a recommendation, not a prediction of
  an unimplemented recipe's effect.
- `get_event_evidence(transition_ids)` returns neutral chronological observations for each selected
  history. The tool reports timing, measurements, operating-limit crossings, override states,
  controller-output saturation, property arrival, and final transition duration. The agent uses
  these observations with trend evidence and process knowledge to write the event transcript.
- `view_specific_trends(transition_ids, start_hour, end_hour, layout, highlight_id)` privately renders either the overview or pressure/ethylene/vent focus for agent inspection without changing UI state.
- `get_trend_data(transition_ids, tags, start_hour, end_hour, resample_minutes)` returns bounded, cleaned CSV whenever exact trend evidence would improve the analysis.

After an image-producing tool call, use Kaleido to render a clean PNG from the current Plotly figure and attach it as image input on the next Responses turn. This static copy exists only for model vision; the engineer continues using the interactive browser figure. Maintain conversation continuity by replaying prior messages, model outputs, tool calls, and tool results. Translate calls into a compact visible trace such as “Loaded 3 transitions,” “Focused pressure and hydrogen,” and “Checked exact duration.”

## Agent Instructions

- Use supplied histories only. Begin either standard optimization prompt by loading the cohort,
  inspecting the complete overview, and calling `summarize_transitions` plus
  `get_event_evidence`; privately inspect specific
  views and retrieve CSV evidence as useful.
- Write a compact AI-generated notable-event transcript before the recommendation. Select events
  that explain transition performance. Connect each event to its significance. Identify repeated
  event chains across comparable transitions. Do not reproduce a bare tool-generated event list.
  Add hidden transition/time evidence markers to every transcript claim so browser hover can shade
  the referenced interval and mark trace intersections across the synchronized trends.
- Compare the focal typical run with its two analogs.
- Determine whether the transition is predisposed toward high or low pressure.
- Explain the mechanism by connecting vent flow, FM2 comonomer feed, and hydrogen feed to changing gas inventory and pressure margin.
- Treat hydrogen as slowly consumed and venting as the fastest practical removal mechanism when reducing hydrogen. Do not default to delayed or staggered setpoint changes when they merely extend transition time and mixed resin.
- Treat minimum transition resin, bounded by safety, operability, constraints, and product quality, as the primary optimization objective. Prefer simultaneous stable arrival of density and MFR inside the destination ranges.
- Diagnose which property leads, whether the lagging property is hard-constrained, and whether the leading move consumes shared constraint margin. Describe rate limiting only as a ramp limit on the working setpoint of the receiving `rM2` or `rH2` concentration PID while it remains in cascade and follows the live APC request. The density and MFR targets move directly to their destination recipe values; never ramp, filter, delay, or sequence those property targets as a substitute for concentration-controller rate limiting.
- Consider guarded pre-transition property positioning inside the source-grade range, PID setpoint ramp limits, constraint-headroom staging, and other documented directions only when repeated evidence supports their mechanism. Select the strongest intervention rather than returning a menu.
- Do not ordinarily recommend sequential property moves or intermediate holds. Require comparative evidence that simultaneous movement creates more transition resin through a shared constraint or unacceptable intermediate state before raising either as an exceptional hypothesis.
- Explain that low pressure can reduce gas-density heat removal, reactant partial pressures, polymerization rate, and catalyst productivity, while potentially worsening carryover margin. Explain that excessive pressure raises absolute reactant partial pressures and that high heavy-comonomer partial pressure can increase condensation, resin softening, and stickiness propensity.
- Base recommendations on this supplied process knowledge plus cohort evidence, not on generic interpretations inferred from line direction alone.
- Return exactly three distinct recommendations ranked from highest to lowest confidence. Label each
  recommendation with its rank and confidence level.
- Cite transition IDs and trends, events, or exact metrics.
- Request CSV whenever exact values, extrema, timing, or calculations strengthen the evidence.
- Propose a directional recipe/SOP change; include a range only when the cohort supports it.
- Use prior-day lab-error variability to establish a guarded basis for property edging. Stop at a
  justified recommendation and engineer handoff; never claim effects before implementation and
  simulation or plant verification.
- Never claim autonomous control or issue a direct control command.
- Keep the final response short enough to present in about one minute.

## Agile Acceptance

Manually run both suggested prompts. Each must select the correct cohort, visibly update the workspace during tool use, and return a recommendation consistent with the plotted pressure, composition, and flow behavior. Add no structured-output schema, unrelated-question guards, eval suite, or production retry system.
