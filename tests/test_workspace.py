import pytest

from components.data import load_repository
from components.trends import LANES, _lane_y_range, build_transition_figure


def test_overview_contains_nine_lanes_and_dynamic_time_window() -> None:
    repository = load_repository()
    figure = build_transition_figure(repository, ["TR-01", "TR-03", "TR-05"], "TR-05")

    subplot_titles = {annotation.text for annotation in figure.layout.annotations}
    assert {
        "Total pressure",
        "Ethylene partial pressure",
        "Reactor vent flow",
        "Density",
        "Comonomer mole ratio",
        "FM2 comonomer feed",
        "MFR (melt flow rate)",
        "Hydrogen mole ratio",
        "Hydrogen feed",
    }.issubset(subplot_titles)
    assert tuple(figure.layout.xaxis.range) == (-2.0, 7.567)
    assert {
        tuple(figure.get_subplot(row, col).xaxis.range)
        for row in range(2, 5)
        for col in range(1, 4)
    } == {(-2.0, 7.567)}
    assert figure.layout.hovermode == "x unified"
    assert figure.layout.dragmode == "zoom"
    assert any(annotation.text == "TR-05 start · 0.0 h " for annotation in figure.layout.annotations)
    assert any("TR-05 end" in annotation.text and "272 t" in annotation.text for annotation in figure.layout.annotations)
    assert figure.get_subplot(2, 1).xaxis.plotly_name == "xaxis2"
    assert figure.get_subplot(2, 2).xaxis.plotly_name == "xaxis3"
    assert figure.get_subplot(2, 3).xaxis.plotly_name == "xaxis4"


def test_overview_adds_flow_evidence_bands_and_subplot_legends() -> None:
    repository = load_repository()
    figure = build_transition_figure(repository, ["TR-01", "TR-03", "TR-05"], "TR-05")

    tags = {(trace.meta or {}).get("tag") for trace in figure.data}
    assert "Reactor vent flow" in tags
    assert "FM2 feed" in tags
    assert "H2 feed" in tags
    assert sum(trace.name == "Target range" and trace.fill == "tonexty" for trace in figure.data) == 2
    assert any(trace.name == "Pressure range" and trace.fill == "tonexty" for trace in figure.data)
    vent = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "Reactor vent flow"}
    )
    fm2 = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "FM2 feed"}
    )
    hydrogen = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "H2 feed"}
    )
    pressure = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "Reactor pressure"}
    )
    density = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "Inferred density"}
    )
    mfr = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-05", "tag": "Inferred MFR"}
    )
    assert vent.yaxis != pressure.yaxis
    assert fm2.yaxis != density.yaxis
    assert hydrogen.yaxis != mfr.yaxis
    for legend_name in (
        "legend",
        "legend2",
        "legend3",
        "legend4",
        "legend5",
        "legend6",
        "legend7",
        "legend8",
        "legend9",
    ):
        legend = getattr(figure.layout, legend_name)
        assert 0.0 <= legend.x <= 1.0
        assert 0.0 <= legend.y <= 1.0
        assert legend.orientation == "v"
        assert legend.xanchor == "right"

    timing_legend = figure.layout.legend10
    assert timing_legend.orientation == "h"
    assert timing_legend.groupclick == "togglegroup"
    timing_items = [trace for trace in figure.data if trace.legend == "legend10"]
    assert [trace.name for trace in timing_items] == ["TR-01", "TR-03", "TR-05"]
    assert all(trace.showlegend for trace in timing_items)
    lane_transition_items = [
        trace
        for trace in figure.data
        if (trace.meta or {}).get("transition_id") in {"TR-01", "TR-03", "TR-05"}
        and not str(trace.legendgroup).startswith("reference-")
        and trace.showlegend
    ]
    assert {trace.legendgroup for trace in lane_transition_items} == {
        "pressure-total_pressure_kpa",
        "ethylene-ethylene_partial_pressure_kpa",
        "vent-vent_flow_kg_h",
        "density-predicted_density_kg_m3",
        "density-lab_density_kg_m3",
        "comonomer-comonomer_mole_ratio",
        "fm2_feed-comonomer_feed_kg_h",
        "mfr-predicted_mfr_g_10min",
        "mfr-lab_mfr_g_10min",
        "hydrogen-hydrogen_mole_ratio",
        "hydrogen_feed-hydrogen_feed_kg_h",
    }
    assert {trace.name for trace in lane_transition_items} == {
        "Reactor pressure",
        "C2 partial pressure",
        "Reactor vent flow",
        "Inferred density",
        "Lab density",
        "FM2/C2 mol ratio",
        "FM2 feed",
        "Inferred MFR",
        "Lab MFR",
        "H2/C2 mol ratio",
        "H2 feed",
    }
    assert {trace.meta["transition_id"] for trace in lane_transition_items} == {"TR-05"}

    limit_traces = [trace for trace in figure.data if "Actuator limit" in (trace.name or "")]
    assert {trace.meta["tag"] for trace in limit_traces} == {
        "Vent flow actuator limit",
        "FM2 feed actuator limit",
        "Hydrogen feed actuator limit",
    }
    requested = [trace for trace in figure.data if trace.name == "APC requested SP"]
    constrained = [trace for trace in figure.data if trace.name == "Constrained working SP"]
    assert len(requested) == len(constrained) == 2
    saturation_shapes = [
        shape
        for shape in figure.layout.shapes
        if shape.fillcolor == "rgba(196, 79, 79, 0.13)"
    ]
    assert saturation_shapes
    assert {shape.yref for shape in saturation_shapes}.issubset(
        {"y8 domain", "y9 domain", "y10 domain"}
    )


