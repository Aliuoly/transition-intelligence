import json
from pathlib import Path

from agent.tools import TOOL_SCHEMAS, TransitionToolbox, WorkspaceState
from components.data import load_repository


def test_load_transitions_updates_workspace_and_returns_visual_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    image_path = tmp_path / "trends.png"
    image_path.write_bytes(b"png evidence")
    workspace = WorkspaceState()
    toolbox = TransitionToolbox(load_repository(), workspace)
    monkeypatch.setattr(toolbox, "_render", lambda: image_path)

    result = toolbox.load_transitions("2210", "1630", 3)

    assert workspace.selected_transition_ids == ["TR-01", "TR-03", "TR-05"]
    assert workspace.focal_id == "TR-05"
    assert workspace.layout_name == "overview"
    assert result.activity == "Loaded 3 transitions"
    assert result.image_path == image_path
    evidence = json.loads(result.text_output)
    assert set(evidence) == {"transitions"}
    assert all(
        set(item)
        == {
            "transition_id",
            "date",
            "start_recipe",
            "end_recipe",
            "duration_hours",
            "transition_resin_t",
        }
        for item in evidence["transitions"]
    )


def test_agent_tool_contract_separates_ui_loading_from_private_inspection() -> None:
    schemas = {item["name"]: item for item in TOOL_SCHEMAS}

    assert set(schemas) == {
        "load_transitions",
        "summarize_transitions",
        "get_event_evidence",
        "view_specific_trends",
        "get_trend_data",
    }
    view_parameters = schemas["view_specific_trends"]["parameters"]
    assert view_parameters["properties"]["layout"]["enum"] == ["overview", "pressure_vent"]


def test_summarize_transitions_exposes_limits_and_prior_day_lab_error() -> None:
    toolbox = TransitionToolbox(load_repository(), WorkspaceState())

    result = toolbox.summarize_transitions(["TR-01", "TR-05"])

    evidence = json.loads(result.text_output)
    assert "pending engineer implementation and verification" in evidence["summary_basis"]
    assert [item["transition_id"] for item in evidence["transitions"]] == ["TR-01", "TR-05"]
    summary = evidence["transitions"][0]
    assert summary["actuator_limits"]["hydrogen"]["limit"] == 20.0
    assert summary["actuator_limits"]["comonomer"]["limit"] == 7000.0
    assert summary["actuator_limits"]["vent"]["limit"] == 1000.0
    assert summary["pretransition_lab_error_baseline"]["window_hours"] == 24.0
    assert summary["pretransition_lab_error_baseline"]["density_error_kg_m3"]["samples"] == 12
    assert set(summary["requested_vs_constrained_setpoints"]) == {"comonomer", "hydrogen"}


def test_event_evidence_is_chronological_and_leaves_significance_to_agent() -> None:
    toolbox = TransitionToolbox(load_repository(), WorkspaceState())

    result = toolbox.get_event_evidence(["TR-05", "TR-06"])

    evidence = json.loads(result.text_output)
    assert result.activity == "Collected event evidence for 2 transitions"
    assert [item["transition_id"] for item in evidence["transitions"]] == [
        "TR-05",
        "TR-06",
    ]
    high_pressure_events = evidence["transitions"][0]["events"]
    high_pressure = next(
        item for item in high_pressure_events if item["event"] == "High-pressure limit excursions"
    )
    assert "vent override activated" in high_pressure["evidence"]
    assert "significance" not in high_pressure
    assert all(
        set(item)
        == {
            "start_hour",
            "end_hour",
            "cumulative_hours",
            "event",
            "evidence",
        }
        for transcript in evidence["transitions"]
        for item in transcript["events"]
    )
    assert all(
        events == sorted(events, key=lambda item: (item["start_hour"], item["event"]))
        for events in (item["events"] for item in evidence["transitions"])
    )

    low_pressure_events = evidence["transitions"][1]["events"]
    low_pressure = next(
        item for item in low_pressure_events if item["event"] == "Low-pressure limit exposure"
    )
    assert "inhibited a hydrogen-removal vent request" in low_pressure["evidence"]


def test_view_specific_trends_does_not_update_visible_workspace(
    monkeypatch, tmp_path: Path
) -> None:
    image_path = tmp_path / "trends.png"
    image_path.write_bytes(b"png evidence")
    workspace = WorkspaceState(
        selected_transition_ids=["TR-01", "TR-03", "TR-05"],
        focal_id="TR-05",
        layout_name="overview",
        start_recipe="2210",
        end_recipe="1630",
    )
    toolbox = TransitionToolbox(load_repository(), workspace)
    monkeypatch.setattr(toolbox, "_render_specific", lambda *_args: image_path)

    result = toolbox.view_specific_trends(
        ["TR-02", "TR-04", "TR-06"],
        -0.5,
        3.0,
        "pressure_vent",
        "TR-04",
    )

    assert workspace.selected_transition_ids == ["TR-01", "TR-03", "TR-05"]
    assert workspace.relative_time_window is None
    assert workspace.layout_name == "overview"
    assert workspace.focal_id == "TR-05"
    assert workspace.start_recipe == "2210"
    assert workspace.end_recipe == "1630"
    assert result.activity == "Inspected specific trends"


def test_get_trend_data_returns_bounded_named_csv() -> None:
    toolbox = TransitionToolbox(load_repository(), WorkspaceState())

    result = toolbox.get_trend_data(
        ["TR-01", "TR-05"],
        ["total_pressure", "hydrogen_mole_ratio"],
        0.0,
        0.1,
        2,
    )

    assert "total_pressure [kPa]" in result.text_output
    assert "transition_id,relative_hour,total_pressure,hydrogen_mole_ratio" in result.text_output
    assert "TR-01" in result.text_output
    assert "TR-05" in result.text_output
    assert "TR-03" not in result.text_output
