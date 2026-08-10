"""Aggregate matched baseline/candidate campaigns for the final optimization check."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compare_optimization import transition_metrics

from components.data import load_repository


def source_grade_compliant(data_dir: Path) -> bool:
    repository = load_repository(data_dir)
    frame = repository.histories[
        repository.histories["direction"].eq("1630 → 2210")
        & repository.histories["relative_hour"].lt(0.0)
    ]
    return bool(
        (
            frame["predicted_density_kg_m3"].between(917.0, 919.0)
            & frame["predicted_mfr_g_10min"].between(2.65, 3.35)
        ).all()
    )


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

    rows: list[pd.DataFrame] = []
    compliance: dict[str, bool] = {}
    for label, baseline_dir, candidate_dir in args.pair:
        baseline_path = Path(baseline_dir)
        candidate_path = Path(candidate_dir)
        baseline = transition_metrics(load_repository(baseline_path)).add_prefix("baseline_")
        candidate = transition_metrics(load_repository(candidate_path)).add_prefix("candidate_")
        comparison = baseline.join(candidate)
        comparison.insert(0, "seed", label)
        for metric in transition_metrics(load_repository(baseline_path)).columns:
            comparison[f"change_{metric}"] = (
                comparison[f"candidate_{metric}"] - comparison[f"baseline_{metric}"]
            )
        rows.append(comparison.reset_index())
        compliance[label] = source_grade_compliant(candidate_path)

    combined = pd.concat(rows, ignore_index=True)
    acceptance = {
        "all_source_grade_pretransition_samples_compliant": all(compliance.values()),
        "no_low_pressure_exposure": bool(
            combined["candidate_hours_below_low_limit"].eq(0.0).all()
        ),
        "minimum_pressure_at_least_2105_kpa": bool(
            combined["candidate_minimum_pressure_kpa"].min() >= 2105.0
        ),
        "every_case_reduces_transition_resin": bool(
            combined["change_transition_resin_t"].lt(0.0).all()
        ),
    }
    summary = {
        "runs_per_case": len(combined),
        "mean_duration_h": {
            "baseline": round(float(combined["baseline_duration_h"].mean()), 4),
            "candidate": round(float(combined["candidate_duration_h"].mean()), 4),
            "change": round(float(combined["change_duration_h"].mean()), 4),
        },
        "mean_transition_resin_t": {
            "baseline": round(float(combined["baseline_transition_resin_t"].mean()), 4),
            "candidate": round(float(combined["candidate_transition_resin_t"].mean()), 4),
            "change": round(float(combined["change_transition_resin_t"].mean()), 4),
        },
        "candidate_worst_case": {
            "duration_h": round(float(combined["candidate_duration_h"].max()), 4),
            "transition_resin_t": round(
                float(combined["candidate_transition_resin_t"].max()), 4
            ),
            "minimum_pressure_kpa": round(
                float(combined["candidate_minimum_pressure_kpa"].min()), 4
            ),
            "vented_hours": round(float(combined["candidate_vented_hours"].max()), 4),
        },
        "acceptance": acceptance,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.output_dir / "robustness_comparison.csv", index=False)
    (args.output_dir / "robustness_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))
    if not all(acceptance.values()):
        raise SystemExit("Final candidate failed one or more acceptance checks")


if __name__ == "__main__":
    main()
