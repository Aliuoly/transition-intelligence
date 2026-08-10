"""Interactive Plotly trends and the matching simplified VLM export."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from components.data import TransitionRepository

TRANSITION_COLORS = {
    "TR-01": "#2f7f93",
    "TR-02": "#4f78a8",
    "TR-03": "#756bb1",
    "TR-04": "#0b8f6a",
    "TR-05": "#087f5b",
    "TR-06": "#8b6fb0",
}

PANEL_BACKGROUND = "#f3f5f7"
GRID_COLOR = "#dce2e7"
TEXT_COLOR = "#263746"
LIMIT_COLOR = "#8e5b56"
TARGET_COLOR = "#586a78"
TARGET_BAND_COLOR = "rgba(63, 155, 126, 0.13)"
SATURATION_COLOR = "rgba(196, 79, 79, 0.13)"
ACTUATOR_LIMIT_COLOR = "#b25d57"
EVENT_LEGEND = "legend10"

LANES: tuple[dict[str, Any], ...] = (
    {
        "key": "pressure",
        "row": 2,
        "col": 1,
        "title": "Total pressure",
        "unit": "kPa",
        "legend": "legend",
        "series": (("total_pressure_kpa", "Reactor pressure", "line"),),
        "band": ("pressure_low_limit_kpa", "pressure_high_limit_kpa", "Pressure range"),
        "references": (),
    },
    {
        "key": "ethylene",
        "row": 3,
        "col": 1,
        "title": "Ethylene partial pressure",
        "unit": "kPa",
        "legend": "legend2",
        "series": (("ethylene_partial_pressure_kpa", "C2 partial pressure", "line"),),
        "band": None,
        "references": (
            ("ethylene_partial_pressure_sp_kpa", "Ethylene setpoint", "dash", TARGET_COLOR),
        ),
    },
    {
        "key": "vent",
        "row": 4,
        "col": 1,
        "title": "Reactor vent flow",
        "unit": "kg/h",
        "legend": "legend3",
        "series": (("vent_flow_kg_h", "Reactor vent flow", "line"),),
        "band": None,
        "references": (),
        "actuator_key": "vent",
    },
    {
        "key": "density",
        "row": 2,
        "col": 2,
        "title": "Density",
        "unit": "kg/m³",
        "legend": "legend4",
        "series": (
            ("predicted_density_kg_m3", "Inferred density", "line"),
            ("lab_density_kg_m3", "Lab density", "marker"),
        ),
        "band": ("density_low_limit_kg_m3", "density_high_limit_kg_m3", "Target range"),
        "references": (
            ("density_target_kg_m3", "Density target", "dash", TARGET_COLOR),
        ),
    },
    {
        "key": "comonomer",
        "row": 3,
        "col": 2,
        "title": "Comonomer mole ratio",
        "unit": "mol/mol",
        "legend": "legend5",
        "series": (("comonomer_mole_ratio", "FM2/C2 mol ratio", "line"),),
        "band": None,
        "references": (
            (
                "comonomer_mole_ratio_sp_request",
                "APC requested SP",
                "dot",
                "#8a99a5",
            ),
            (
                "comonomer_mole_ratio_sp",
                "Constrained working SP",
                "dash",
                TARGET_COLOR,
            ),
        ),
    },
    {
        "key": "fm2_feed",
        "row": 4,
        "col": 2,
        "title": "FM2 comonomer feed",
        "unit": "kg/h",
        "legend": "legend6",
        "series": (("comonomer_feed_kg_h", "FM2 feed", "line"),),
        "band": None,
        "references": (),
        "actuator_key": "comonomer",
    },
    {
        "key": "mfr",
        "row": 2,
        "col": 3,
        "title": "MFR (melt flow rate)",
        "unit": "g/10 min",
        "legend": "legend7",
        "series": (
            ("predicted_mfr_g_10min", "Inferred MFR", "line"),
            ("lab_mfr_g_10min", "Lab MFR", "marker"),
        ),
        "band": ("mfr_low_limit_g_10min", "mfr_high_limit_g_10min", "Target range"),
        "references": (
            ("mfr_target_g_10min", "MFR target", "dash", TARGET_COLOR),
        ),
    },
    {
        "key": "hydrogen",
        "row": 3,
        "col": 3,
        "title": "Hydrogen mole ratio",
        "unit": "mol/mol",
        "legend": "legend8",
        "series": (("hydrogen_mole_ratio", "H2/C2 mol ratio", "line"),),
        "band": None,
        "references": (
            (
                "hydrogen_mole_ratio_sp_request",
                "APC requested SP",
                "dot",
                "#8a99a5",
            ),
            (
                "hydrogen_mole_ratio_sp",
                "Constrained working SP",
                "dash",
                TARGET_COLOR,
            ),
        ),
    },
    {
        "key": "hydrogen_feed",
        "row": 4,
        "col": 3,
        "title": "Hydrogen feed",
        "unit": "kg/h",
        "legend": "legend9",
        "series": (("hydrogen_feed_kg_h", "H2 feed", "line"),),
        "band": None,
        "references": (),
        "actuator_key": "hydrogen",
    },
)


def _selected_lanes(layout_name: str) -> tuple[dict[str, Any], ...]:
    if layout_name == "overview":
        return LANES
    if layout_name == "pressure_vent":
        return tuple(lane for lane in LANES if lane["key"] in {"pressure", "ethylene", "vent"})
    raise ValueError(f"Unknown layout: {layout_name}")


def _subplot_figure(
    lanes: tuple[dict[str, Any], ...], include_event_rail: bool
) -> go.Figure:
    first_data_row = 2 if include_event_rail else 1
    data_rows = max(int(lane["row"]) for lane in lanes) - first_data_row + 1
    data_cols = max(int(lane["col"]) for lane in lanes)
    lane_by_position = {
        (int(lane["row"]), int(lane["col"])): lane for lane in lanes
    }
    titles = (["Transition timing + resin volume"] if include_event_rail else []) + [
        str(lane_by_position[(row, col)]["title"])
        for row in range(first_data_row, first_data_row + data_rows)
        for col in range(1, data_cols + 1)
    ]
    event_rows = 1 if include_event_rail else 0
    specs = []
    row_heights = []
    if include_event_rail:
        specs.append([{"colspan": data_cols}] + [None] * (data_cols - 1))
        row_heights.append(0.12)
    specs.extend([[{} for _ in range(data_cols)] for _ in range(data_rows)])
    row_heights.extend([(1.0 - 0.12 * event_rows) / data_rows] * data_rows)
    return make_subplots(
        rows=data_rows + event_rows,
        cols=data_cols,
        specs=specs,
        row_heights=row_heights,
        vertical_spacing=0.065,
        horizontal_spacing=0.065,
        subplot_titles=titles,
        shared_xaxes=False,
    )


def _hover_template(transition_id: str, tag_name: str, unit: str) -> str:
    return (
        f"<b>{transition_id}</b><br>{tag_name}<br>"
        "Relative hour: %{x:.2f} h<br>"
        f"Value: %{{y:.3f}} {unit}<extra></extra>"
    )


def _add_event_rail(
    figure: go.Figure,
    transition_ids: list[str],
    repository: TransitionRepository,
    focal_id: str | None,
) -> None:
    for index, transition_id in enumerate(transition_ids):
        event = repository.events_by_id[transition_id]
        volume_t = repository.transition_volume_t(transition_id)
        color = TRANSITION_COLORS.get(transition_id, "#436b60")
        opacity = 1.0 if transition_id == focal_id else 0.58
        width = 6 if transition_id == focal_id else 4
        figure.add_trace(
            go.Scatter(
                x=[event["start_hour"], event["end_hour"]],
                y=[index, index],
                mode="lines+markers",
                line={"color": color, "width": width},
                marker={"color": color, "size": [6, 11], "symbol": ["circle", "diamond"]},
                opacity=opacity,
                name=transition_id,
                legend=EVENT_LEGEND,
                legendgroup=transition_id,
                showlegend=True,
                hovertemplate=(
                    f"<b>{transition_id}</b><br>Start: 0.00 h<br>Transition end: "
                    f"{event['end_hour']:.2f} h<br>Transition resin: {volume_t:.1f} t"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
        figure.add_annotation(
            x=event["start_hour"],
            y=index,
            text=f"{transition_id} start · 0.0 h ",
            showarrow=False,
            xanchor="right",
            font={"size": 9, "color": color},
            xref="x",
            yref="y",
        )
        figure.add_annotation(
            x=event["end_hour"],
            y=index,
            text=f" {transition_id} end · {event['end_hour']:.1f} h · {volume_t:.0f} t",
            showarrow=False,
            xanchor="left",
            font={"size": 10, "color": color},
            xref="x",
            yref="y",
        )


def _add_transition_series(
    figure: go.Figure,
    frame: pd.DataFrame,
    transition_id: str,
    lane: dict[str, Any],
    focal_id: str | None,
) -> None:
    color = TRANSITION_COLORS.get(transition_id, "#436b60")
    is_focal = transition_id == focal_id
    opacity = 1.0 if is_focal else 0.5
    width = 2.5 if is_focal else 1.5
    for series_index, (column, tag_name, trace_kind) in enumerate(lane["series"]):
        if trace_kind == "marker":
            valid = frame[column].notna()
            x = frame.loc[valid, "relative_hour"]
            y = frame.loc[valid, column]
            mode = "markers"
            marker = {"color": color, "size": 7 if is_focal else 6, "symbol": "circle-open"}
            line = None
        else:
            x = frame["relative_hour"]
            y = frame[column]
            mode = "lines"
            marker = None
            line = {"color": color, "width": width}
        figure.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode=mode,
                line=line,
                marker=marker,
                opacity=opacity,
                name=tag_name,
                meta={"transition_id": transition_id, "tag": tag_name},
                legend=lane["legend"],
                legendgroup=f"{lane['key']}-{column}",
                showlegend=is_focal,
                hovertemplate=_hover_template(transition_id, tag_name, lane["unit"]),
            ),
            row=lane["row"],
            col=lane["col"],
        )


def _add_target_band(
    figure: go.Figure,
    frame: pd.DataFrame,
    transition_id: str,
    lane: dict[str, Any],
) -> None:
    if lane["band"] is None:
        return
    low_column, high_column, label = lane["band"]
    group = f"{lane['key']}-band"
    figure.add_trace(
        go.Scatter(
            x=frame["relative_hour"],
            y=frame[low_column],
            mode="lines",
            line={"width": 0},
            legend=lane["legend"],
            legendgroup=group,
            showlegend=False,
            hoverinfo="skip",
        ),
        row=lane["row"],
        col=lane["col"],
    )
    figure.add_trace(
        go.Scatter(
            x=frame["relative_hour"],
            y=frame[high_column],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor=TARGET_BAND_COLOR,
            name=label,
            legend=lane["legend"],
            legendgroup=group,
            hoverinfo="skip",
        ),
        row=lane["row"],
        col=lane["col"],
    )


def _add_references(
    figure: go.Figure,
    frame: pd.DataFrame,
    transition_id: str,
    lane: dict[str, Any],
) -> None:
    for column, tag_name, dash, color in lane["references"]:
        figure.add_trace(
            go.Scatter(
                x=frame["relative_hour"],
                y=frame[column],
                mode="lines",
                line={"color": color, "width": 1.2, "dash": dash},
                name=tag_name,
                meta={"transition_id": transition_id, "tag": tag_name},
                legend=lane["legend"],
                legendgroup=f"reference-{lane['key']}-{column}",
                showlegend=True,
                hovertemplate=_hover_template(transition_id, tag_name, lane["unit"]),
            ),
            row=lane["row"],
            col=lane["col"],
        )


def _lane_y_range(histories: pd.DataFrame, lane: dict[str, Any]) -> tuple[float, float]:
    """Return a padded data range that excludes actuator-limit evidence traces."""
    columns = [str(item[0]) for item in lane["series"]]
    columns.extend(str(item[0]) for item in lane["references"])
    if lane["band"] is not None:
        columns.extend((str(lane["band"][0]), str(lane["band"][1])))
    values = pd.concat(
        [pd.to_numeric(histories[column], errors="coerce") for column in columns],
        ignore_index=True,
    ).dropna()
    if values.empty:
        return (0.0, 1.0)
    minimum = float(values.min())
    maximum = float(values.max())
    span = maximum - minimum
    padding = span * 0.07 if span > 0 else max(abs(maximum) * 0.05, 1e-6)
    lower = minimum - padding
    if lane.get("actuator_key") is not None and minimum >= 0:
        lower = max(0.0, lower)
    return (lower, maximum + padding)


def _position_legends(
    figure: go.Figure,
    lanes: tuple[dict[str, Any], ...],
    include_event_rail: bool,
) -> None:
    for lane in lanes:
        subplot = figure.get_subplot(lane["row"], lane["col"])
        x_domain = subplot.xaxis.domain
        y_domain = subplot.yaxis.domain
        figure.update_layout(
            {
                lane["legend"]: {
                    "x": x_domain[1] - 0.005,
                    "y": y_domain[1] - 0.005,
                    "xanchor": "right",
                    "yanchor": "top",
                    "xref": "paper",
                    "yref": "paper",
                    "orientation": "v",
                    "bgcolor": "rgba(255,255,255,0.78)",
                    "bordercolor": "rgba(184,195,203,0.75)",
                    "borderwidth": 1,
                    "font": {"size": 7, "color": TEXT_COLOR},
                    "groupclick": "togglegroup",
                    "itemsizing": "constant",
                    "tracegroupgap": 1,
                }
            }
        )

    if not include_event_rail:
        return
    timing_subplot = figure.get_subplot(1, 1)
    figure.update_layout(
        {
            EVENT_LEGEND: {
                "x": timing_subplot.xaxis.domain[1] - 0.005,
                "y": 1.015,
                "xanchor": "right",
                "yanchor": "bottom",
                "xref": "paper",
                "yref": "paper",
                "orientation": "h",
                "bgcolor": "rgba(255,255,255,0.86)",
                "bordercolor": "rgba(184,195,203,0.75)",
                "borderwidth": 1,
                "font": {"size": 9, "color": TEXT_COLOR},
                "groupclick": "togglegroup",
                "itemsizing": "constant",
                "title": {"text": "Show / hide runs"},
            }
        }
    )


def _saturation_intervals(
    frame: pd.DataFrame, column: str, threshold: float
) -> list[tuple[float, float]]:
    if frame.empty:
        return []
    ordered = frame.sort_values("relative_hour")
    sample_hours = float(ordered["relative_hour"].diff().median()) if len(ordered) > 1 else 0.0
    intervals: list[tuple[float, float]] = []
    start: float | None = None
    previous: float | None = None
    for hour, saturated in zip(
        ordered["relative_hour"], ordered[column] >= threshold, strict=True
    ):
        hour = float(hour)
        if saturated and start is None:
            start = hour
        if not saturated and start is not None and previous is not None:
            intervals.append((start, previous + sample_hours))
            start = None
        previous = hour
    if start is not None and previous is not None:
        intervals.append((start, previous + sample_hours))
    return intervals


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _add_actuator_evidence(
    figure: go.Figure,
    histories: pd.DataFrame,
    transition_ids: list[str],
    repository: TransitionRepository,
    lane: dict[str, Any],
    window: tuple[float, float],
) -> None:
    actuator_key = lane.get("actuator_key")
    if actuator_key is None:
        return
    definition = repository.operating_limits["actuators"][actuator_key]
    limit = float(definition["limit"])
    threshold = limit * float(repository.operating_limits["saturation_fraction"])
    figure.add_trace(
        go.Scatter(
            x=[window[0], window[1]],
            y=[limit, limit],
            mode="lines",
            line={"color": ACTUATOR_LIMIT_COLOR, "width": 1.2, "dash": "dot"},
            name=f"Actuator limit · {limit:g} {definition['unit']}",
            meta={"tag": f"{definition['label']} actuator limit"},
            legend=lane["legend"],
            legendgroup=f"actuator-limit-{actuator_key}",
            showlegend=True,
            hovertemplate=(
                f"<b>{definition['label']} actuator limit</b><br>"
                f"%{{y:.1f}} {definition['unit']}<extra></extra>"
            ),
        ),
        row=lane["row"],
        col=lane["col"],
    )
    intervals: list[tuple[float, float]] = []
    for transition_id in transition_ids:
        frame = histories[histories["transition_id"] == transition_id]
        intervals.extend(_saturation_intervals(frame, definition["column"], threshold))
    for start, end in _merge_intervals(intervals):
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor=SATURATION_COLOR,
            opacity=1.0,
            line_width=0,
            layer="below",
            row=lane["row"],
            col=lane["col"],
        )


def _shade_pressure_events(
    figure: go.Figure,
    transition_ids: Iterable[str],
    events_by_id: dict[str, dict[str, Any]],
    pressure_lane: dict[str, Any],
) -> None:
    for transition_id in transition_ids:
        event = events_by_id[transition_id]
        intervals = event["high_pressure_intervals"] + event["low_pressure_intervals"]
        meaningful = [item for item in intervals if item["end_hour"] - item["start_hour"] >= 0.05]
        if not meaningful:
            continue
        longest = max(meaningful, key=lambda item: item["end_hour"] - item["start_hour"])
        figure.add_vrect(
            x0=longest["start_hour"],
            x1=longest["end_hour"],
            fillcolor=TRANSITION_COLORS.get(transition_id, LIMIT_COLOR),
            opacity=0.07,
            line_width=0,
            row=pressure_lane["row"],
            col=pressure_lane["col"],
        )


def build_transition_figure(
    repository: TransitionRepository,
    selected_transition_ids: Iterable[str],
    focal_id: str | None = None,
    relative_time_window: tuple[float, float] | None = None,
    layout_name: str = "overview",
    *,
    simplified: bool = False,
    include_event_rail: bool = True,
    responsive_height: bool = False,
) -> go.Figure:
    """Build an interactive overview or focused pressure-and-vent figure.

    The selected IDs, focal ID, time window, and layout name form the Stage 3 tool boundary.
    """
    transition_ids = list(dict.fromkeys(selected_transition_ids))
    if not transition_ids:
        raise ValueError("At least one transition ID is required")
    unknown = set(transition_ids) - set(repository.metadata_by_id)
    if unknown:
        raise ValueError(f"Unknown transition IDs: {', '.join(sorted(unknown))}")
    if focal_id not in transition_ids:
        focal_id = transition_ids[0]

    lanes = _selected_lanes(layout_name)
    if not include_event_rail:
        lanes = tuple({**lane, "row": int(lane["row"]) - 1} for lane in lanes)
    figure = _subplot_figure(lanes, include_event_rail)
    end_hour = max(repository.events_by_id[item]["end_hour"] for item in transition_ids)
    window = relative_time_window or (-2.0, end_hour + 2.0)
    histories = repository.histories[
        repository.histories["transition_id"].isin(transition_ids)
        & repository.histories["relative_hour"].between(*window)
    ]

    if include_event_rail:
        _add_event_rail(figure, transition_ids, repository, focal_id)
    reference_id = focal_id or transition_ids[0]
    reference_frame = histories[histories["transition_id"] == reference_id]
    for lane in lanes:
        _add_target_band(figure, reference_frame, reference_id, lane)
    for transition_id in transition_ids:
        frame = histories[histories["transition_id"] == transition_id]
        for lane in lanes:
            _add_transition_series(figure, frame, transition_id, lane, focal_id)

    for lane in lanes:
        _add_references(figure, reference_frame, reference_id, lane)
        _add_actuator_evidence(
            figure,
            histories,
            transition_ids,
            repository,
            lane,
            window,
        )
        figure.add_vline(
            x=0.0,
            line={"color": "#748691", "width": 1, "dash": "dot"},
            opacity=0.55,
            row=lane["row"],
            col=lane["col"],
        )
    pressure_lane = next((lane for lane in lanes if lane["key"] == "pressure"), None)
    if pressure_lane is not None:
        _shade_pressure_events(figure, transition_ids, repository.events_by_id, pressure_lane)

    data_rows = max(int(lane["row"]) for lane in lanes)
    figure.update_xaxes(range=window, showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    figure.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, automargin=True)
    if include_event_rail:
        figure.update_yaxes(
            tickmode="array",
            tickvals=list(range(len(transition_ids))),
            ticktext=transition_ids,
            showgrid=False,
            fixedrange=True,
            row=1,
            col=1,
        )
        figure.update_xaxes(showticklabels=False, row=1, col=1)
    for lane in lanes:
        figure.update_yaxes(
            title_text=lane["unit"],
            range=_lane_y_range(histories, lane),
            autorange=False,
            row=lane["row"],
            col=lane["col"],
        )
        if lane["row"] == data_rows:
            figure.update_xaxes(
                title_text="Relative hour from recipe switch",
                row=lane["row"],
                col=lane["col"],
            )

    figure_height = 680 if not include_event_rail else (930 if layout_name == "overview" else 760)
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor=PANEL_BACKGROUND,
        plot_bgcolor="#ffffff",
        font={"family": "Segoe UI, Arial, sans-serif", "size": 11, "color": TEXT_COLOR},
        height=None if responsive_height else figure_height,
        autosize=responsive_height,
        margin={"l": 64, "r": 24, "t": 78, "b": 55},
        hovermode="x unified",
        dragmode="zoom",
        uirevision="transition-workspace-v1",
        modebar={"orientation": "v"},
        showlegend=not simplified,
    )
    _position_legends(figure, lanes, include_event_rail)
    return figure


def export_vlm_png(figure: go.Figure, destination: Path, width: int = 1600, height: int = 1000) -> Path:
    """Export a simplified evidence image without affecting browser interactivity."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.write_image(destination, width=width, height=height, scale=1)
    return destination
