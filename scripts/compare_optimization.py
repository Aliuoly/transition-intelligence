"""Compare baseline and candidate low-pressure transition trajectories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.data import TransitionRepository, load_repository

DIRECTION = "1630 → 2210"


def transition_metrics(repository: TransitionRepository) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for transition_id in repository.transition_ids("1630", "2210"):
        frame = repository.histories[
            (repository.histories["transition_id"] == transition_id)
            & (repository.histories["relative_hour"] >= 0.0)
        ].copy()
        event = repository.events_by_id[transition_id]
        frame = frame[frame["relative_hour"] <= float(event["end_hour"])]
        sample_hours = float(frame["relative_hour"].diff().median())
        rows.append(
            {
                "transition_id": transition_id,
                "duration_h": float(event["end_hour"]),
                "transition_resin_t": repository.transition_volume_t(transition_id),
                "minimum_pressure_kpa": float(frame["total_pressure_kpa"].min()),
                "hours_below_low_limit": float(
                    (frame["total_pressure_kpa"] < frame["pressure_low_limit_kpa"]).sum()
                    * sample_hours
                ),
                "vented_hours": float((frame["vent_flow_kg_h"] > 0.0).sum() * sample_hours),
            }
        )
    return pd.DataFrame(rows).set_index("transition_id")


def plot_trajectories(
    baseline: TransitionRepository,
    candidate: TransitionRepository,
    output_path: Path,
) -> None:
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    variables = (
        ("total_pressure_kpa", "Total pressure [kPa]"),
        ("predicted_density_kg_m3", "Predicted density [kg/m³]"),
        ("predicted_mfr_g_10min", "Predicted MFR [g/10 min]"),
    )
    colors = {"TR-02": "#2a6f97", "TR-04": "#ca6702", "TR-06": "#6a4c93"}
    for transition_id in baseline.transition_ids("1630", "2210"):
        for repository, style, label_suffix in (
            (baseline, "--", "baseline"),
            (candidate, "-", "candidate"),
        ):
            frame = repository.histories[
                repository.histories["transition_id"].eq(transition_id)
                & repository.histories["relative_hour"].between(0.0, 11.5)
            ]
            for axis, (column, ylabel) in zip(axes, variables, strict=True):
                axis.plot(
                    frame["relative_hour"],
                    frame[column],
                    linestyle=style,
                    color=colors[transition_id],
                    linewidth=1.8,
                    alpha=0.9,
                    label=f"{transition_id} {label_suffix}" if axis is axes[0] else None,
                )
                axis.set_ylabel(ylabel)
                axis.grid(alpha=0.2)
    axes[0].axhspan(2100.0, 2300.0, color="#75a478", alpha=0.12)
    axes[1].axhspan(919.0, 921.0, color="#75a478", alpha=0.12)
    axes[2].axhspan(0.82, 1.18, color="#75a478", alpha=0.12)
    axes[0].legend(ncol=3, fontsize=8, loc="upper right")
    axes[-1].set_xlabel("Hours after recipe switch")
    figure.suptitle("Agent candidate versus historical baseline — 1630 → 2210")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "data")
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    baseline = load_repository(args.baseline)
    candidate = load_repository(args.candidate)
    baseline_metrics = transition_metrics(baseline)
    candidate_metrics = transition_metrics(candidate)
    comparison = pd.concat(
        {"baseline": baseline_metrics, "candidate": candidate_metrics}, axis=1
    )
    for metric in baseline_metrics.columns:
        comparison[("change", metric)] = candidate_metrics[metric] - baseline_metrics[metric]
        denominator = baseline_metrics[metric].replace(0.0, np.nan)
        comparison[("change_percent", metric)] = (
            100.0 * (candidate_metrics[metric] - baseline_metrics[metric]) / denominator
        )
    comparison = comparison.sort_index(axis=1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(args.output_dir / "comparison.csv", float_format="%.4f")
    aggregate = {
        metric: {
            "baseline_mean": round(float(baseline_metrics[metric].mean()), 4),
            "candidate_mean": round(float(candidate_metrics[metric].mean()), 4),
            "change": round(
                float(candidate_metrics[metric].mean() - baseline_metrics[metric].mean()), 4
            ),
        }
        for metric in baseline_metrics.columns
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps({"direction": DIRECTION, "mean_metrics": aggregate}, indent=2) + "\n"
    )
    plot_trajectories(
        baseline,
        candidate,
        args.output_dir / "trajectory_comparison.png",
    )
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
