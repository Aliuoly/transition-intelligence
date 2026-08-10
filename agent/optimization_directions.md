# Knowledge — Selecting Grade-Transition Optimization Directions

Use this knowledge to choose three worthwhile transition-recipe or SOP changes from
observed historical tendencies. It is a private diagnostic framework, not a list to reproduce for
the engineer.

The primary objective is to minimize transition resin: material produced after the recipe switch
and before both destination properties are stably inside their acceptable ranges. Constraint
exposure, safety, operability, and product-quality requirements bound that objective. Do not reduce
calculated transition resin by shifting off-spec production into an uncounted pre-transition period.

## 1. Selection Mandate

The agent's job is to identify three interventions worth investigating, not to enumerate every
available intervention in the final answer.

For each candidate intervention:

1. Identify a repeated, material tendency in comparable transitions.
2. Determine the limiting mechanism and its consequence for transition resin or constraint margin.
3. Confirm that the proposed intervention acts on that mechanism.
4. Check important counter-effects and conflicting evidence.
5. Reject the intervention if the required evidence is absent.
6. Rank supported interventions from highest to lowest confidence based on evidence quality,
   repeatability, mechanism support, and materiality.

Return exactly three distinct recommendations, ranked from highest to lowest confidence. Label each
recommendation with its rank and confidence level. Never respond with a generic, unranked menu of
possibilities.

Evidence should establish more than line direction. Use transition IDs and, when possible, exact
timing, property-entry times, rates, constraint durations, extrema, feed saturation, or venting.
One run may generate a hypothesis; a recipe change normally requires a repeated tendency across
comparable runs.

## 2. Diagnose Property Arrival and the Limiting Tendency

For density and MFR (melt flow rate), determine when each property first enters and then remains in
the destination range. Compare normalized progress and time-to-range rather than raw engineering
unit slopes.

Classify the observed tendency before selecting an intervention:

- **Balanced arrival:** density and MFR become stably acceptable at approximately the same time.
- **Density leads:** density becomes acceptable materially before MFR.
- **MFR leads:** MFR becomes acceptable materially before density.
- **Constraint-limited lag:** the slower property coincides with feed/removal saturation, pressure
  override, vent inhibition, thermal limitation, or another demonstrated hard constraint.
- **Unconstrained lag:** the slower property still has unused manipulated-variable and constraint
  authority.
- **Overshoot or reversal:** a property enters its range but exits again or moves away from target.
- **Inference-limited conclusion:** property timing is uncertain because inferential and laboratory
  measurements disagree materially.

The preferred trajectory brings density and MFR into their destination ranges simultaneously. A
property that arrives early has generally moved faster than useful if the other property still
determines transition end.

## 3. Pre-Transition Property Positioning

When the source-grade operating envelope permits it, consider moving a source-grade property target
toward the edge of its acceptable range nearest the destination before the formal recipe switch.
This reduces the property distance that must be traveled while producing transition resin.

Do not target the specification limit itself. Preserve an explicit guard band for inferential-model
error, laboratory delay, ordinary process variation, and control variability. Use historical
inferential-versus-lab error and run-to-run variation to support the guard band when those data are
available. If the data cannot support a numerical value, recommend determining a conservative
engineering margin rather than inventing one.

Pre-positioning is justified only when:

- the source product remains inside its approved quality range with the guard band applied;
- the change does not merely produce uncounted off-spec material before the recorded switch;
- the resulting starting condition repeatedly reduces the remaining property distance or transition
  resin in comparable histories; and
- secondary pressure, thermal, catalyst, and operability effects are acceptable.

Pre-position both properties when both can safely move toward the destination and doing so preserves
balanced arrival. If only one can be pre-positioned, check whether it would merely make an already
leading property arrive even earlier.

### Slow the leading property

When one property repeatedly arrives well before the other, consider imposing a slower setpoint ramp
limit on the concentration PID associated with the leading property. This is especially valuable
when the leading move consumes shared constraint margin needed by the lagging property.

Example: if density repeatedly reaches its destination well before MFR while increasing both
comonomer and hydrogen drives pressure upward, impose slower setpoint ramping to the comonomer-ratio
PID. The density trajectory should better match the hard-limited MFR trajectory while reducing early
gas addition and preserving pressure headroom. The evidence must show that density leads, MFR sets
transition end, and pressure or another shared constraint is materially affected.

Slowing a leading property is not beneficial merely because it is fast. It should either preserve
scarce constraint authority, reduce overshoot or undesirable resin exposure, or improve simultaneous
arrival without delaying the limiting property.

### Accelerate the lagging property only when authority exists

Consider a faster PID setpoint ramp for the lagging property only when the histories show unused
feed/removal capacity and adequate pressure, thermal, and equipment margin. Do not claim that a ramp
change can overcome a hard feed limit, maximum practical removal rate, vent inhibition, controller
saturation, or another active constraint.

If the lag is hard-constrained, optimize the leading property or the demonstrated constraint
mechanism instead.

### Control overshoot or reversal

