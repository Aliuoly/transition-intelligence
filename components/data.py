"""Read the frozen Stage 1 exports used by the interactive workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROPERTY_SPECS = {
    "2210": {
        "density_target_kg_m3": 920.0,
        "density_low_limit_kg_m3": 919.0,
        "density_high_limit_kg_m3": 921.0,
        "mfr_target_g_10min": 1.0,
        "mfr_low_limit_g_10min": 0.82,
        "mfr_high_limit_g_10min": 1.18,
    },
    "1630": {
        "density_target_kg_m3": 918.0,
        "density_low_limit_kg_m3": 917.0,
        "density_high_limit_kg_m3": 919.0,
        "mfr_target_g_10min": 3.0,
        "mfr_low_limit_g_10min": 2.65,
        "mfr_high_limit_g_10min": 3.35,
    },
}

DEFAULT_OPERATING_LIMITS: dict[str, Any] = {
    "pressure": {"low": 2100.0, "high": 2300.0, "unit": "kPa"},
    "actuators": {
        "vent": {
            "column": "vent_flow_kg_h",
            "label": "Vent flow",
            "limit": 1000.0,
            "unit": "kg/h",
        },
        "comonomer": {
            "column": "comonomer_feed_kg_h",
            "label": "FM2 feed",
            "limit": 7000.0,
            "unit": "kg/h",
        },
        "hydrogen": {
            "column": "hydrogen_feed_kg_h",
            "label": "Hydrogen feed",
            "limit": 20.0,
            "unit": "kg/h",
        },
    },
    "saturation_fraction": 0.98,
}


def _duration_hours(mask: pd.Series, frame: pd.DataFrame) -> float:
    if len(frame) < 2 or not mask.any():
        return 0.0
    sample_hours = float(frame["relative_hour"].diff().median())
    return float(mask.sum() * sample_hours)


def _first_stable_entry(frame: pd.DataFrame, value: str, low: str, high: str) -> float | None:
    after_switch = frame[frame["relative_hour"] >= 0.0]
    if len(after_switch) < 2:
        return None
    sample_hours = float(after_switch["relative_hour"].diff().median())
    required = max(2, round(0.5 / sample_hours) + 1)
    inside = after_switch[value].between(after_switch[low], after_switch[high])
    sustained = inside.rolling(required, min_periods=required).sum().eq(required)
    matches = after_switch.loc[sustained, "relative_hour"]
    return None if matches.empty else float(matches.iloc[0] - 0.5)


def _error_statistics(values: pd.Series) -> dict[str, float | int | None]:
    clean = values.dropna()
    if clean.empty:
        return {"samples": 0, "bias": None, "std": None, "absolute_p95": None}
    return {
        "samples": len(clean),
        "bias": round(float(clean.mean()), 4),
        "std": round(float(clean.std(ddof=1)), 4) if len(clean) > 1 else 0.0,
        "absolute_p95": round(float(clean.abs().quantile(0.95)), 4),
    }


def _event_window(mask: pd.Series, frame: pd.DataFrame) -> tuple[float, float, float] | None:
    """Return first, last, and cumulative hours for a boolean event mask."""
    if len(frame) < 2 or not mask.any():
        return None
    sample_hours = float(frame["relative_hour"].diff().median())
    active = frame.loc[mask, "relative_hour"]
    return (
        round(float(active.iloc[0]), 3),
        round(float(active.iloc[-1]), 3),
        round(float(mask.sum() * sample_hours), 3),
    )


def _event_entry(
    window: tuple[float, float, float],
    event: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "start_hour": window[0],
        "end_hour": window[1],
        "cumulative_hours": window[2],
        "event": event,
        "evidence": evidence,
    }


@dataclass(frozen=True)
class TransitionRepository:
    histories: pd.DataFrame
    metadata: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    operating_limits: dict[str, Any] = field(default_factory=lambda: DEFAULT_OPERATING_LIMITS)
    pretransition_labs: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def metadata_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["transition_id"]: item for item in self.metadata}

    @property
    def events_by_id(self) -> dict[str, dict[str, Any]]:
        return {item["transition_id"]: item for item in self.events}

    def transition_ids(self, start_recipe: str, end_recipe: str) -> list[str]:
        return [
            item["transition_id"]
            for item in self.metadata
            if item["start_recipe"] == start_recipe and item["end_recipe"] == end_recipe
        ]

    def transition_volume_t(self, transition_id: str) -> float:
        """Integrate production rate from recipe switch through transition end."""
        end_hour = self.events_by_id[transition_id]["end_hour"]
        frame = self.histories[
            (self.histories["transition_id"] == transition_id)
            & self.histories["relative_hour"].between(0.0, end_hour)
        ]
        if len(frame) < 2:
            return 0.0
        return float(np.trapezoid(frame["production_rate_t_h"], frame["relative_hour"]))

    def trend_summary(self, transition_id: str) -> dict[str, Any]:
        """Return engineer-visible evidence derived from the plotted histories."""
        if transition_id not in self.metadata_by_id:
            raise ValueError(f"Unknown transition ID: {transition_id}")
        event = self.events_by_id[transition_id]
        full_history = self.histories[
            (self.histories["transition_id"] == transition_id)
            & (self.histories["relative_hour"] >= 0.0)
        ].copy()
        frame = full_history[
            full_history["relative_hour"].between(0.0, event["end_hour"])
        ].copy()
        density_entry = _first_stable_entry(
            full_history,
            "predicted_density_kg_m3",
            "density_low_limit_kg_m3",
            "density_high_limit_kg_m3",
        )
        mfr_entry = _first_stable_entry(
            full_history,
            "predicted_mfr_g_10min",
            "mfr_low_limit_g_10min",
            "mfr_high_limit_g_10min",
        )
        actuator_summary: dict[str, Any] = {}
        threshold_fraction = float(self.operating_limits["saturation_fraction"])
        for key, definition in self.operating_limits["actuators"].items():
            values = frame[definition["column"]]
            saturated = values >= threshold_fraction * float(definition["limit"])
            actuator_summary[key] = {
                "label": definition["label"],
                "limit": definition["limit"],
                "unit": definition["unit"],
                "peak": round(float(values.max()), 3),
                "saturated_hours": round(_duration_hours(saturated, frame), 3),
            }

        setpoints: dict[str, Any] = {}
        for key, requested, constrained in (
            ("comonomer", "comonomer_mole_ratio_sp_request", "comonomer_mole_ratio_sp"),
            ("hydrogen", "hydrogen_mole_ratio_sp_request", "hydrogen_mole_ratio_sp"),
        ):
            if requested not in frame:
                continue
            gap = (frame[requested] - frame[constrained]).abs()
            setpoints[key] = {
                "maximum_request_constraint_gap": round(float(gap.max()), 6),
                "constrained_hours": round(_duration_hours(gap > 1e-6, frame), 3),
            }

        labs = self.pretransition_labs
        labs = labs[labs["transition_id"] == transition_id] if not labs.empty else labs
        lab_summary = {
            "window_hours": 24.0,
            "density_error_kg_m3": _error_statistics(
                labs.get("density_error_kg_m3", pd.Series(dtype=float))
            ),
            "mfr_error_g_10min": _error_statistics(
                labs.get("mfr_error_g_10min", pd.Series(dtype=float))
            ),
        }
        pressure_limits = self.operating_limits["pressure"]
        pressure = frame["total_pressure_kpa"]
        entries = {"density": density_entry, "mfr": mfr_entry}
        available_entries = {key: value for key, value in entries.items() if value is not None}
        limiting_property = (
            max(available_entries, key=available_entries.get) if available_entries else None
        )
        return {
            "transition_id": transition_id,
            "duration_hours": event["end_hour"],
            "transition_resin_t": round(self.transition_volume_t(transition_id), 2),
            "stable_property_entry_hours": entries,
            "limiting_property": limiting_property,
            "pressure": {
                "low_limit_kpa": pressure_limits["low"],
                "high_limit_kpa": pressure_limits["high"],
                "start_kpa": round(float(pressure.iloc[0]), 2),
                "minimum_kpa": round(float(pressure.min()), 2),
                "maximum_kpa": round(float(pressure.max()), 2),
                "below_low_limit_hours": round(
                    _duration_hours(pressure <= pressure_limits["low"], frame), 3
                ),
                "above_high_limit_hours": round(
                    _duration_hours(pressure >= pressure_limits["high"], frame), 3
                ),
            },
            "actuator_limits": actuator_summary,
            "requested_vs_constrained_setpoints": setpoints,
            "pretransition_lab_error_baseline": lab_summary,
        }

    def event_evidence(self, transition_id: str) -> list[dict[str, Any]]:
        """Return neutral, chronological event evidence for agent interpretation."""
        if transition_id not in self.metadata_by_id:
            raise ValueError(f"Unknown transition ID: {transition_id}")

        metadata = self.metadata_by_id[transition_id]
        end_hour = float(self.events_by_id[transition_id]["end_hour"])
        frame = self.histories[
            (self.histories["transition_id"] == transition_id)
            & self.histories["relative_hour"].between(0.0, end_hour)
        ].copy()
        if frame.empty:
            return []

        transcript: list[dict[str, Any]] = [
            _event_entry(
                (0.0, 0.0, 0.0),
                f"Recipe switched from {metadata['start_recipe']} to {metadata['end_recipe']}",
                "Density and MFR targets changed to the destination recipe at t=0.",
            )
        ]
        limits = self.operating_limits
        pressure = frame["total_pressure_kpa"]
        low_limit = float(limits["pressure"]["low"])
        high_limit = float(limits["pressure"]["high"])

        high_window = _event_window(pressure >= high_limit, frame)
        high_override = frame.get(
            "vent_high_pressure_override_active", pd.Series(False, index=frame.index)
        ).astype(bool)
        if high_window is not None:
            override_window = _event_window(high_override, frame)
            override_detail = (
                " The high-pressure vent override activated."
                if override_window is not None
                else ""
            )
            transcript.append(
                _event_entry(
                    high_window,
                    "High-pressure limit excursions",
                    f"Pressure peaked at {pressure.max():.1f} kPa against a {high_limit:.0f} kPa limit.{override_detail}",
                )
            )

        low_window = _event_window(pressure <= low_limit, frame)
        low_override = frame.get(
            "vent_override_active", pd.Series(False, index=frame.index)
        ).astype(bool)
        if low_window is not None:
            inhibit_detail = (
                " Low-pressure override inhibited a hydrogen-removal vent request."
                if low_override.any()
                else ""
            )
            transcript.append(
                _event_entry(
                    low_window,
                    "Low-pressure limit exposure",
                    f"Pressure fell to {pressure.min():.1f} kPa against a {low_limit:.0f} kPa limit.{inhibit_detail}",
                )
            )

        threshold_fraction = float(limits["saturation_fraction"])
        for key in ("comonomer", "hydrogen"):
            definition = limits["actuators"][key]
            values = frame[definition["column"]]
            window = _event_window(
                values >= threshold_fraction * float(definition["limit"]), frame
            )
            if window is None or window[2] < (10.0 / 60.0):
                continue
            transcript.append(
                _event_entry(
                    window,
                    f"{definition['label']} output saturated high",
                    f"Output reached {values.max():.1f} {definition['unit']} against a {definition['limit']:.0f} {definition['unit']} limit for {window[2]:.2f} cumulative hours.",
                )
            )

        nitrogen = frame["nitrogen_feed_kg_h"]
        nitrogen_definition = {"minimum": 50.0, "maximum": 200.0}
        for bound, value in nitrogen_definition.items():
            if bound == "minimum":
                mask = nitrogen <= value + 1e-6
            else:
                mask = nitrogen >= value - 1e-6
            window = _event_window(mask, frame)
            if window is None or window[2] < (10.0 / 60.0):
                continue
            transcript.append(
                _event_entry(
                    window,
                    f"Pressure controller output saturated at {bound}",
                    f"Nitrogen feed held at its {value:.0f} kg/h {bound} for {window[2]:.2f} cumulative hours.",
                )
            )

        hydrogen_vent_demand = frame.get(
            "vent_hydrogen_error_demand_active", pd.Series(False, index=frame.index)
        ).astype(bool)
        venting = frame["vent_flow_kg_h"] > 0.0
        removal_window = _event_window(hydrogen_vent_demand & venting, frame)
        if removal_window is not None:
            transcript.append(
                _event_entry(
                    removal_window,
                    "Hydrogen-removal vent demand active",
                    f"Vent flow reached {frame['vent_flow_kg_h'].max():.0f} kg/h while excess-hydrogen demand was active.",
                )
            )

        entries = self.trend_summary(transition_id)["stable_property_entry_hours"]
        for property_name in ("density", "mfr"):
            entry_hour = entries[property_name]
            if entry_hour is None:
                continue
            property_label = "Density" if property_name == "density" else "MFR"
            transcript.append(
                _event_entry(
                    (round(float(entry_hour), 3), round(float(entry_hour), 3), 0.0),
                    f"{property_label} entered its destination range",
                    f"Predicted {property_name} remained inside its destination range for at least 0.5 hours.",
                )
            )

        transcript.append(
            _event_entry(
                (round(end_hour, 3), round(end_hour, 3), 0.0),
                "Transition reached the on-spec criterion",
                f"The recorded transition ended at t={end_hour:.2f} h.",
            )
        )
        return sorted(transcript, key=lambda item: (item["start_hour"], item["event"]))


def load_repository(data_dir: Path | None = None) -> TransitionRepository:
    """Load the static exports; this function never invokes the simulator."""
    source = data_dir or ROOT / "data"
    histories = pd.read_csv(source / "transitions.csv")
    pre_transition = histories["relative_hour"] < 0.0
    for recipe, specifications in PROPERTY_SPECS.items():
        recipe_context = pre_transition & histories["start_recipe"].astype(str).eq(recipe)
        for column, value in specifications.items():
            histories.loc[recipe_context, column] = value
    metadata = json.loads((source / "transition_metadata.json").read_text())["transitions"]
    events = json.loads((source / "events.json").read_text())["transitions"]
    limits_path = source / "operating_limits.json"
    operating_limits = (
        json.loads(limits_path.read_text()) if limits_path.exists() else DEFAULT_OPERATING_LIMITS
    )
    labs_path = source / "pretransition_lab_samples.csv"
    pretransition_labs = pd.read_csv(labs_path) if labs_path.exists() else pd.DataFrame()
    return TransitionRepository(
        histories,
        tuple(metadata),
        tuple(events),
        operating_limits,
        pretransition_labs,
    )