def test_actuator_limit_is_excluded_from_lane_y_range() -> None:
    repository = load_repository()
    histories = repository.histories[
        repository.histories["transition_id"].isin(["TR-01", "TR-03", "TR-05"])
    ]
    fm2_lane = next(lane for lane in LANES if lane["key"] == "fm2_feed")

    lower, upper = _lane_y_range(histories, fm2_lane)

    assert lower >= 0.0
    assert upper < repository.operating_limits["actuators"]["comonomer"]["limit"]


@pytest.mark.parametrize(
    ("transition_id", "old_density", "new_density", "old_mfr", "new_mfr"),
    [
        ("TR-01", 920.0, 918.0, 1.0, 3.0),
        ("TR-04", 918.0, 920.0, 3.0, 1.0),
    ],
)
def test_property_targets_switch_from_source_to_destination_at_zero(
    transition_id: str,
    old_density: float,
    new_density: float,
    old_mfr: float,
    new_mfr: float,
) -> None:
    repository = load_repository()
    frame = repository.histories[repository.histories["transition_id"] == transition_id]
    before = frame[frame["relative_hour"] < 0.0]
    after = frame[frame["relative_hour"] >= 0.0]

    assert set(before["density_target_kg_m3"]) == {old_density}
    assert set(after["density_target_kg_m3"]) == {new_density}
    assert set(before["mfr_target_g_10min"]) == {old_mfr}
    assert set(after["mfr_target_g_10min"]) == {new_mfr}
    assert set(before["density_low_limit_kg_m3"]) == {old_density - 1.0}
    assert set(after["density_low_limit_kg_m3"]) == {new_density - 1.0}


def test_transition_volume_integrates_switch_to_end_production() -> None:
    repository = load_repository()

    assert repository.transition_volume_t("TR-01") == pytest.approx(263.35, abs=0.02)
    assert repository.transition_volume_t("TR-04") == pytest.approx(416.85, abs=0.02)


def test_lab_traces_keep_sparse_sample_timestamps() -> None:
    repository = load_repository()
    figure = build_transition_figure(repository, ["TR-04"], "TR-04")
    source = repository.histories[repository.histories["transition_id"] == "TR-04"]

    density_trace = next(trace for trace in figure.data if trace.name == "Lab density")
    mfr_trace = next(trace for trace in figure.data if trace.name == "Lab MFR")
    assert list(density_trace.x) == list(source.loc[source["lab_density_kg_m3"].notna(), "relative_hour"])
    assert list(mfr_trace.x) == list(source.loc[source["lab_mfr_g_10min"].notna(), "relative_hour"])
    assert density_trace.mode == "markers"
    assert mfr_trace.mode == "markers"


def test_focal_run_is_emphasized_and_focus_layout_is_available() -> None:
    repository = load_repository()
    figure = build_transition_figure(
        repository,
        ["TR-02", "TR-04", "TR-06"],
        "TR-04",
        (-1.0, 5.0),
        "pressure_vent",
    )

    focal = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-04", "tag": "Reactor pressure"}
    )
    peer = next(
        trace
        for trace in figure.data
        if trace.meta == {"transition_id": "TR-02", "tag": "Reactor pressure"}
    )
    assert focal.opacity == 1.0
    assert peer.opacity < focal.opacity
    assert tuple(figure.layout.xaxis.range) == (-1.0, 5.0)
    titles = {annotation.text for annotation in figure.layout.annotations}
    assert "Reactor vent flow" in titles
    assert "Density" not in titles
    assert "MFR (melt flow rate)" not in titles
    assert figure.get_subplot(2, 1).xaxis.plotly_name == "xaxis2"
    assert figure.get_subplot(3, 1).xaxis.plotly_name == "xaxis3"
    assert figure.get_subplot(4, 1).xaxis.plotly_name == "xaxis4"


def test_browser_figure_omits_embedded_event_rail() -> None:
    repository = load_repository()
    figure = build_transition_figure(
        repository,
        ["TR-02", "TR-04", "TR-06"],
        "TR-04",
        include_event_rail=False,
    )

    titles = {annotation.text for annotation in figure.layout.annotations}
    assert "Transition timing + resin volume" not in titles
    assert "Total pressure" in titles
    assert not any(" start · " in annotation.text for annotation in figure.layout.annotations)
    assert figure.get_subplot(1, 1).xaxis.plotly_name == "xaxis"
    assert figure.get_subplot(3, 3).xaxis.plotly_name == "xaxis9"
    assert "legend10" not in figure.layout.to_plotly_json()
    assert figure.layout.height == 680
