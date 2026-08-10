"""Render transition capsules using the gas-phase example's native 4x3 layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _finish_axis(axis: plt.Axes, title: str, ylabel: str) -> None:
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.25)


def _merge_legends(axis: plt.Axes, twin: plt.Axes) -> None:
    handles, labels = axis.get_legend_handles_labels()
    twin_handles, twin_labels = twin.get_legend_handles_labels()
    axis.legend(handles + twin_handles, labels + twin_labels, loc="best")


def render_transition(frame: pd.DataFrame, output_path: Path) -> None:
    transition_id = str(frame["transition_id"].iloc[0])
    direction = str(frame["direction"].iloc[0])
    x = frame["relative_hour"]
    fig, axes_grid = plt.subplots(4, 3, figsize=(20, 18), sharex=True)
    axes = axes_grid.flatten()

    ax = axes[0]
    ax.plot(x, frame["ethylene_feed_kg_h"], label="F_m1")
    twin = ax.twinx()
    twin.plot(x, frame["ethylene_partial_pressure_kpa"], color="tab:orange", label="pM1")
    twin.plot(
        x,
        frame["ethylene_partial_pressure_sp_kpa"],
        color="tab:red",
        linestyle="--",
        label="SP pM1",
    )
    _finish_axis(ax, "F_m1 vs pM1", "F_m1 [kg/h]")
    twin.set_ylabel("pM1 [kPa]")
    _merge_legends(ax, twin)

    for ax, feed, ratio, ratio_sp, title, ratio_label in (
        (
            axes[1],
            "comonomer_feed_kg_h",
            "comonomer_mole_ratio",
            "comonomer_mole_ratio_sp",
            "F_m2 vs rM2",
            "rM2",
        ),
        (
            axes[2],
            "hydrogen_feed_kg_h",
            "hydrogen_mole_ratio",
            "hydrogen_mole_ratio_sp",
            "F_h2 vs rH2",
            "rH2",
        ),
    ):
        ax.plot(x, frame[feed], label=feed.split("_")[0])
        twin = ax.twinx()
        twin.plot(x, frame[ratio], color="tab:orange", label=ratio_label)
        twin.plot(x, frame[ratio_sp], color="tab:red", linestyle="--", label=f"SP {ratio_label}")
        _finish_axis(ax, title, f"{feed.split('_')[0]} [kg/h]")
        twin.set_ylabel(ratio_label)
        _merge_legends(ax, twin)

    ax = axes[3]
    ax.plot(x, frame["production_rate_t_h"], label="Production rate")
    twin = ax.twinx()
    twin.plot(x, frame["catalyst_feed_kg_h"], color="tab:orange", label="F_cat")
    _finish_axis(ax, "Production Rate vs F_cat", "Production [t/h]")
    twin.set_ylabel("F_cat [kg/h]")
    _merge_legends(ax, twin)

    for ax, predicted, lab, target, low, high, title, ylabel in (
        (
            axes[4],
            "predicted_mfr_g_10min",
            "lab_mfr_g_10min",
            "mfr_target_g_10min",
            "mfr_low_limit_g_10min",
            "mfr_high_limit_g_10min",
            "Melt Index",
            "MFR [g/10 min]",
        ),
        (
            axes[5],
            "predicted_density_kg_m3",
            "lab_density_kg_m3",
            "density_target_kg_m3",
            "density_low_limit_kg_m3",
            "density_high_limit_kg_m3",
            "Density",
            "Density [kg/m³]",
        ),
    ):
        ax.plot(x, frame[predicted], color="tab:orange", label="Predicted")
        labs = frame.dropna(subset=[lab])
        ax.scatter(labs["relative_hour"], labs[lab], s=22, label="Lab")
        ax.plot(x, frame[target], color="tab:red", linestyle="--", label="Target")
        ax.plot(x, frame[low], color="0.55", linestyle=":", label="Limits")
        ax.plot(x, frame[high], color="0.55", linestyle=":")
        _finish_axis(ax, title, ylabel)
        ax.legend(loc="best")

    ax = axes[6]
    generation_args = json.loads((ROOT / "data/generation_args.json").read_text())
    ax.plot(
        x,
        frame["hydrogen_mole_ratio_error"],
        color="tab:purple",
        label="rH2 error",
    )
    ax.axhline(
        generation_args["vent_hydrogen_error_threshold"],
        color="tab:red",
        linestyle="--",
        label="Vent threshold",
    )
    _finish_axis(ax, "Hydrogen Error Vent Demand", "rH2 error")
    ax.legend(loc="best")

    ax = axes[7]
    ax.plot(x, frame["total_pressure_kpa"], label="Pressure")
    ax.plot(
        x,
        frame["pressure_control_sp_kpa"],
        color="tab:blue",
        linestyle=":",
        label="N2 PI target",
    )
    ax.plot(x, frame["pressure_low_limit_kpa"], color="tab:red", linestyle="--", label="Low limit")
    ax.plot(
        x, frame["pressure_high_limit_kpa"], color="tab:green", linestyle="--", label="High limit"
    )
    _finish_axis(ax, "Pressure", "Pressure [kPa]")
    ax.legend(loc="best")

    ax = axes[8]
    ax.plot(x, frame["bed_level_m"], label="Bed level")
    twin = ax.twinx()
    twin.plot(x, frame["discharge_valve_position"], color="tab:orange", label="Valve position")
    _finish_axis(ax, "Bed Level vs Discharge Valve", "Bed level [m]")
    twin.set_ylabel("Valve position")
    _merge_legends(ax, twin)

    ax = axes[9]
    ax.plot(x, frame["poison_feed_g_h"], color="tab:purple", label="Poison Feed")
    twin = ax.twinx()
    twin.plot(
        x,
        100.0 * frame["catalyst_site1_fraction"],
        color="tab:brown",
        linestyle="--",
        label="Type-1 sites",
    )
    _finish_axis(ax, "Poison and Catalyst Site Split", "Poison [g/h]")
    twin.set_ylabel("Type-1 catalyst sites [%]")
    _merge_legends(ax, twin)

    ax = axes[10]
    ax.plot(x, frame["nitrogen_feed_kg_h"], color="tab:green", label="Nitrogen Flow")
    _finish_axis(ax, "Nitrogen Flow", "F_n2 [kg/h]")
    ax.legend(loc="best")

    ax = axes[11]
    ax.plot(x, frame["vent_flow_kg_h"], color="tab:red", label="F_vent")
    ax.plot(x, frame["vent_requested_kg_h"], color="black", linestyle="--", label="Requested")
    _finish_axis(ax, "Vent Flow", "F_vent [kg/h]")
    ax.legend(loc="best")

    for ax in axes:
        ax.axvline(0.0, color="0.35", linewidth=0.8, alpha=0.8)
    for ax in axes[9:]:
        ax.set_xlabel("Relative time [h]")

    fig.suptitle(f"{transition_id}: {direction}", fontsize=18)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.975))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transition_ids", nargs="*", default=["TR-01", "TR-02"])
    args = parser.parse_args()
    transitions = pd.read_csv(ROOT / "data/transitions.csv")
    for transition_id in args.transition_ids:
        frame = transitions[transitions["transition_id"] == transition_id]
        if frame.empty:
            raise ValueError(f"Unknown transition ID: {transition_id}")
        render_transition(frame, ROOT / "assets" / f"{transition_id}_native_trends.png")


if __name__ == "__main__":
    main()
