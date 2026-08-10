"""Transition Intelligence demo workspace."""

from __future__ import annotations

import asyncio
import html
import os
from pathlib import Path
from typing import Any

import streamlit as st
from agents.exceptions import AgentsException
from openai import OpenAIError

from agent import (
    AnswerDelta,
    ReasoningDelta,
    ToolCompleted,
    ToolStarted,
    TransitionAgent,
    TransitionToolbox,
    WorkspaceState,
)
from components.chat import render_chat_autoscroll
from components.data import TransitionRepository, load_repository
from components.event_interaction import (
    render_chart_event_bridge,
    render_interactive_answer,
)
from components.trends import TRANSITION_COLORS, build_transition_figure

ROOT = Path(__file__).resolve().parent
AI_ICON = ROOT / "assets/ai.png"
PLOTLY_CONFIG = {
    "scrollZoom": False,
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
}


@st.cache_data(show_spinner=False)
def get_repository() -> TransitionRepository:
    return load_repository()


def inject_css() -> None:
    css = (ROOT / "assets/workspace.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialize_state() -> None:
    defaults: dict[str, Any] = {
        "start_recipe": "1630",
        "end_recipe": "2210",
        "selected_ids": [],
        "focal_id": None,
        "layout_label": "3 × 3 overview",
        "relative_time_window": None,
        "messages": [],
        "conversation_history": [],
        "pending_prompt": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def current_workspace() -> WorkspaceState:
    return WorkspaceState(
        selected_transition_ids=list(st.session_state.selected_ids),
        focal_id=st.session_state.focal_id,
        layout_name=(
            "overview"
            if st.session_state.layout_label == "3 × 3 overview"
            else "pressure_vent"
        ),
        relative_time_window=st.session_state.relative_time_window,
        start_recipe=st.session_state.start_recipe,
        end_recipe=st.session_state.end_recipe,
    )


def apply_workspace(workspace: WorkspaceState) -> None:
    st.session_state.start_recipe = workspace.start_recipe
    st.session_state.end_recipe = workspace.end_recipe
    st.session_state.selected_ids = list(workspace.selected_transition_ids)
    st.session_state.focal_id = workspace.focal_id
    st.session_state.layout_label = (
        "3 × 3 overview" if workspace.layout_name == "overview" else "Pressure + vent"
    )
    st.session_state.relative_time_window = workspace.relative_time_window


def clear_manual_window() -> None:
    st.session_state.relative_time_window = None


def queue_agent_prompt() -> None:
    if prompt := st.session_state.get("agent-chat-input"):
        st.session_state.pending_prompt = prompt


def render_filters(repository: TransitionRepository) -> list[str]:
    recipe_options = sorted({str(item["start_recipe"]) for item in repository.metadata})
    start_recipe = st.selectbox(
        "Start recipe",
        recipe_options,
        key="start_recipe",
        on_change=clear_manual_window,
    )
    end_options = [item for item in recipe_options if item != start_recipe]
    if st.session_state.end_recipe not in end_options:
        st.session_state.end_recipe = end_options[0]
    end_recipe = st.selectbox(
        "End recipe",
        end_options,
        key="end_recipe",
        on_change=clear_manual_window,
    )
    matching_ids = repository.transition_ids(start_recipe, end_recipe)
    return sorted(
        matching_ids,
        key=lambda transition_id: str(repository.metadata_by_id[transition_id]["date"]),
        reverse=True,
    )


def toggle_run(transition_id: str, matching_ids: list[str], widget_key: str) -> None:
    selected = set(st.session_state.selected_ids)
    if st.session_state[widget_key]:
        if len(selected) >= 4:
            st.session_state[widget_key] = False
            return
        selected.add(transition_id)
    else:
        selected.discard(transition_id)
    st.session_state.selected_ids = [item for item in matching_ids if item in selected]
    if st.session_state.focal_id not in selected:
        st.session_state.focal_id = st.session_state.selected_ids[0] if selected else None
    clear_manual_window()


def render_run_viewer(repository: TransitionRepository, matching_ids: list[str]) -> None:
    pair_key = f"{st.session_state.start_recipe}-{st.session_state.end_recipe}"
    if st.session_state.get("run_viewer_pair") != pair_key:
        st.session_state.run_viewer_pair = pair_key
        st.session_state.selected_ids = matching_ids[:3]
        recommended = "TR-05" if st.session_state.start_recipe == "2210" else "TR-04"
        st.session_state.focal_id = (
            recommended if recommended in st.session_state.selected_ids else st.session_state.selected_ids[0]
        ) if st.session_state.selected_ids else None

    selected = set(st.session_state.selected_ids)
    maximum_duration = max(
        (float(repository.events_by_id[item]["end_hour"]) for item in matching_ids),
        default=1.0,
    )
    st.markdown('<div class="panel-kicker run-viewer-kicker">Timing + transition resin</div>', unsafe_allow_html=True)
    with st.container(height=190, border=True, key="run-viewer"):
        for transition_id in matching_ids:
            item = repository.metadata_by_id[transition_id]
            event = repository.events_by_id[transition_id]
            duration_hours = float(event["end_hour"])
            duration_width = 100.0 * duration_hours / maximum_duration
            volume_t = repository.transition_volume_t(transition_id)
            color = TRANSITION_COLORS.get(transition_id, "#436b60")
            widget_key = f"run-toggle-{pair_key}-{transition_id}"
            if widget_key not in st.session_state:
                st.session_state[widget_key] = transition_id in selected
            checkbox_column, timing_column = st.columns((0.35, 5.65), gap="small")
            with checkbox_column:
                st.checkbox(
                    f"Show {transition_id}",
                    key=widget_key,
                    label_visibility="collapsed",
                    disabled=transition_id not in selected and len(selected) >= 4,
                    on_change=toggle_run,
                    args=(transition_id, matching_ids, widget_key),
                )
            with timing_column:
                st.markdown(
                    f"""
                    <div class="run-timing-row" style="--run-color:{color}">
                      <span class="run-identity">
                        <strong>{transition_id}</strong>
                        <span class="run-date">{str(item['date'])[:10]}</span>
                      </span>
                      <span class="run-duration-track">
                        <span class="run-duration-line" style="width:{duration_width:.1f}%"></span>
                      </span>
                      <span class="run-duration">{duration_hours:.1f} h</span>
                      <span class="run-volume">{volume_t:.0f} t</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_empty_canvas() -> None:
    st.markdown(
        """
        <div class="empty-canvas">
          <strong>Transition trends</strong>
          <span>Select historical transitions to compare synchronized evidence.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tool_activity_html(activities: list[dict[str, str]]) -> str:
    if not activities:
        return ""
    rows = []
    for activity in activities:
        state = activity.get("state", "complete")
        detail = html.escape(activity.get("detail", "Working…"))
        state_label = "Running" if state == "running" else "Completed"
        rows.append(
            f"""
            <div class="tool-activity-row tool-activity-{state}">
              <span class="tool-state-dot" aria-label="{state_label}"></span>
              <span class="tool-activity-copy">
                <span>{detail}</span>
              </span>
              <span class="tool-state-label">{state_label}</span>
            </div>
            """
        )
    count = len(activities)
    label = "Tool activity" if count == 1 else f"Tool activity · {count} steps"
    return (
        f'<div class="tool-activity"><div class="tool-activity-title">{label}</div>'
        f'{"".join(rows)}</div>'
    )


def render_tool_activity(activities: list[dict[str, str]]) -> None:
    if markup := tool_activity_html(activities):
        st.html(markup)


def analysis_trace_label(steps: list[dict[str, str]]) -> str:
    completed_tools = sum(
        step.get("type") == "tool" and step.get("state") == "complete" for step in steps
    )
    if completed_tools:
        suffix = "tool" if completed_tools == 1 else "tools"
        return f"Thinking · {completed_tools} {suffix} used"
    return "Thinking"


def running_tool_label(name: str) -> str:
    return {
        "load_transitions": "Loading matching transitions…",
        "summarize_transitions": "Summarizing limits and transition evidence…",
        "get_event_evidence": "Collecting notable event evidence…",
        "view_specific_trends": "Inspecting focused trends…",
        "get_trend_data": "Checking exact trend data…",
    }.get(name, "Running analysis tool…")


def render_analysis_trace(steps: list[dict[str, str]]) -> None:
    status = st.status(
        analysis_trace_label(steps),
        expanded=False,
        state="complete",
        type="compact",
    )
    if not steps:
        status.markdown(
            '<span class="agent-thinking">No analysis details were returned.</span>',
            unsafe_allow_html=True,
        )
    for step in steps:
        if step.get("type") == "reasoning":
            status.markdown(step.get("content") or "Reviewing the evidence…")
        elif step.get("type") == "tool":
            status.html(
                tool_activity_html(
                    [
                        {
                            "detail": step.get("content", "Working…"),
                            "state": step.get("state", "complete"),
                        }
                    ]
                )
            )


def render_message(message: dict[str, Any]) -> None:
    role = message["role"]
    avatar = str(AI_ICON) if role == "assistant" else None
    with st.chat_message(role, avatar=avatar):
        if role == "assistant":
            analysis = message.get("analysis")
            if analysis is None:
                analysis = [
                    {
                        "type": "tool",
                        "content": tool.get("detail", "Completed"),
                        "state": tool.get("state", "complete"),
                    }
                    for tool in message.get("tools", [])
                ]
            render_analysis_trace(analysis)
        if role == "assistant":
            render_interactive_answer(message["content"], TRANSITION_COLORS)
        else:
            st.markdown(message["content"])


def render_agent_pane(repository: TransitionRepository) -> None:
    prompt = st.session_state.pop("pending_prompt", None)
    welcome_placeholder = None
    transcript = st.container(height="stretch", border=False, key="agent-transcript")
    with transcript:
        if st.session_state.messages:
            for message in st.session_state.messages:
                render_message(message)
        else:
            welcome_placeholder = st.empty()
            with welcome_placeholder.container():
                st.markdown(
                    '<div class="agent-welcome"><strong>How can I help?</strong><span>Choose a transition or ask a question.</span></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Optimize transition 2210 to 1630",
                    key="prompt-high-pressure",
                    width="stretch",
                ):
                    prompt = "Optimize transition 2210 to 1630"
                if st.button(
                    "Optimize transition 1630 to 2210",
                    key="prompt-low-pressure",
                    width="stretch",
                ):
                    prompt = "Optimize transition 1630 to 2210"

    st.chat_input(
        "Ask about a transition",
        key="agent-chat-input",
        submit_mode="disable",
        on_submit=queue_agent_prompt,
    )
    render_chat_autoscroll()

    if prompt is not None:
        if welcome_placeholder is not None:
            welcome_placeholder.empty()
        user_message = {"role": "user", "content": prompt}
        st.session_state.messages.append(user_message)
        with transcript:
            render_message(user_message)
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Set OPENAI_API_KEY to run the live analysis.")
        else:
            workspace = current_workspace()
            toolbox = TransitionToolbox(repository, workspace)
            live_analysis: list[dict[str, str]] = []
            live_answer = ""
            with transcript, st.chat_message("assistant", avatar=str(AI_ICON)):
                analysis_status = st.status(
                    "Thinking",
                    expanded=True,
                    state="running",
                    type="compact",
                )
                reasoning_placeholder = analysis_status.empty()
                reasoning_placeholder.markdown(
                    '<span class="agent-thinking">Reviewing the transition history…</span>',
                    unsafe_allow_html=True,
                )
                tool_placeholder = None
                response_placeholder = st.empty()

            async def stream_run():
                nonlocal reasoning_placeholder, tool_placeholder, live_answer
                run = await TransitionAgent().start(
                    prompt,
                    toolbox,
                    st.session_state.conversation_history,
                )
                async for event in run.stream_events():
                    match event:
                        case ReasoningDelta(text, new_summary):
                            if new_summary:
                                live_analysis.append({"type": "reasoning", "content": text})
                                if reasoning_placeholder is None:
                                    reasoning_placeholder = analysis_status.empty()
                            elif live_analysis and live_analysis[-1].get("type") == "reasoning":
                                live_analysis[-1]["content"] += text
                            if reasoning_placeholder is not None:
                                reasoning_placeholder.markdown(live_analysis[-1]["content"])

                        case ToolStarted(name, _arguments):
                            detail = running_tool_label(name)
                            live_analysis.append(
                                {
                                    "type": "tool",
                                    "name": name,
                                    "content": detail,
                                    "state": "running",
                                }
                            )
                            tool_placeholder = analysis_status.empty()
                            tool_placeholder.html(
                                tool_activity_html([{"detail": detail, "state": "running"}])
                            )
                            reasoning_placeholder = None

                        case ToolCompleted(activity):
                            apply_workspace(workspace)
                            if live_analysis and live_analysis[-1].get("type") == "tool":
                                live_analysis[-1]["content"] = activity
                                live_analysis[-1]["state"] = "complete"
                            if tool_placeholder is not None:
                                tool_placeholder.html(
                                    tool_activity_html(
                                        [{"detail": activity, "state": "complete"}]
                                    )
                                )
                            analysis_status.update(
                                label=analysis_trace_label(live_analysis),
                                expanded=True,
                                state="running",
                            )

                        case AnswerDelta(text):
                            if not live_answer:
                                analysis_status.update(
                                    label=analysis_trace_label(live_analysis),
                                    expanded=False,
                                    state="complete",
                                )
                            live_answer += text
                            response_placeholder.markdown(live_answer + "▌")
                return run.result

            try:
                result = asyncio.run(stream_run())
            except (AgentsException, OpenAIError, OSError, RuntimeError, ValueError) as error:
                analysis_status.update(label="Analysis failed", expanded=True, state="error")
                response_placeholder.error(str(error))
            else:
                apply_workspace(workspace)
                st.session_state.conversation_history = list(result.conversation_history)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.answer,
                        "analysis": [dict(step) for step in live_analysis],
                    }
                )
                response_placeholder.empty()
                with response_placeholder.container():
                    render_interactive_answer(result.answer, TRANSITION_COLORS)


st.set_page_config(
    page_title="Transition Intelligence",
    page_icon="◫",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_css()
initialize_state()
repository = get_repository()

st.markdown(
    """
    <div class="demo-header">
      <div class="demo-title">Transition Intelligence</div>
    </div>
    """,
    unsafe_allow_html=True,
)

trend_column, agent_column = st.columns((5.65, 2.55), gap="medium")
with agent_column:
    st.markdown(
        '<div class="panel-kicker run-viewer-kicker">Advisor analysis</div>',
        unsafe_allow_html=True,
    )
    with st.container(border=True, key="agent-panel"):
        render_agent_pane(repository)

with trend_column:
    recipe_column, viewer_column = st.columns((1.25, 4.75), gap="small")
    with recipe_column:
        st.markdown('<div class="panel-kicker run-viewer-kicker">Transition recipes</div>', unsafe_allow_html=True)
        with st.container(height=190, border=True, key="cohort-controls"):
            matching = render_filters(repository)
    with viewer_column:
        render_run_viewer(repository, matching)
    selected = list(st.session_state.selected_ids)
    focal = st.session_state.focal_id
    layout = current_workspace().layout_name
    if selected:
        figure = build_transition_figure(
            repository,
            selected,
            focal,
            st.session_state.relative_time_window,
            layout,
            include_event_rail=False,
            responsive_height=True,
        )
        chart_key = f"transition-trends-{layout}"
        st.plotly_chart(
            figure,
            width="stretch",
            config=PLOTLY_CONFIG,
            key=chart_key,
        )
        render_chart_event_bridge(chart_key, TRANSITION_COLORS)
    else:
        render_empty_canvas()
