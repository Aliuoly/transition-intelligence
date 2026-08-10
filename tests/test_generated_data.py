import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_generated_transition_contract() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    metadata = json.loads((ROOT / "data/transition_metadata.json").read_text())["transitions"]
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())

    assert transitions["transition_id"].nunique() == 6
    assert transitions.groupby("direction")["transition_id"].nunique().to_dict() == {
        "1630 → 2210": 3,
        "2210 → 1630": 3,
    }
    assert len(metadata) == 6
    high = transitions["pressure_high_limit_kpa"].iloc[0]
    low = transitions["pressure_low_limit_kpa"].iloc[0]
    assert transitions.groupby("direction")["total_pressure_kpa"].max()["2210 → 1630"] >= high - 5
    assert (
        transitions.groupby("direction")["total_pressure_kpa"].min()["1630 → 2210"]
        <= low + generation_args["vent_close_margin_kpa"] + 5
    )
    assert (
        transitions.groupby("direction")["transition_id"]
        .apply(
            lambda ids: transitions[transitions["transition_id"].isin(ids)][
                "total_pressure_kpa"
            ].nunique()
        )
        .min()
        > 1
    )


def test_lab_values_are_sparse_and_sample_aligned() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    labs = transitions.dropna(subset=["lab_density_kg_m3", "lab_mfr_g_10min"])

    assert not labs.empty
    assert len(labs) < len(transitions) / 10
    sample_minutes = pd.to_datetime(labs["timestamp"], utc=True).dt.minute
    assert set(sample_minutes).issubset({0})


def test_prior_day_lab_baseline_and_operating_limits_are_exported() -> None:
    labs = pd.read_csv(ROOT / "data/pretransition_lab_samples.csv")
    limits = json.loads((ROOT / "data/operating_limits.json").read_text())
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())

    assert labs.groupby("transition_id").size().eq(12).all()
    assert labs["relative_hour"].between(-24.0, 0.0, inclusive="left").all()
    assert labs["density_error_kg_m3"].std() > 0.15
    assert labs["mfr_error_g_10min"].abs().max() > 0.05
    assert limits["actuators"]["vent"]["limit"] == generation_args["vent_max_kg_h"]
    assert limits["actuators"]["comonomer"]["limit"] == 7000.0
    assert limits["actuators"]["hydrogen"]["limit"] == 20.0


def test_composition_requested_and_constrained_setpoints_are_exported() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")

    assert {
        "comonomer_mole_ratio_sp_request",
        "comonomer_mole_ratio_sp",
        "hydrogen_mole_ratio_sp_request",
        "hydrogen_mole_ratio_sp",
    }.issubset(transitions.columns)


def test_vent_is_mass_flow_and_bounded() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())

    assert "vent_flow_kg_h" in transitions
    assert transitions["vent_flow_kg_h"].between(0.0, 1000.0).all()
    assert transitions["vent_requested_kg_h"].max() == 1000.0
    high_side = transitions[transitions["direction"] == "2210 → 1630"]
    high_crossings = high_side.groupby("transition_id")["total_pressure_kpa"].max().ge(
        transitions["pressure_high_limit_kpa"].iloc[0]
    )
    high_vent_max = high_side.groupby("transition_id")["vent_flow_kg_h"].max()
    assert high_vent_max[high_crossings].eq(1000.0).all()
    assert high_side["vent_high_pressure_override_active"].any()
    expected_hydrogen_demand = (
        transitions["hydrogen_mole_ratio_error"] > generation_args["vent_hydrogen_error_threshold"]
    )
    assert transitions["vent_hydrogen_error_demand_active"].eq(expected_hydrogen_demand).all()
    automatic_requests = transitions[
        transitions["vent_hydrogen_error_demand_active"]
        & ~transitions["vent_high_pressure_override_active"]
    ]
    assert not automatic_requests.empty
    assert automatic_requests["vent_requested_kg_h"].eq(1000.0).all()


def test_hydrogen_feed_respects_limit() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())

    assert transitions["hydrogen_feed_kg_h"].between(
        0.0, generation_args["hydrogen_flow_max_kg_h"] + 0.01
    ).all()
    assert transitions["hydrogen_feed_kg_h"].max() >= (
        0.98 * generation_args["hydrogen_flow_max_kg_h"]
    )


def test_efficiency_and_nitrogen_follow_generation_contract() -> None:
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())
    metadata = json.loads((ROOT / "data/transition_metadata.json").read_text())["transitions"]

    lower, upper = generation_args["pds_efficiency_bounds"]
    assert transitions["discharge_efficiency"].between(lower, upper).all()
    deviation = generation_args["pds_efficiency_max_deviation_fraction"]
    relative_error = (
        transitions["discharge_efficiency"] / transitions["discharge_efficiency_mean"] - 1.0
    )
    assert relative_error.abs().le(deviation + 1e-6).all()
    assert transitions["discharge_efficiency"].eq(0.80).all()
    assert transitions["discharge_efficiency_mean"].eq(0.80).all()
    poison_lower, poison_upper = generation_args["poison_bounds_g_h"]
    assert transitions["poison_feed_g_h"].between(poison_lower, poison_upper).all()
    assert transitions["poison_feed_g_h"].nunique() > 100
    assert transitions.groupby("transition_id")["poison_feed_mean_g_h"].first().nunique() == 6
    site_low, site_high = generation_args["catalyst_site1_fraction_range"]
    assert transitions["catalyst_site1_fraction"].between(site_low, site_high).all()
    assert (
        transitions.groupby("transition_id")["catalyst_site1_fraction"].first().nunique()
        == 6
    )
    assert transitions["relative_hour"].min() == -2.0
    preconditioning = transitions[transitions["nitrogen_preconditioning_active"]]
    automatic = transitions[~transitions["nitrogen_preconditioning_active"]]
    assert preconditioning.empty
    assert (
        automatic["nitrogen_feed_kg_h"]
        .between(
            generation_args["nitrogen_flow_min_kg_h"] - 0.01,
            generation_args["nitrogen_flow_max_kg_h"] + 0.01,
        )
        .all()
    )
    assert transitions["nitrogen_feed_kg_h"].nunique() > 100

    targets = pd.Series(
        [item["perturbations"]["pressure_precondition_target_kpa"] for item in metadata]
    )
    actual = pd.Series([item["baseline_pressure_kpa"] for item in metadata])
    target_low, target_high = generation_args["pressure_precondition_target_range_kpa"]
    assert targets.min() == target_low
    assert targets.max() == target_high
    assert (actual - targets).abs().lt(15.0).all()


def test_pretransition_operating_contexts_are_distinct() -> None:
    metadata = json.loads((ROOT / "data/transition_metadata.json").read_text())["transitions"]
    baseline = pd.DataFrame(metadata)
    baseline["direction"] = baseline["start_recipe"] + " → " + baseline["end_recipe"]
    within_direction_ranges = baseline.groupby("direction")[
        [
            "baseline_pressure_kpa",
            "baseline_catalyst_feed_kg_h",
            "discharge_efficiency_at_start",
            "poison_feed_g_h_at_start",
        ]
    ].agg(lambda values: values.max() - values.min())

    assert within_direction_ranges["baseline_pressure_kpa"].gt(100.0).all()
    assert within_direction_ranges["baseline_catalyst_feed_kg_h"].max() > 0.05
    assert baseline["discharge_efficiency_at_start"].eq(0.80).all()
    assert within_direction_ranges["poison_feed_g_h_at_start"].gt(5.0).all()
