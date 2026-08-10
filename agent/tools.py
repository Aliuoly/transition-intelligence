"""Local function tools that control and inspect the visible trend workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from components.data import TransitionRepository
from components.trends import build_transition_figure, export_vlm_png

ROOT = Path(__file__).resolve().parents[1]
RENDER_PATH = ROOT / ".cache/agent/current_trends.png"
MAX_TRANSITIONS = 3

TAG_COLUMNS = {
    "total_pressure": ("total_pressure_kpa", "kPa"),
    "pressure_low_limit": ("pressure_low_limit_kpa", "kPa"),
    "pressure_high_limit": ("pressure_high_limit_kpa", "kPa"),
    "ethylene_partial_pressure": ("ethylene_partial_pressure_kpa", "kPa"),
    "ethylene_partial_pressure_setpoint": ("ethylene_partial_pressure_sp_kpa", "kPa"),
    "predicted_density": ("predicted_density_kg_m3", "kg/m3"),
    "lab_density": ("lab_density_kg_m3", "kg/m3"),
    "density_target": ("density_target_kg_m3", "kg/m3"),
    "comonomer_mole_ratio": ("comonomer_mole_ratio", "mol/mol"),
    "comonomer_mole_ratio_requested_setpoint": (
        "comonomer_mole_ratio_sp_request",
        "mol/mol",
    ),
    "comonomer_mole_ratio_setpoint": ("comonomer_mole_ratio_sp", "mol/mol"),
    "fm2_comonomer_feed": ("comonomer_feed_kg_h", "kg/h"),
    "predicted_mfr": ("predicted_mfr_g_10min", "g/10 min"),
    "lab_mfr": ("lab_mfr_g_10min", "g/10 min"),
    "mfr_target": ("mfr_target_g_10min", "g/10 min"),
    "hydrogen_mole_ratio": ("hydrogen_mole_ratio", "mol/mol"),
    "hydrogen_mole_ratio_requested_setpoint": (
        "hydrogen_mole_ratio_sp_request",
        "mol/mol",
    ),
    "hydrogen_mole_ratio_setpoint": ("hydrogen_mole_ratio_sp", "mol/mol"),
    "hydrogen_feed": ("hydrogen_feed_kg_h", "kg/h"),
    "vent_flow": ("vent_flow_kg_h", "kg/h"),
}


@dataclass
class WorkspaceState:
    selected_transition_ids: list[str] = field(default_factory=list)
    focal_id: str | None = None
    layout_name: str = "overview"
    relative_time_window: tuple[float, float] | None = None
    start_recipe: str = "1630"
    end_recipe: str = "2210"


@dataclass(frozen=True)
class ToolResult:
    activity: str
    text_output: str
    image_path: Path | None = None


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "load_transitions",
        "description": (
            "Load the latest matching historical cohort into the visible 3x3 workspace. "
            "Use this first for an optimization request; it returns limited run-identification "
            "summaries and a complete nine-trend image. This is the tool that changes what the "
            "engineer sees in the UI."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "start_recipe": {"type": "string", "enum": ["2210", "1630"]},
                "end_recipe": {"type": "string", "enum": ["2210", "1630"]},
                "count": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["start_recipe", "end_recipe", "count"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "summarize_transitions",
        "description": (
            "Return deterministic trend summaries for selected transitions: stable property-entry "
            "times, pressure exposure, explicit actuator limits and saturation duration, requested-"
            "versus-constrained composition setpoints, and the prior 24-hour lab-error baseline. "
            "Use after loading a cohort before recommending a recipe or SOP change."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "transition_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^TR-[0-9]{2}$"},
                    "minItems": 1,
                    "maxItems": 3,
                },
            },
            "required": ["transition_ids"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_event_evidence",
        "description": (
            "Return neutral chronological evidence for notable transition events: pressure "
            "excursions, vent override states, controller-output saturation, property arrival, "
            "and transition duration. Use after summarize_transitions for every optimization "
            "request, then write an AI-generated transcript that explains event significance."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "transition_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^TR-[0-9]{2}$"},
                    "minItems": 1,
                    "maxItems": 3,
                },
            },
            "required": ["transition_ids"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "view_specific_trends",
        "description": (
            "Privately inspect selected transitions over a specific time window in either the "
            "complete overview or focused pressure/ethylene/vent layout. Returns an image for "
            "agent analysis without changing the engineer's visible UI state."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "transition_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^TR-[0-9]{2}$"},
                    "minItems": 1,
                    "maxItems": 3,
                },
                "start_hour": {"type": "number", "minimum": -2.0, "maximum": 13.0},
                "end_hour": {"type": "number", "minimum": -1.9, "maximum": 14.0},
                "layout": {"type": "string", "enum": ["overview", "pressure_vent"]},
                "highlight_id": {"type": "string", "pattern": "^TR-[0-9]{2}$"},
            },
            "required": ["transition_ids", "start_hour", "end_hour", "layout", "highlight_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_trend_data",
        "description": (
            "Return bounded cleaned CSV for numerical comparison, extrema, timing, and calculation. "
            "Use it whenever exact trend evidence would improve the analysis."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "transition_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^TR-[0-9]{2}$"},
                    "minItems": 1,
                    "maxItems": 3,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(TAG_COLUMNS)},
                    "minItems": 1,
                    "maxItems": 8,
                },
                "start_hour": {"type": "number", "minimum": -2.0, "maximum": 13.0},
                "end_hour": {"type": "number", "minimum": -1.9, "maximum": 14.0},
                "resample_minutes": {"type": "integer", "minimum": 2, "maximum": 60},
            },
            "required": [
                "transition_ids",
                "tags",
                "start_hour",
                "end_hour",
                "resample_minutes",
            ],
            "additionalProperties": False,
        },
    },
]


class TransitionToolbox:
    def __init__(self, repository: TransitionRepository, workspace: WorkspaceState) -> None:
        self.repository = repository
        self.workspace = workspace

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        handlers = {
            "load_transitions": self.load_transitions,
            "summarize_transitions": self.summarize_transitions,
            "get_event_evidence": self.get_event_evidence,
            "view_specific_trends": self.view_specific_trends,
            "get_trend_data": self.get_trend_data,
        }
        if name not in handlers:
            raise ValueError(f"Unknown tool: {name}")
        return handlers[name](**arguments)

    def _validate_ids(self, transition_ids: list[str]) -> list[str]:
        unique_ids = list(dict.fromkeys(transition_ids))
        if not unique_ids or len(unique_ids) > MAX_TRANSITIONS:
            raise ValueError("Select between one and three transition IDs")
        unknown = set(unique_ids) - set(self.repository.metadata_by_id)
        if unknown:
            raise ValueError(f"Unknown transition IDs: {', '.join(sorted(unknown))}")
        return unique_ids

    def _render(self) -> Path:
        figure = build_transition_figure(
            self.repository,
            self.workspace.selected_transition_ids,
            self.workspace.focal_id,
            self.workspace.relative_time_window,
            self.workspace.layout_name,
            simplified=True,
        )
        return export_vlm_png(figure, RENDER_PATH)

    def _render_specific(
        self,
        transition_ids: list[str],
        highlight_id: str,
        relative_time_window: tuple[float, float],
        layout: str,
    ) -> Path:
        figure = build_transition_figure(
            self.repository,
            transition_ids,
            highlight_id,
            relative_time_window,
            layout,
            simplified=True,
        )
        return export_vlm_png(figure, RENDER_PATH)

    def load_transitions(self, start_recipe: str, end_recipe: str, count: int = 3) -> ToolResult:
        if start_recipe == end_recipe:
            raise ValueError("Start and end recipes must differ")
        matching = self.repository.transition_ids(start_recipe, end_recipe)
        selected = matching[-count:]
        if not selected:
            raise ValueError(f"No transitions found for {start_recipe} to {end_recipe}")
        preferred = "TR-05" if (start_recipe, end_recipe) == ("2210", "1630") else "TR-04"
        focal_id = preferred if preferred in selected else selected[-1]
        self.workspace.selected_transition_ids = selected
        self.workspace.focal_id = focal_id
        self.workspace.layout_name = "overview"
        self.workspace.relative_time_window = None
        self.workspace.start_recipe = start_recipe
        self.workspace.end_recipe = end_recipe

        payload = {
            "transitions": [
                {
                    "transition_id": item,
                    "date": self.repository.metadata_by_id[item]["date"],
                    "start_recipe": self.repository.metadata_by_id[item]["start_recipe"],
                    "end_recipe": self.repository.metadata_by_id[item]["end_recipe"],
                    "duration_hours": self.repository.metadata_by_id[item]["duration_hours"],
                    "transition_resin_t": round(self.repository.transition_volume_t(item), 2),
                }
                for item in selected
            ],
        }
        return ToolResult(
            activity=f"Loaded {len(selected)} transitions",
            text_output=json.dumps(payload, separators=(",", ":")),
            image_path=self._render(),
        )

    def summarize_transitions(self, transition_ids: list[str]) -> ToolResult:
        selected = self._validate_ids(transition_ids)
        payload = {
            "summary_basis": (
                "Visible historical trends and explicit engineer-visible operating limits; "
                "recommendations are hypotheses pending engineer implementation and verification."
            ),
            "transitions": [self.repository.trend_summary(item) for item in selected],
        }
        return ToolResult(
            activity=f"Summarized constraints for {len(selected)} transitions",
            text_output=json.dumps(payload, separators=(",", ":")),
        )

    def get_event_evidence(self, transition_ids: list[str]) -> ToolResult:
        selected = self._validate_ids(transition_ids)
        payload = {
            "transitions": [
                {
                    "transition_id": transition_id,
                    "events": self.repository.event_evidence(transition_id),
                }
                for transition_id in selected
            ]
        }
        return ToolResult(
            activity=f"Collected event evidence for {len(selected)} transitions",
            text_output=json.dumps(payload, separators=(",", ":")),
        )

    def view_specific_trends(
        self,
        transition_ids: list[str],
        start_hour: float,
        end_hour: float,
        layout: str,
        highlight_id: str,
    ) -> ToolResult:
        selected = self._validate_ids(transition_ids)
        if start_hour >= end_hour:
            raise ValueError("start_hour must be less than end_hour")
        if highlight_id not in selected:
            raise ValueError("highlight_id must be one of transition_ids")
        if layout not in {"overview", "pressure_vent"}:
            raise ValueError(f"Unknown layout: {layout}")
        summary = {
            "transition_ids": selected,
            "highlight_id": highlight_id,
            "layout": layout,
            "relative_time_window": [start_hour, end_hour],
        }
        return ToolResult(
            "Inspected specific trends",
            json.dumps(summary, separators=(",", ":")),
            self._render_specific(selected, highlight_id, (start_hour, end_hour), layout),
        )

    def get_trend_data(
        self,
        transition_ids: list[str],
        tags: list[str],
        start_hour: float,
        end_hour: float,
        resample_minutes: int,
    ) -> ToolResult:
        selected = self._validate_ids(transition_ids)
        if start_hour >= end_hour:
            raise ValueError("start_hour must be less than end_hour")
        if not 2 <= resample_minutes <= 60:
            raise ValueError("resample_minutes must be between 2 and 60")
        unknown_tags = set(tags) - set(TAG_COLUMNS)
        if unknown_tags:
            raise ValueError(f"Unknown tags: {', '.join(sorted(unknown_tags))}")

        columns = [TAG_COLUMNS[tag][0] for tag in tags]
        frame = self.repository.histories[
            self.repository.histories["transition_id"].isin(selected)
            & self.repository.histories["relative_hour"].between(start_hour, end_hour)
        ][["transition_id", "relative_hour", *columns]].copy()
        bin_width = resample_minutes / 60.0
        frame["relative_hour"] = (frame["relative_hour"] / bin_width).round() * bin_width
        cleaned = frame.groupby(["transition_id", "relative_hour"], as_index=False).mean(numeric_only=True)
        cleaned = cleaned.rename(columns={TAG_COLUMNS[tag][0]: tag for tag in tags})
        cleaned["relative_hour"] = cleaned["relative_hour"].round(3)
        cleaned = cleaned.round(5)
        units = ", ".join(f"{tag} [{TAG_COLUMNS[tag][1]}]" for tag in tags)
        output = f"# units: relative_hour [h], {units}\n{cleaned.to_csv(index=False)}"
        return ToolResult(
            activity=f"Checked exact data for {len(selected)} transitions",
            text_output=output,
        )
