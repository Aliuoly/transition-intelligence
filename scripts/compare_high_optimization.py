"""Validate and visualize the final 2210-to-1630 optimization candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.data import TransitionRepository, load_repository


def transition_rows(
    label: str,
    baseline: TransitionRepository,
    candidate: TransitionRepository,
) -> list[dict[str, float | str | bool]]:
    rows: list[dict[str, float | str | bool]] = []
    for transition_id in baseline.transition_ids("2210", "1630"):
        baseline_event = baseline.events_by_id[transition_id]
        candidate_event = candidate.events_by_id[transition_id]
        baseline_frame = baseline.histories[
            baseline.histories["transition_id"].eq(transition_id)
            & baseline.histories["relative_hour"].between(0.0, baseline_event["end_hour"])
        ]
        candidate_frame = candidate.histories[
            candidate.histories["transition_id"].eq(transition_id)
            & candidate.histories["relative_hour"].between(0.0, candidate_event["end_hour"])
        ]
        baseline_dt = float(baseline_frame["relative_hour"].diff().median())
        candidate_dt = float(candidate_frame["relative_hour"].diff().median())
        perturbations = candidate.metadata_by_id[transition_id]["perturbations"]
        rows.append(
            {
                "seed": label,
                "transition_id": transition_id,
                "ramp_active": perturbations["comonomer_sp_ramp_rate_per_h"] > 0.0,
                "baseline_duration_h": float(baseline_event["end_hour"]),
                "candidate_duration_h": float(candidate_event["end_hour"]),
                "baseline_transition_resin_t": baseline.transition_volume_t(transition_id),
                "candidate_transition_resin_t": candidate.transition_volume_t(transition_id),
                "baseline_maximum_pressure_kpa": float(
                    baseline_frame["total_pressure_kpa"].max()
                ),
                "candidate_maximum_pressure_kpa": float(
                    candidate_frame["total_pressure_kpa"].max()
                ),
                "baseline_vented_hours": float(
                    baseline_frame["vent_flow_kg_h"].gt(0.0).sum() * baseline_dt
                ),
                "candidate_vented_hours": float(
                    candidate_frame["vent_flow_kg_h"].gt(0.0).sum() * candidate_dt
                ),
            }
        )
    return rows


def control_contract_passes(candidate: TransitionRepository) -> bool:
    histories = candidate.histories[candidate.histories["direction"].eq("2210 → 1630")]
    pre_switch = histories[histories["relative_hour"].lt(0.0)].groupby(
        "transition_id"
    ).tail(1)
    post_switch = histories[histories["relative_hour"].ge(0.0)].groupby(
        "transition_id"
    ).head(1)
    property_targets_step = bool(
        pre_switch["density_supervisory_target_kg_m3"].eq(920.0).all()
        and post_switch["density_supervisory_target_kg_m3"].eq(918.0).all()
        and pre_switch["mfr_supervisory_target_g_10min"].eq(1.0).all()
        and post_switch["mfr_supervisory_target_g_10min"].eq(3.0).all()
    )
    hydrogen_unlimited = bool(
        (
            histories["hydrogen_mole_ratio_sp_request"]
            - histories["hydrogen_mole_ratio_sp"]
        )
        .abs()
        .lt(1e-9)
        .all()
    )
    comonomer_contract = True
    for transition_id, frame in histories[histories["relative_hour"].ge(0.0)].groupby(
        "transition_id"
    ):
        active = (
            candidate.metadata_by_id[transition_id]["perturbations"][
                "comonomer_sp_ramp_rate_per_h"
            ]
            > 0.0
        )
        request_difference = (
            frame["comonomer_mole_ratio_sp_request"] - frame["comonomer_mole_ratio_sp"]
        ).abs()
        working_rate = (
            frame["comonomer_mole_ratio_sp"].diff() / frame["relative_hour"].diff()
        ).abs()
        if active:
            comonomer_contract &= bool(
                request_difference.max() > 0.01 and working_rate.max() <= 0.02002
            )
        else:
            comonomer_contract &= bool(request_difference.max() < 1e-9)
    return property_targets_step and hydrogen_unlimited and comonomer_contract


def plot_comparison(
    baseline: TransitionRepository,
    candidate: TransitionRepository,
    output_path: Path,
) -> None:
    figure, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    colors = {"TR-01": "#2a6f97", "TR-03": "#ca6702", "TR-05": "#6a4c93"}
    variables = (
        ("total_pressure_kpa", "Total pressure [kPa]"),
        ("predicted_density_kg_m3", "Predicted density [kg/m³]"),
        ("predicted_mfr_g_10min", "Predicted MFR [g/10 min]"),
    )
    for transition_id in baseline.transition_ids("2210", "1630"):
        for repository, style, suffix in (
            (baseline, "--", "baseline"),
            (candidate, "-", "candidate"),
        ):
            frame = repository.histories[
                repository.histories["transition_id"].eq(transition_id)
                & repository.histories["relative_hour"].between(0.0, 7.0)
            ]
            for axis, (column, ylabel) in zip(axes[:3], variables, strict=True):
                axis.plot(
                    frame["relative_hour"],
                    frame[column],
                    linestyle=style,
                    color=colors[transition_id],
                    linewidth=1.8,
                    label=f"{transition_id} {suffix}" if axis is axes[0] else None,
                )
                axis.set_ylabel(ylabel)
                axis.grid(alpha=0.2)
        candidate_frame = candidate.histories[
            candidate.histories["transition_id"].eq(transition_id)
            & candidate.histories["relative_hour"].between(0.0, 7.0)
        ]
        axes[3].plot(
            candidate_frame["relative_hour"],
            candidate_frame["comonomer_mole_ratio_sp_request"],
            linestyle="--",
            color=colors[transition_id],
            alpha=0.65,
            label=f"{transition_id} APC request",
        )
        axes[3].plot(
            candidate_frame["relative_hour"],
            candidate_frame["comonomer_mole_ratio_sp"],
            color=colors[transition_id],
            linewidth=2.0,
            label=f"{transition_id} rM2 working SP",
        )
    axes[0].axhspan(2100.0, 2300.0, color="#75a478", alpha=0.12)
    axes[1].axhspan(917.0, 919.0, color="#75a478", alpha=0.12)
    axes[2].axhspan(2.65, 3.35, color="#75a478", alpha=0.12)
    axes[0].legend(ncol=3, fontsize=8, loc="upper right")
    axes[3].set_ylabel("Comonomer ratio SP [mol/mol]")
    axes[3].set_xlabel("Hours after recipe switch")
    axes[3].grid(alpha=0.2)
    axes[3].legend(ncol=3, fontsize=8, loc="lower right")
    figure.suptitle("Final candidate versus historical baseline — 2210 → 1630")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair",
        action="append",
        nargs=3,
        metavar=("LABEL", "BASELINE_DIR", "CANDIDATE_DIR"),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows: list[dict[str, float | str | bool]] = []
    contracts: list[bool] = []
    plot_pair: tuple[TransitionRepository, TransitionRepository] | None = None
    for label, baseline_dir, candidate_dir in args.pair:
        baseline = load_repository(Path(baseline_dir))
        candidate = load_repository(Path(candidate_dir))
        rows.extend(transition_rows(label, baseline, candidate))
        contracts.append(control_contract_passes(candidate))
        if plot_pair is None:
            plot_pair = (baseline, candidate)

    comparison = pd.DataFrame(rows)
    comparison["change_duration_h"] = (
        comparison["candidate_duration_h"] - comparison["baseline_duration_h"]
    )
    comparison["change_transition_resin_t"] = (
        comparison["candidate_transition_resin_t"]
        - comparison["baseline_transition_resin_t"]
    )
    acceptance = {
        "control_layer_contract_passes": all(contracts),
        "no_candidate_high_pressure_exposure": bool(
            comparison["candidate_maximum_pressure_kpa"].lt(2300.0).all()
        ),
        "no_candidate_venting": bool(comparison["candidate_vented_hours"].eq(0.0).all()),
        "no_case_increases_duration": bool(comparison["change_duration_h"].le(0.001).all()),
        "no_case_materially_increases_resin": bool(
            comparison["change_transition_resin_t"].le(0.05).all()
        ),
        "every_active_case_reduces_resin": bool(
            comparison.loc[comparison["ramp_active"], "change_transition_resin_t"].lt(0.0).all()
        ),
    }
    active = comparison[comparison["ramp_active"]]
    summary = {
        "matched_runs": len(comparison),
        "active_runs": len(active),
        "all_runs_mean": {
            "baseline_duration_h": round(float(comparison["baseline_duration_h"].mean()), 4),
            "candidate_duration_h": round(float(comparison["candidate_duration_h"].mean()), 4),
            "baseline_transition_resin_t": round(
                float(comparison["baseline_transition_resin_t"].mean()), 4
            ),
            "candidate_transition_resin_t": round(
                float(comparison["candidate_transition_resin_t"].mean()), 4
            ),
        },
        "active_runs_mean": {
            "baseline_duration_h": round(float(active["baseline_duration_h"].mean()), 4),
            "candidate_duration_h": round(float(active["candidate_duration_h"].mean()), 4),
            "baseline_transition_resin_t": round(
                float(active["baseline_transition_resin_t"].mean()), 4
            ),
            "candidate_transition_resin_t": round(
                float(active["candidate_transition_resin_t"].mean()), 4
            ),
        },
        "candidate_maximum_pressure_kpa": round(
            float(comparison["candidate_maximum_pressure_kpa"].max()), 4
        ),
        "acceptance": acceptance,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.output_dir / "robustness_comparison.csv", index=False)
    (args.output_dir / "robustness_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    assert plot_pair is not None
    plot_comparison(*plot_pair, args.output_dir / "trajectory_comparison.png")
    print(json.dumps(summary, indent=2))
    if not all(acceptance.values()):
        raise SystemExit("Final candidate failed one or more acceptance checks")


if __name__ == "__main__":
    main()