When an aggressive composition move repeatedly causes property overshoot, range exit, or reversal
that extends transition end, consider a more conservative PID setpoint ramp. Do not recommend a
slower ramp for small harmless overshoot that does not affect transition resin or constraints.

## 5. Stage Constraint Headroom Before the Transition

Consider changing an approved pre-transition operating target when the starting condition repeatedly
determines whether the upcoming move encounters a constraint. Examples include:

- lower starting total pressure before net gas addition, subject to cooling, fluidization, reactant
  partial-pressure, catalyst-productivity, and carryover requirements;
- greater usable pressure inventory before aggressive component removal or venting, subject to high
  pressure, condensation, resin-softening, and equipment limits;
- additional thermal or cooling margin before a heat-load increase;
- production-rate or inventory positioning when a demonstrated production, cooling, withdrawal, or
  turnover limit controls transition duration; and
- positioning away from a known compressor, recycle, feed-system, dew-point, temperature, or other
  equipment constraint.

Only recommend a particular headroom change when the relevant signal or site knowledge demonstrates
the mechanism. If a likely constraint is not present in the available data, recommend collecting or
reviewing that evidence instead of asserting it caused the transition.

Never recommend operating at a constraint boundary. Preserve appropriate engineering margin.

## 6. Reduce Demonstrated Constraint Conflict

A transition can waste manipulated-variable authority when one action opposes another. Examples
include adding a gas component while pressure control vents it, or requesting removal while a
low-pressure inhibit prevents venting.

Potential recipe or SOP responses include:

- pre-transition headroom staging;
- slowing an already-leading property through its PID setpoint ramp limit;
- changing an approved production or pressure target; or
- investigating whether the relevant control strategy or equipment capacity should be improved.

Choose among them from the evidence. Do not recommend bypassing an override, relaxing a safety or
equipment limit, or directly commanding a valve.

## 7. Production Rate and Inventory Turnover

Consider production-rate changes only when historical evidence shows that they improve the limiting
mechanism. A lower rate may release cooling or equipment margin but can slow inventory turnover. A
higher rate may displace old-grade inventory faster but increase heat load and consume constraint
margin. Evaluate the net effect on transition resin, not transition clock time alone.

Consider bed mass, product withdrawal, and inventory state when those data are available and show a
repeatable effect. Do not invent an inventory recommendation from property lag alone.

## 8. Inferential Models and Measurement Uncertainty

When inferred properties and laboratory measurements show a repeated transition-specific bias,
distinguish a real trajectory problem from a measurement/model problem.

Supported responses may include:

- improving the inferential model;
- adding transition-specific model treatment;
- increasing the pre-positioning guard band; or
- applying a bounded temporary supervisory bias only when repeated evidence quantifies the bias and
  expert review supports compensation.

Do not tune a recipe to cancel a one-off model error. Do not use an inferred early arrival as the
basis for slowing a property when laboratory evidence contradicts it.

## 9. General Constraints Beyond the Visible Demo Trends

The same reasoning applies to pressure, temperature, cooling duty, dew-point or condensation margin,
fluidization, recycle/compressor capacity, catalyst or production limits, feed delivery, removal or
vent capacity, product withdrawal, emissions, and equipment limits.

These are candidate mechanisms, not automatic recommendations. Name one only when it is supported by
available trends, events, site-specific expert knowledge, or an explicit data request. The absence of
a signal is not evidence that the corresponding constraint was active.

## 10. Directions That Require Exceptional Evidence

Do not ordinarily recommend sequential property moves, deliberate delays, or intermediate holds.
For independent property responses, simultaneous movement finishes in the longer response time;
sequential movement increases transition-resin production.

Such a strategy is worth investigating only if comparative evidence shows that simultaneous movement
activates a shared constraint or creates an unacceptable intermediate resin/operability state so
severely that it produces more transition resin than the alternative. State this exceptional evidence
explicitly. Otherwise reject the strategy.

Also reject:

- arbitrary target biases;
- faster ramps against an active hard constraint;
- moving a source property to its exact specification limit;
- pre-positioning that creates off-spec source resin;
- changes that merely improve one property while delaying simultaneous arrival;
- direct valve commands or autonomous control changes;
- bypassing or weakening constraints; and
- a final answer that lists all possible optimization directions without selecting one.

## 11. Recommendation Decision Order

Use this order when analyzing a cohort:

1. Establish stable destination-range entry times for density and MFR.
2. Identify the leading property and the transition-ending property.
3. Determine whether the laggard is hard-constrained or has unused authority.
4. Identify shared constraint consumption or opposing control action.
5. Check whether safe, guarded pre-positioning could reduce the required property travel.
6. Rank candidate interventions by how directly they address the demonstrated mechanism and by
   their compatibility with the visible constraints; do not predict an outcome before implementation.
7. Select the three strongest distinct interventions and rank them from highest to lowest confidence.
8. Hand each recommendation to the engineer with what should be validated and what result would
   falsify the proposed mechanism. Do not present an unimplemented effect as known.

If fewer than three recipe changes pass this evidence gate, use the remaining ranked positions for
specific data-collection or validation recommendations. State why the histories do not yet justify a
recipe change in those positions.
