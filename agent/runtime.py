"""OpenAI Agents SDK runner and UI-neutral stream events for the demo."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    FunctionTool,
    ModelSettings,
    RunConfig,
    Runner,
    ToolOutputImage,
    ToolOutputText,
    set_tracing_export_api_key,
)
from agents.tool_context import ToolContext
from dotenv import load_dotenv
from openai.types.shared import Reasoning

from agent.tools import TOOL_SCHEMAS, ToolResult, TransitionToolbox, WorkspaceState
from components.data import TransitionRepository

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-5.6-luna"
TRACE_WORKFLOW_NAME = "Transition Intelligence Demo"
MAX_TURNS = 8
KNOWLEDGE_FILES = (
    HERE / "instruction.md",
    HERE / "knowledge.md",
    HERE / "optimization_directions.md",
)

load_dotenv(ROOT / ".env")
if tracing_api_key := os.getenv("OPENAI_API_KEY"):
    set_tracing_export_api_key(tracing_api_key)


AGENT_INSTRUCTIONS = "\n\n".join(file.read_text() for file in KNOWLEDGE_FILES)


@dataclass
class TransitionContext:
    repository: TransitionRepository
    workspace: WorkspaceState
    tool_results: dict[str, ToolResult] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ReasoningDelta:
    text: str
    new_summary: bool


@dataclass(frozen=True)
class ToolStarted:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolCompleted:
    activity: str


@dataclass(frozen=True)
class AnswerDelta:
    text: str


TransitionStreamEvent = ReasoningDelta | ToolStarted | ToolCompleted | AnswerDelta


@dataclass(frozen=True)
class AgentRunResult:
    response_id: str
    answer: str
    activities: tuple[str, ...]
    analysis_steps: tuple[dict[str, str], ...]
    conversation_history: tuple[Any, ...]


def _encode_image(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _sdk_tool_output(result: ToolResult) -> list[ToolOutputText | ToolOutputImage]:
    output: list[ToolOutputText | ToolOutputImage] = [
        ToolOutputText(text=result.text_output)
    ]
    if result.image_path is not None:
        output.append(
            ToolOutputImage(image_url=_encode_image(result.image_path), detail="high")
        )
    return output


def _build_tools() -> list[FunctionTool]:
    tools: list[FunctionTool] = []
    for schema in TOOL_SCHEMAS:
        name = schema["name"]

        async def invoke(
            ctx: ToolContext[TransitionContext],
            arguments_json: str,
            tool_name: str = name,
        ) -> list[ToolOutputText | ToolOutputImage]:
            arguments = json.loads(arguments_json)
            toolbox = TransitionToolbox(ctx.context.repository, ctx.context.workspace)
            result = toolbox.execute(tool_name, arguments)
            ctx.context.tool_results[ctx.tool_call_id] = result
            return _sdk_tool_output(result)

        tools.append(
            FunctionTool(
                name=name,
                description=schema["description"],
                params_json_schema=schema["parameters"],
                on_invoke_tool=invoke,
                strict_json_schema=bool(schema.get("strict", True)),
            )
        )
    return tools


def _tool_call_details(item: Any) -> tuple[str, dict[str, Any]]:
    raw_item = item.raw_item
    name = raw_item.get("name", "tool") if isinstance(raw_item, dict) else raw_item.name
    raw_arguments = (
        raw_item.get("arguments", "{}")
        if isinstance(raw_item, dict)
        else raw_item.arguments
    )
    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError):
        arguments = {}
    return name, arguments


def _tool_call_id(item: Any) -> str | None:
    call_id = getattr(item, "call_id", None)
    if call_id:
        return call_id
    raw_item = item.raw_item
    if isinstance(raw_item, dict):
        return raw_item.get("call_id") or raw_item.get("id")
    return getattr(raw_item, "call_id", None) or getattr(raw_item, "id", None)


class TransitionRun:
    """Adapts SDK stream events without exposing SDK classes to Streamlit."""

    def __init__(self, sdk_result: Any, context: TransitionContext) -> None:
        self._sdk_result = sdk_result
        self.context = context
        self._activities: list[str] = []
        self._analysis_steps: list[dict[str, str]] = []
        self._result: AgentRunResult | None = None

    async def stream_events(self):
        reasoning_summary_open = False
        async for event in self._sdk_result.stream_events():
            if event.type == "raw_response_event":
                data = event.data
                if data.type == "response.created":
                    reasoning_summary_open = False
                elif data.type == "response.reasoning_summary_text.delta":
                    is_new = not reasoning_summary_open
                    reasoning_summary_open = True
                    if is_new:
                        self._analysis_steps.append(
                            {"type": "reasoning", "content": data.delta}
                        )
                    else:
                        self._analysis_steps[-1]["content"] += data.delta
                    yield ReasoningDelta(data.delta, is_new)
                elif data.type == "response.output_text.delta":
                    yield AnswerDelta(data.delta)
                continue

            if event.type != "run_item_stream_event":
                continue
            if event.name == "tool_called":
                name, arguments = _tool_call_details(event.item)
                yield ToolStarted(name, arguments)
            elif event.name == "tool_output":
                call_id = _tool_call_id(event.item)
                result = self.context.tool_results.pop(call_id, None)
                activity = result.activity if result is not None else "Completed tool call"
                self._activities.append(activity)
                self._analysis_steps.append(
                    {"type": "tool", "content": activity, "state": "complete"}
                )
                yield ToolCompleted(activity)

        answer = str(self._sdk_result.final_output or "").strip()
        if not answer:
            raise RuntimeError("The agent returned no final text")
        self._result = AgentRunResult(
            response_id=self._sdk_result.last_response_id or "",
            answer=answer,
            activities=tuple(self._activities),
            analysis_steps=tuple(dict(step) for step in self._analysis_steps),
            conversation_history=tuple(self._sdk_result.to_input_list()),
        )

    @property
    def result(self) -> AgentRunResult:
        if self._result is None:
            raise RuntimeError("Consume stream_events() before reading the result")
        return self._result


class TransitionAgent:
    def __init__(
        self,
        model: str | None = None,
        enable_tracing: bool = True,
        runner: Any = Runner,
    ) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.enable_tracing = enable_tracing
        self._runner = runner
        self.agent = Agent[TransitionContext](
            name="Transition Intelligence",
            instructions=AGENT_INSTRUCTIONS,
            model=self.model,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="xhigh", summary="auto"),
                verbosity="low",
                parallel_tool_calls=False,
            ),
            tools=_build_tools(),
        )

    async def start(
        self,
        prompt: str,
        toolbox: TransitionToolbox,
        conversation_history: list[Any] | None = None,
    ) -> TransitionRun:
        history = list(conversation_history or [])
        history.append(
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        )
        context = TransitionContext(toolbox.repository, toolbox.workspace)
        sdk_result = self._runner.run_streamed(
            self.agent,
            history,
            context=context,
            max_turns=MAX_TURNS,
            run_config=RunConfig(
                workflow_name=TRACE_WORKFLOW_NAME,
                trace_metadata={"model": self.model},
                tracing_disabled=not self.enable_tracing,
            ),
        )
        return TransitionRun(sdk_result, context)
