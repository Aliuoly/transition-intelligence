# Repository Guidelines

## Purpose and Scope

This repository contains a fixed-scope sales demo for polyethylene grade-transition decision support. Optimize for a convincing seven-minute happy path, not production readiness. Use shortcuts, static exports, narrow assumptions, and demo-specific code when they reduce delivery time. Do not add databases, authentication, deployment infrastructure, APC/MPC logic, or features outside the staged plans.

The engineer remains the decision maker. Recommendations change transition recipes or SOPs; they never write control targets to a plant.

## Plans and Execution

Treat `.plans/00-master-plan.md` as governing scope and execute numbered stages in order. Update a stage when discoveries materially change its interface or acceptance criteria. Do not expand scope to resolve a demo-only limitation. Prefer the simplest workaround that preserves the presentation.

## Project Structure

- `app.py` — Streamlit entry point and top-level workspace.
- `components/` — Plotly figures and focused UI panels.
- `agent/` — OpenAI Responses API loop and local analysis tools.
- `data/` — generated histories, derived events, and generation arguments.
- `scripts/` — offline simulation and data-generation utilities.
- `assets/` — CSS and static presentation assets.
- `.plans/` — staged implementation contracts.
- `tests/` — only high-value smoke or calculation checks.

Use the gas-phase example from ModularSimulator commit `da3ec63` through an isolated, untracked archive. Do not modify the user’s current dirty ModularSimulator checkout or copy simulator source into tracked demo files.

## Development Commands

- `uv sync` — install pinned dependencies.
- `uv run streamlit run app.py` — run the demo.
- `uv run python scripts/generate_transitions.py` — regenerate offline histories.
- `uv run pytest -q` — run the intentionally small test set.
- `uv run ruff check .` — catch obvious Python errors.

## Coding Style

Use Python with four-space indentation, type hints at data/tool boundaries, `snake_case` functions and modules, and `PascalCase` classes. Prefer direct, readable code over abstractions intended for future reuse. Keep Plotly construction separate from agent orchestration so tool-driven UI changes remain understandable.

## Communications Style

- Do not use maxims. Say what happened to the named subject. Do not end with a general truth about a category.
- Do not use “X rather than Y” or “X, not Y” closers. State X. Stop.
- Do not use “the” before a noun that has not been introduced. Introduce a new noun with “a” or name the noun precisely.
- Use simple past for completed past events. Write “marked,” not “was marking.”
- Name the referent. Avoid phrases such as “that job,” “this pattern,” or “that asymmetry.”
- Do not assign intentions or strength to objects. A comma does not perform a job.
- Write one idea per sentence. If a sentence balances on “and,” split the sentence. Cut any decorative half.

## Validation and Delivery

Validate the ideal workflow manually before adding tests. Required checks are limited to: both transition directions generate non-identical histories, the 3×2 trend layout is correct, tool calls update UI state, and both suggested prompts return evidence consistent with visible trends. Skip broad regression suites, browser automation, coverage targets, exhaustive error handling, and production hardening unless needed to complete the live demo.

Use short imperative commits. For visual changes, include a screenshot and note any simulated-data assumptions.
