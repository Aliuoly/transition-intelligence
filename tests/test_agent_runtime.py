import asyncio
from pathlib import Path
from types import SimpleNamespace

from agents.tool_context import ToolContext

from agent.runtime import (
    AGENT_INSTRUCTIONS,
    DEFAULT_MODEL,
    KNOWLEDGE_FILES,
    AnswerDelta,
    ReasoningDelta,
    ToolCompleted,
    ToolStarted,
    TransitionAgent,
    TransitionContext,
)
from agent.tools import ToolResult, TransitionToolbox, WorkspaceState
from components.data import load_repository


class FakeRunResult:
    def __init__(self, context: TransitionContext, image_path: Path) -> None:
        self.context = context
        self.image_path = image_path
        self.final_output = "Directional recommendation"
        self.last_response_id = "response-2"

    async def stream_events(self):
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.created"),
        )
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(
                type="response.reasoning_summary_text.delta",
                delta="Inspecting visible trends.",
            ),
        )
        yield SimpleNamespace(
            type="run_item_stream_event",
            name="tool_called",
            item=SimpleNamespace(
                raw_item=SimpleNamespace(
                    name="load_transitions",
                    arguments='{"start_recipe":"2210","end_recipe":"1630","count":3}',
                    call_id="call-1",
                )
            ),
        )
        self.context.workspace.selected_transition_ids = ["TR-01", "TR-03", "TR-05"]
        self.context.tool_results["call-1"] = ToolResult(
            activity="Loaded 3 transitions",
            text_output="{}",
            image_path=self.image_path,
        )
        yield SimpleNamespace(
            type="run_item_stream_event",
            name="tool_output",
            item=SimpleNamespace(
                call_id="call-1",
                raw_item=SimpleNamespace(call_id="call-1"),
            ),
        )
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.created"),
        )
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(
                type="response.reasoning_summary_text.delta",
                delta="Comparing the selected runs.",
            ),
        )
        yield SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(
                type="response.output_text.delta",
                delta="Directional recommendation",
            ),
        )

    def to_input_list(self):
        return [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Optimize transition"}],
            },
            {"type": "message", "role": "assistant", "content": []},
        ]


class FakeRunner:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path
        self.requests: list[dict[str, object]] = []

    def run_streamed(self, agent, input, **kwargs):
        self.requests.append({"agent": agent, "input": input, **kwargs})
        return FakeRunResult(kwargs["context"], self.image_path)


def test_agent_instructions_include_all_process_knowledge_documents() -> None:
    assert len(KNOWLEDGE_FILES) == 3
    assert all(path.exists() for path in KNOWLEDGE_FILES)
    assert "Transition Dynamics and Process Memory" in AGENT_INSTRUCTIONS
    assert "Observation → Mechanism → Consequence → Intervention" in AGENT_INSTRUCTIONS
    assert "Selecting Grade-Transition Optimization Directions" in AGENT_INSTRUCTIONS
    assert "### Slow the leading property" in AGENT_INSTRUCTIONS
    assert "Do **not** ramp, filter, delay, or otherwise reshape the density or MFR target" not in (
        AGENT_INSTRUCTIONS
    )
    assert "Avoid These Failure Modes" in AGENT_INSTRUCTIONS
    assert "Notable event transcript" in AGENT_INSTRUCTIONS
    assert "write a compact **Notable event transcript** in your own words" in AGENT_INSTRUCTIONS
    assert "does not supply event significance" in AGENT_INSTRUCTIONS
    assert "<!--event:TR-05:0.533:1.133-->" in AGENT_INSTRUCTIONS
    assert "Keep each bullet on one physical Markdown line" in AGENT_INSTRUCTIONS
    assert "final answer under 350 words" in AGENT_INSTRUCTIONS
    assert "exactly three distinct recommendations" in AGENT_INSTRUCTIONS
    assert "ranked from highest to lowest confidence" in AGENT_INSTRUCTIONS
    assert "Return one primary recommendation" not in AGENT_INSTRUCTIONS


def test_runner_stream_translates_events_and_preserves_history(tmp_path: Path) -> None:
    image_path = tmp_path / "evidence.png"
    image_path.write_bytes(b"image")
    runner = FakeRunner(image_path)
    toolbox = TransitionToolbox(load_repository(), WorkspaceState())
    agent = TransitionAgent(runner=runner, enable_tracing=False)
    previous_history = [
        {"type": "message", "role": "user", "content": []},
        {"type": "message", "role": "assistant", "content": []},
    ]

    async def consume():
        run = await agent.start("Optimize transition", toolbox, previous_history)
        events = [event async for event in run.stream_events()]
        return events, run.result

    events, result = asyncio.run(consume())

    assert events == [
        ReasoningDelta("Inspecting visible trends.", True),
        ToolStarted(
            "load_transitions",
            {"start_recipe": "2210", "end_recipe": "1630", "count": 3},
        ),
        ToolCompleted("Loaded 3 transitions"),
        ReasoningDelta("Comparing the selected runs.", True),
        AnswerDelta("Directional recommendation"),
    ]
    assert result.answer == "Directional recommendation"
    assert result.response_id == "response-2"
    assert result.activities == ("Loaded 3 transitions",)
    assert result.analysis_steps == (
        {"type": "reasoning", "content": "Inspecting visible trends."},
        {"type": "tool", "content": "Loaded 3 transitions", "state": "complete"},
        {"type": "reasoning", "content": "Comparing the selected runs."},
    )
    assert result.conversation_history[-1]["role"] == "assistant"
    assert toolbox.workspace.selected_transition_ids == ["TR-01", "TR-03", "TR-05"]

    request = runner.requests[0]
    assert request["agent"].model == DEFAULT_MODEL
    assert request["agent"].model_settings.reasoning.effort == "xhigh"
    assert request["agent"].model_settings.verbosity == "low"
    assert request["agent"].model_settings.parallel_tool_calls is False
    assert request["max_turns"] == 8
    assert request["run_config"].workflow_name == "Transition Intelligence Demo"
    assert request["input"][:2] == previous_history
    assert request["input"][-1]["role"] == "user"


def test_sdk_function_tool_keeps_strict_schema_and_returns_image(
    monkeypatch, tmp_path: Path
) -> None:
    image_path = tmp_path / "evidence.png"
    image_path.write_bytes(b"image")
    monkeypatch.setattr(TransitionToolbox, "_render", lambda _self: image_path)
    context = TransitionContext(load_repository(), WorkspaceState())
    agent = TransitionAgent(enable_tracing=False)
    tool = next(item for item in agent.agent.tools if item.name == "load_transitions")
    tool_context = ToolContext(
        context,
        tool_name=tool.name,
        tool_call_id="call-1",
        tool_arguments='{"start_recipe":"2210","end_recipe":"1630","count":3}',
    )

    output = asyncio.run(tool.on_invoke_tool(tool_context, tool_context.tool_arguments))

    assert tool.strict_json_schema is True
    assert tool.params_json_schema["properties"]["count"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 3,
    }
    assert output[0].type == "text"
    assert output[1].type == "image"
    assert output[1].image_url.startswith("data:image/png;base64,")
    assert context.tool_results["call-1"].activity == "Loaded 3 transitions"
