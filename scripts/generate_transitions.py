"""Generate the fixed six-transition demo campaign from ModularSimulator.

The public entry point creates a clean, ignored archive of the pinned simulator
commit and invokes this file again in an isolated uv environment.  The second
invocation performs the campaign and writes only demo-facing exports.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_COMMIT = "da3ec63"
CACHE_ROOT = ROOT / ".cache" / f"modular-simulator-{SIMULATOR_COMMIT}-stage1"
PATCH_MARKER = CACHE_ROOT / ".transition-demo-patched"
PATCH_VERSION = "12"
CAMPAIGN_START = datetime(2025, 1, 6, 8, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Recipe:
    code: str
    density: float
    mfr: float
    density_limits: tuple[float, float]
    mfr_limits: tuple[float, float]


RECIPES = {
    "2210": Recipe("2210", 920.0, 1.0, (919.0, 921.0), (0.82, 1.18)),
    "1630": Recipe("1630", 918.0, 3.0, (917.0, 919.0), (2.65, 3.35)),
}

DEFAULT_ARGS: dict[str, Any] = {
    "seed": 17,
    "sample_period_seconds": 120,
    "startup_hours": 24.0,
    "grade_2210_stabilization_hours": 30.0,
    "transition_spacing_hours": 44.0,
    "pressure_low_limit_kpa": 2100.0,
    "pressure_high_limit_kpa": 2300.0,
    "pressure_baseline_sp_kpa": 2225.0,
    "vent_max_kg_h": 1000.0,
    "vent_close_margin_kpa": 30.0,
    "vent_reopen_hysteresis_kpa": 10.0,
    "vent_high_reset_margin_kpa": 10.0,
    "vent_hydrogen_error_threshold": 0.05,
    "hydrogen_flow_max_kg_h": 20.0,
    "comonomer_flow_max_kg_h": 7000.0,
    "pretransition_lab_baseline_hours": 24.0,
    "lab_sample_interval_hours": 2.0,
    "lab_density_error_std_kg_m3": 0.30,
    "lab_mfr_relative_error_std": 0.04,
    "nitrogen_flow_min_kg_h": 50.0,
    "nitrogen_flow_max_kg_h": 200.0,
    "nitrogen_precondition_min_kg_h": 0.0,
    "nitrogen_precondition_max_kg_h": 3000.0,
    "nitrogen_precondition_hours": 10.0,
    "nitrogen_precondition_auto_settle_hours": 2.25,
    "nitrogen_precondition_gain_kg_h_per_kpa": 50.0,
    "pressure_precondition_target_range_kpa": [2130.0, 2270.0],
    "pds_efficiency_nominal": 0.80,
    "pds_efficiency_means": [0.80, 0.80, 0.80, 0.80, 0.80, 0.80],
    "pds_efficiency_reversion_per_h": 0.0,
    "pds_efficiency_volatility_per_sqrt_h": 0.0,
    "pds_efficiency_bounds": [0.70, 0.95],
    "pds_efficiency_max_deviation_fraction": 0.10,
    "poison_feed_means_g_h": [40.0, 140.0, 70.0, 180.0, 100.0, 220.0],
    "poison_reversion_per_h": 0.50,
    "poison_volatility_g_h_per_sqrt_h": 15.0,
    "poison_bounds_g_h": [0.0, 300.0],
    "catalyst_site1_fraction_range": [0.45, 0.55],
}


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one compatibility target in {path}, found {count}")
    path.write_text(text.replace(old, new))


def _find_simulator_repo() -> Path:
    candidates = [
        Path(os.environ["MODULAR_SIMULATOR_REPO"])
        if "MODULAR_SIMULATOR_REPO" in os.environ
        else None,
        ROOT.parent / "ModularSimulator",
        Path("/home/alden/projects/ModularSimulator"),
    ]
    for candidate in candidates:
        if candidate and (candidate / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(candidate), "cat-file", "-t", SIMULATOR_COMMIT],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip() == "commit":
                return candidate
    raise RuntimeError(
        "ModularSimulator with commit da3ec63 was not found. Set MODULAR_SIMULATOR_REPO."
    )


def _prepare_isolated_simulator() -> None:
    if PATCH_MARKER.exists() and PATCH_MARKER.read_text().strip() == PATCH_VERSION:
        return

    simulator_repo = _find_simulator_repo()
    staging = CACHE_ROOT.with_name(f"{CACHE_ROOT.name}-staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    archive_path = staging / "simulator.tar"
    subprocess.run(
        [
            "git",
            "-C",
            str(simulator_repo),
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            SIMULATOR_COMMIT,
        ],
        check=True,
    )
    with tarfile.open(archive_path) as archive:
        archive.extractall(staging, filter="data")
    archive_path.unlink()

    components_init = staging / "src/modular_simulation/components/__init__.py"
    _replace_once(
        components_init,
        "TagData = DataValue\n",
        "TagData = DataValue\nTagMetadata = PointMetadata\n",
    )

    control_element = (
        staging / "src/modular_simulation/components/control_system/control_element.py"
    )
    _replace_once(
        control_element,
        'mv_trajectory: Trajectory = Field(\n        ..., description="A Trajectory instance for manual control of the element."\n    )',
        'mv_trajectory: Trajectory = Field(\n        default_factory=lambda: Trajectory(y0=0.0),\n        description="A Trajectory instance for manual control of the element.",\n    )',
    )

    abstract_controller = (
        staging / "src/modular_simulation/components/control_system/abstract_controller.py"
    )
    _replace_once(
        abstract_controller,
        "        # Initialize control action with 'never' timestamp to ensure immediate update at t=0\n"
        '        self._control_action = DataValue(value=mv_data.value, time=float("-inf"), ok=mv_data.ok)\n',
        "        # First execution occurs after one system interval, giving dynamic controllers a finite dt.\n"
        "        self._control_action = DataValue(value=mv_data.value, time=system.time, ok=mv_data.ok)\n",
    )
    _replace_once(
        abstract_controller,
        "    sp_trajectory: Trajectory | None = Field(\n",
        "    setpoint_ramp_rate: PerSeconds | None = Field(\n"
        "        default=None,\n"
        "        description=(\n"
        '            "Optional rate limit for the controller working setpoint while "\n'
        '            "following its active auto or cascade request."\n'
        "        ),\n"
        "    )\n"
        "    sp_trajectory: Trajectory | None = Field(\n",
    )
    _replace_once(
        abstract_controller,
        "    _sp_point: Point = PrivateAttr()\n",
        "    _sp_point: Point = PrivateAttr()\n"
        "    _requested_sp: DataValue = PrivateAttr()\n",
    )
    _replace_once(
        abstract_controller,
        "        self._sp_point.data = DataValue(\n"
        "            time=system.time, value=self.sp_trajectory(system.time), ok=True\n"
        "        )\n",
        "        self._sp_point.data = DataValue(\n"
        "            time=system.time, value=self.sp_trajectory(system.time), ok=True\n"
        "        )\n"
        "        self._requested_sp = self._sp_point.data\n",
    )
    _replace_once(
        abstract_controller,
        "        sp = self._mode_manager.get_setpoint(t)\n"
        "        self._sp_point.data = sp\n",
        "        requested_sp = self._mode_manager.get_setpoint(t)\n"
        "        self._requested_sp = requested_sp\n"
        "        sp = self._apply_setpoint_ramp(requested_sp, t)\n"
        "        self._sp_point.data = sp\n",
    )
    _replace_once(
        abstract_controller,
        "    def _apply_mv_ramp(\n",
        "    def _apply_setpoint_ramp(self, requested_sp: DataValue, t: Seconds) -> DataValue:\n"
        "        if self.setpoint_ramp_rate is None:\n"
        "            return requested_sp\n"
        "        previous_sp = self._sp_point.data\n"
        "        dt = t - previous_sp.time\n"
        "        if dt <= 0.0:\n"
        "            return DataValue(time=t, value=previous_sp.value, ok=requested_sp.ok)\n"
        "        maximum_delta = self.setpoint_ramp_rate * dt\n"
        "        delta = requested_sp.value - previous_sp.value\n"
        "        if np.absolute(delta) <= maximum_delta:\n"
        "            value = requested_sp.value\n"
        "        else:\n"
        "            value = previous_sp.value + math.copysign(maximum_delta, delta)\n"
        "        return DataValue(time=t, value=value, ok=requested_sp.ok)\n\n"
        "    def _apply_mv_ramp(\n",
    )

    bang_bang = (
        staging / "src/modular_simulation/components/control_system/controllers/bang_bang.py"
    )
    _replace_once(bang_bang, "    def post_install(\n", "    def post_wire_to_element(\n")

    first_order = (
        staging
        / "src/modular_simulation/components/control_system/controllers/first_order_trajectory.py"
    )
    _replace_once(
        first_order,
        "from __future__ import annotations\n",
        "from __future__ import annotations\nimport math\n",
    )
    _replace_once(
        first_order,
        "        open_loop_tc = self._get_open_loop_tc()\n"
        "        closed_loop_tc = open_loop_tc * self.closed_loop_time_constant_fraction\n"
        "        dt = t - self.t\n",
        "        open_loop_tc = self._get_open_loop_tc()\n"
        "        dt = t - self.t\n"
        "        if not math.isfinite(float(open_loop_tc)) or open_loop_tc <= 0.0:\n"
        "            return cv, True\n"
        "        if not math.isfinite(float(dt)) or dt <= 0.0:\n"
        "            return cv, True\n"
        "        closed_loop_tc = open_loop_tc * self.closed_loop_time_constant_fraction\n",
    )

    calculation = staging / "src/modular_simulation/components/calculations/abstract_calculation.py"
    _replace_once(
        calculation,
        "        if not exceptions:\n            # Perform initial calculation\n            try:\n",
        "        if not exceptions:\n            # Perform initial calculation\n"
        "            was_initialized = self._initialized\n"
        "            self._initialized = True\n            try:\n",
    )
    _replace_once(
        calculation,
        "            except Exception as e:\n                exceptions.append(e)\n\n        return exceptions\n",
        "            except Exception as e:\n                exceptions.append(e)\n"
        "            finally:\n                self._initialized = was_initialized\n\n"
        "        return exceptions\n",
    )

    process_definition = staging / "examples/gas_phase_polymerization/process_definition.py"
    _replace_once(
        process_definition,
        '    F_vent: Annotated[float, M(type=T.CONTROLLED, unit="L/s")] = 0.0\n',
        '    F_vent: Annotated[float, M(type=T.CONTROLLED, unit="kg/h")] = 0.0\n',
    )
    _replace_once(
        process_definition,
        '    discharge_valve_position: Annotated[float, M(type=T.CONTROLLED, unit="")] = 0.0\n',
        '    discharge_valve_position: Annotated[float, M(type=T.CONTROLLED, unit="")] = 0.0\n'
        '    discharge_efficiency: Annotated[float, M(type=T.CONTROLLED, unit="")] = 0.80\n',
    )
    _replace_once(
        process_definition,
        '    discharge_efficiency: Annotated[float, M(type=T.CONSTANT, unit="")] = 0.80\n',
        "",
    )
    _replace_once(
        process_definition,
        '        discharge_efficiency = float(k[k_map["discharge_efficiency"]])\n',
        '        discharge_efficiency = float(u[u_map["discharge_efficiency"]])\n',
    )
    _replace_once(
        process_definition,
        '        F_vent = float(u[u_map["F_vent"]])\n',
        '        F_vent_mass_kg_h = float(u[u_map["F_vent"]])\n',
    )
    _replace_once(
        process_definition,
        "        total_gas_loss = polymer_discharge_rate / discharge_efficiency - polymer_discharge_rate + F_vent\n",
        "        gas_concentration = max(\n"
        "            SMALL, c_monomer + c_comonomer + c_hydrogen + c_nitrogen\n"
        "        )\n"
        "        mixture_mw = (\n"
        "            c_monomer * monomer_mw\n"
        "            + c_comonomer * comonomer_mw\n"
        '            + c_hydrogen * float(k[k_map["hydrogen_mw"]])\n'
        '            + c_nitrogen * float(k[k_map["nitrogen_mw"]])\n'
        "        ) / gas_concentration\n"
        "        vent_molar_flow = (\n"
        "            F_vent_mass_kg_h * 1000.0 / 3600.0 / max(SMALL, mixture_mw)\n"
        "        )\n"
        "        vent_volumetric_flow = (\n"
        "            vent_molar_flow\n"
        "            * R_GAS_KPA_L_PER_MOL_K\n"
        "            * temperature\n"
        "            / max(SMALL, pressure)\n"
        "        )\n"
        "        total_gas_loss = (\n"
        "            polymer_discharge_rate / discharge_efficiency\n"
        "            - polymer_discharge_rate\n"
        "            + vent_volumetric_flow\n"
        "        )\n",
    )

    component_definition = staging / "examples/gas_phase_polymerization/component_definition.py"
    _replace_once(
        component_definition,
        '        mv_tag="F_n2",\n'
        "        mv_range=(0.0, 500.0),\n"
        "        controller=PIDController(\n"
        '            cv_tag="filtered_pressure",\n'
        "            cv_range=(0.0, 3000.0),\n"
        "            sp_trajectory=Trajectory(y0=1900.0),\n"
        "            Kp=500.0 / 200.0,\n"
        "        ),\n",
        '        mv_tag="F_n2",\n'
        "        mv_range=(50.0 / 3.6, 200.0 / 3.6),\n"
        "        controller=PIDController(\n"
        '            cv_tag="filtered_pressure",\n'
        "            cv_range=(0.0, 3000.0),\n"
        "            sp_trajectory=Trajectory(y0=1900.0),\n"
        "            Kp=500.0 / 200.0,\n"
        "            Ti=hour(1.0),\n"
        "        ),\n",
    )
    _replace_once(
        component_definition,
        '        mv_tag="F_h2",\n        mv_range=(0.0, 15.0),\n',
        '        mv_tag="F_h2",\n        mv_range=(0.0, 20.0 / 3.6),\n',
    )
    _replace_once(
        component_definition,
        '    SampledDelayedSensor(measurement_tag="F_vent", unit="L/hr"),\n',
        '    SampledDelayedSensor(measurement_tag="F_vent", unit="kg/hr"),\n',
    )
    _replace_once(
        component_definition,
        "        mv_range=(0.0, 25_000.0),\n        controller=PIDController(\n"
        '            cv_tag="filtered_pressure_vent",\n',
        "        mv_range=(0.0, 1_000.0),\n        controller=PIDController(\n"
        '            cv_tag="filtered_pressure_vent",\n',
    )
    _replace_once(
        component_definition,
        "            Kp=25_000.0 / 200.0,\n",
        "            Kp=1_000.0 / 200.0,\n",
    )
    _replace_once(
        component_definition,
        "            Kp=3500.0,\n            Ti=hour(0.5),\n",
        "            Kp=10000.0,\n            Ti=minute(25),\n",
    )
    _replace_once(
        component_definition,
        "            Kp=200.0,\n            Ti=hour(1.5),\n",
        "            Kp=600.0,\n            Ti=minute(25),\n",
    )
    for class_name in (
        "MoleRatioCalculation",
        "Monomer1PartialPressure",
        "ResidenceTimeCalculation",
        "CatInventoryEstimator",
        "AlTiRatioEstimator",
        "PropertyEstimator",
    ):
        _replace_once(
            component_definition,
            f"    {class_name}(\n",
            f'    {class_name}(\n        name="{class_name}",\n',
        )

    property_estimator = (
        staging / "examples/gas_phase_polymerization/calculations/property_estimator.py"
    )
    _replace_once(
        property_estimator,
        "        self.MI_model_parameters[0] = x_lag_plus[2]\n"
        "        self.density_model_parameters[0] = x_lag_plus[3]\n",
        "        self.MI_model_parameters[0] = x_lag_plus[2, 0]\n"
        "        self.density_model_parameters[0] = x_lag_plus[3, 0]\n",
    )

    native_plot = staging / "examples/gas_phase_polymerization/run_simulation.py"
    _replace_once(
        native_plot,
        '    axes[10].axis("off")\n    axes[11].axis("off")\n\n'
        "    for ax in (axes[6], axes[7], axes[8]):\n",
        "    ax = axes[10]\n"
        '    to_hours(ax, history["F_n2"], label="F_n2", line_kwargs={"color": "tab:green"})\n'
        '    ax.set_title("Nitrogen Flow")\n'
        '    ax.set_ylabel("F_n2 [kg/h]")\n'
        "    ax.grid(True, alpha=0.3)\n"
        '    ax.legend(loc="best")\n\n'
        "    ax = axes[11]\n"
        '    to_hours(ax, history["F_vent"], label="F_vent", line_kwargs={"color": "tab:red"})\n'
        '    ax.set_title("Vent Flow")\n'
        '    ax.set_ylabel("F_vent [kg/h]")\n'
        "    ax.grid(True, alpha=0.3)\n"
        '    ax.legend(loc="best")\n\n'
        "    for ax in (axes[6], axes[7], axes[8], axes[9], axes[10], axes[11]):\n",
    )

    if CACHE_ROOT.exists():
        shutil.rmtree(CACHE_ROOT)
    staging.rename(CACHE_ROOT)
    PATCH_MARKER.write_text(f"{PATCH_VERSION}\n")


def _run_in_isolated_environment(output_dir: Path, scenario_path: Path | None) -> None:
    _prepare_isolated_simulator()
    command = [
        "uv",
        "run",
        "--isolated",
        "--with",
        "thermo>=0.3.0",
        "--with",
        "chemicals>=1.2.0",
        "--with",
        "nicegui",
        "python",
        str(Path(__file__).resolve()),
        "--isolated-root",
        str(CACHE_ROOT),
        "--output-dir",
        str(output_dir),
    ]
    if scenario_path is not None:
        command.extend(["--scenario", str(scenario_path)])
    subprocess.run(command, cwd=ROOT, check=True)


class HydrogenErrorVentController:
    """Request venting from excess hydrogen or pressure, with low-pressure protection."""

    def __init__(
        self,
        low_limit: float,
        high_limit: float,
        close_margin: float,
        reopen_hysteresis: float,
        high_reset_margin: float,
        hydrogen_error_threshold: float,
        maximum: float,
    ) -> None:
        self.close_threshold = low_limit + close_margin
        self.reopen_threshold = self.close_threshold + reopen_hysteresis
        self.high_open_threshold = high_limit
        self.high_reset_threshold = high_limit - high_reset_margin
        self.hydrogen_error_threshold = hydrogen_error_threshold
        self.maximum = maximum
        self.low_pressure_override_active = False
        self.high_pressure_override_active = False
        self.hydrogen_error_demand_active = False

    def update(self, pressure: float, hydrogen_ratio: float, hydrogen_ratio_sp: float) -> float:
        if pressure <= self.close_threshold:
            self.low_pressure_override_active = True
        elif pressure >= self.reopen_threshold:
            self.low_pressure_override_active = False

        if pressure >= self.high_open_threshold:
            self.high_pressure_override_active = True
        elif pressure <= self.high_reset_threshold:
            self.high_pressure_override_active = False

        hydrogen_error = hydrogen_ratio - hydrogen_ratio_sp
        self.hydrogen_error_demand_active = hydrogen_error > self.hydrogen_error_threshold
        requested = self.hydrogen_error_demand_active or self.high_pressure_override_active
        if not requested or self.low_pressure_override_active:
            return 0.0
        return self.maximum


def _put_all_loops_on_highest_cascade(system: Any) -> None:
    """Run every actuator in AUTO and every available controller chain in cascade."""
    from modular_simulation.components import ControllerMode

    def configure(controller: Any) -> None:
        if controller.cascade_controller is None:
            if controller.mode != ControllerMode.AUTO:
                controller.change_control_mode(ControllerMode.AUTO)
            return
        if controller.mode != ControllerMode.CASCADE:
            controller.change_control_mode(ControllerMode.CASCADE)
        configure(controller.cascade_controller)

    for control_element in system.control_elements:
        if control_element.mode != ControllerMode.AUTO:
            control_element.change_control_mode(ControllerMode.AUTO)
        if control_element.controller is not None:
            configure(control_element.controller)


def _intervals(
    mask: pd.Series, hours: pd.Series, minimum_minutes: float = 0.0
) -> list[dict[str, float]]:
    intervals: list[dict[str, float]] = []
    start: float | None = None
    previous = float(hours.iloc[0]) if len(hours) else 0.0
    for active, hour_value in zip(mask.astype(bool), hours, strict=True):
        hour_value = float(hour_value)
        if active and start is None:
            start = hour_value
        if not active and start is not None:
            if (previous - start) * 60.0 >= minimum_minutes:
                intervals.append({"start_hour": round(start, 3), "end_hour": round(previous, 3)})
            start = None
        previous = hour_value
    if start is not None and (previous - start) * 60.0 >= minimum_minutes:
        intervals.append({"start_hour": round(start, 3), "end_hour": round(previous, 3)})
    return intervals


def _first_sustained_on_spec(frame: pd.DataFrame, recipe: Recipe) -> float | None:
    inside = frame["predicted_density_kg_m3"].between(*recipe.density_limits) & frame[
        "predicted_mfr_g_10min"
    ].between(*recipe.mfr_limits)
    required = 16  # 16 two-minute points spans 30 minutes inclusively.
    sustained = inside.rolling(required, min_periods=required).sum().eq(required)
    matches = frame.loc[sustained, "campaign_hour"]
    if matches.empty:
        return None
    return float(matches.iloc[0]) - 0.5


def _build_exports(
    campaign: pd.DataFrame,
    switches: list[dict[str, Any]],
    args: dict[str, Any],
    output_dir: Path,
) -> None:
    transition_frames: list[pd.DataFrame] = []
    pretransition_lab_frames: list[pd.DataFrame] = []
    metadata: list[dict[str, Any]] = []
    events: dict[str, Any] = {"transitions": []}

    for index, switch in enumerate(switches, start=1):
        source = RECIPES[switch["start_recipe"]]
        destination = RECIPES[switch["end_recipe"]]
        next_switch = (
            switches[index]["campaign_hour"]
            if index < len(switches)
            else campaign["campaign_hour"].max()
        )
        search = campaign[
            campaign["campaign_hour"].between(
                switch["campaign_hour"], next_switch, inclusive="left"
            )
        ]
        on_spec_hour = _first_sustained_on_spec(search, destination)
        if on_spec_hour is None:
            on_spec_hour = min(next_switch, switch["campaign_hour"] + 8.0)
        duration = on_spec_hour - switch["campaign_hour"]
        window_end = min(next_switch, on_spec_hour + 2.0)
        next_precondition_start = (
            next_switch - args["nitrogen_precondition_hours"]
            if index < len(switches)
            else float("inf")
        )
        capsule = campaign[
            (campaign["campaign_hour"] >= switch["campaign_hour"] - 2.0)
            & (campaign["campaign_hour"] <= window_end)
            & (campaign["campaign_hour"] < next_precondition_start)
        ].copy()
        transition_id = f"TR-{index:02d}"
        lab_baseline = campaign[
            campaign["campaign_hour"].between(
                switch["campaign_hour"] - args["pretransition_lab_baseline_hours"],
                switch["campaign_hour"],
                inclusive="left",
            )
        ][
            [
                "campaign_hour",
                "timestamp",
                "predicted_density_kg_m3",
                "lab_density_kg_m3",
                "predicted_mfr_g_10min",
                "lab_mfr_g_10min",
            ]
        ].dropna(subset=["lab_density_kg_m3", "lab_mfr_g_10min"])
        lab_baseline = lab_baseline.copy()
        lab_baseline.insert(0, "transition_id", transition_id)
        lab_baseline["relative_hour"] = (
            lab_baseline["campaign_hour"] - switch["campaign_hour"]
        )
        lab_baseline["density_error_kg_m3"] = (
            lab_baseline["lab_density_kg_m3"]
            - lab_baseline["predicted_density_kg_m3"]
        )
        lab_baseline["mfr_error_g_10min"] = (
            lab_baseline["lab_mfr_g_10min"] - lab_baseline["predicted_mfr_g_10min"]
        )
        pretransition_lab_frames.append(lab_baseline)
        capsule["transition_id"] = transition_id
        capsule["relative_hour"] = capsule["campaign_hour"] - switch["campaign_hour"]
        capsule["direction"] = f"{switch['start_recipe']} → {switch['end_recipe']}"
        capsule["start_recipe"] = switch["start_recipe"]
        capsule["end_recipe"] = switch["end_recipe"]
        before_switch = capsule["relative_hour"] < 0.0
        capsule["density_target_kg_m3"] = np.where(
            before_switch, source.density, destination.density
        )
        capsule["density_low_limit_kg_m3"] = np.where(
            before_switch, source.density_limits[0], destination.density_limits[0]
        )
        capsule["density_high_limit_kg_m3"] = np.where(
            before_switch, source.density_limits[1], destination.density_limits[1]
        )
        capsule["mfr_target_g_10min"] = np.where(
            before_switch, source.mfr, destination.mfr
        )
        capsule["mfr_low_limit_g_10min"] = np.where(
            before_switch, source.mfr_limits[0], destination.mfr_limits[0]
        )
        capsule["mfr_high_limit_g_10min"] = np.where(
            before_switch, source.mfr_limits[1], destination.mfr_limits[1]
        )
        capsule["pressure_margin_kpa"] = np.where(
            switch["end_recipe"] == "1630",
            args["pressure_high_limit_kpa"] - capsule["total_pressure_kpa"],
            capsule["total_pressure_kpa"] - args["pressure_low_limit_kpa"],
        )
        transition_frames.append(capsule)

        max_pressure = float(capsule["total_pressure_kpa"].max())
        predisposition = "high-pressure" if switch["end_recipe"] == "1630" else "low-pressure"
        if predisposition == "high-pressure":
            outcome = (
                "High limit reached"
                if max_pressure >= args["pressure_high_limit_kpa"]
                else "High-pressure margin reduced"
            )
        else:
            outcome = (
                "Low vent override active"
                if capsule["vent_override_active"].any()
                else "Low-pressure margin reduced"
            )
        metadata.append(
            {
                "transition_id": transition_id,
                "date": switch["timestamp"],
                "start_recipe": switch["start_recipe"],
                "end_recipe": switch["end_recipe"],
                "duration_hours": round(duration, 3),
                "baseline_pressure_kpa": round(float(switch["baseline_pressure_kpa"]), 2),
                "baseline_production_rate_t_h": round(
                    float(switch["baseline_production_rate_t_h"]), 2
                ),
                "baseline_catalyst_feed_kg_h": round(
                    float(switch["baseline_catalyst_feed_kg_h"]), 4
                ),
                "baseline_density_kg_m3": round(float(switch["baseline_density_kg_m3"]), 4),
                "baseline_mfr_g_10min": round(float(switch["baseline_mfr_g_10min"]), 4),
                "discharge_efficiency_at_start": round(
                    float(switch["discharge_efficiency_at_start"]), 4
                ),
                "poison_feed_g_h_at_start": round(
                    float(switch["poison_feed_g_h_at_start"]), 4
                ),
                "perturbations": switch["perturbations"],
                "predisposition": predisposition,
                "outcome_label": outcome,
            }
        )

        relative = capsule["relative_hour"]
        high = capsule["total_pressure_kpa"] >= args["pressure_high_limit_kpa"]
        low = capsule["total_pressure_kpa"] <= args["pressure_low_limit_kpa"]
        feed_saturation = (
            capsule["comonomer_feed_kg_h"] >= 0.98 * args["comonomer_flow_max_kg_h"]
        ) | (
            capsule["hydrogen_feed_kg_h"] >= 0.98 * args["hydrogen_flow_max_kg_h"]
        )
        venting = capsule["vent_flow_kg_h"] > 0.0
        events["transitions"].append(
            {
                "transition_id": transition_id,
                "start_hour": 0.0,
                "end_hour": round(duration, 3),
                "on_spec_entry_hour": round(duration, 3),
                "high_pressure_intervals": _intervals(high, relative),
                "low_pressure_intervals": _intervals(low, relative),
                "sustained_saturation_intervals": _intervals(feed_saturation, relative, 10.0),
                "venting_intervals": _intervals(venting, relative),
            }
        )

    output = pd.concat(transition_frames, ignore_index=True)
    columns = [
        "transition_id",
        "timestamp",
        "relative_hour",
        "direction",
        "start_recipe",
        "end_recipe",
        "total_pressure_kpa",
        "pressure_low_limit_kpa",
        "pressure_high_limit_kpa",
        "pressure_control_sp_kpa",
        "ethylene_partial_pressure_kpa",
        "ethylene_partial_pressure_sp_kpa",
        "predicted_density_kg_m3",
        "density_supervisory_target_kg_m3",
        "lab_density_kg_m3",
        "density_target_kg_m3",
        "density_low_limit_kg_m3",
        "density_high_limit_kg_m3",
        "comonomer_mole_ratio",
        "comonomer_mole_ratio_sp_request",
        "comonomer_mole_ratio_sp",
        "predicted_mfr_g_10min",
        "mfr_supervisory_target_g_10min",
        "lab_mfr_g_10min",
        "mfr_target_g_10min",
        "mfr_low_limit_g_10min",
        "mfr_high_limit_g_10min",
        "hydrogen_mole_ratio",
        "hydrogen_mole_ratio_sp_request",
        "hydrogen_mole_ratio_sp",
        "hydrogen_mole_ratio_error",
        "catalyst_feed_kg_h",
        "ethylene_feed_kg_h",
        "comonomer_feed_kg_h",
        "hydrogen_feed_kg_h",
        "nitrogen_feed_kg_h",
        "nitrogen_preconditioning_active",
        "pressure_precondition_target_kpa",
        "vent_flow_kg_h",
        "vent_requested_kg_h",
        "vent_hydrogen_error_demand_active",
        "vent_override_active",
        "vent_high_pressure_override_active",
        "discharge_efficiency",
        "discharge_efficiency_mean",
        "poison_feed_g_h",
        "poison_feed_mean_g_h",
        "catalyst_site1_fraction",
        "discharge_valve_position",
        "production_rate_t_h",
        "bed_level_m",
        "pressure_margin_kpa",
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    output[columns].to_csv(output_dir / "transitions.csv", index=False, float_format="%.6f")
    pretransition_labs = pd.concat(pretransition_lab_frames, ignore_index=True)
    pretransition_labs.to_csv(
        output_dir / "pretransition_lab_samples.csv", index=False, float_format="%.6f"
    )
    operating_limits = {
        "pressure": {
            "low": args["pressure_low_limit_kpa"],
            "high": args["pressure_high_limit_kpa"],
            "unit": "kPa",
        },
        "actuators": {
            "vent": {
                "column": "vent_flow_kg_h",
                "label": "Vent flow",
                "limit": args["vent_max_kg_h"],
                "unit": "kg/h",
            },
            "comonomer": {
                "column": "comonomer_feed_kg_h",
                "label": "FM2 feed",
                "limit": args["comonomer_flow_max_kg_h"],
                "unit": "kg/h",
            },
            "hydrogen": {
                "column": "hydrogen_feed_kg_h",
                "label": "Hydrogen feed",
                "limit": args["hydrogen_flow_max_kg_h"],
                "unit": "kg/h",
            },
        },
        "saturation_fraction": 0.98,
    }
    (output_dir / "operating_limits.json").write_text(
        json.dumps(operating_limits, indent=2) + "\n"
    )
    (output_dir / "transition_metadata.json").write_text(
        json.dumps({"transitions": metadata}, indent=2) + "\n"
    )
    (output_dir / "events.json").write_text(json.dumps(events, indent=2) + "\n")
    (output_dir / "generation_args.json").write_text(
        json.dumps(args, indent=2, sort_keys=True) + "\n"
    )


def _run_campaign(
    isolated_root: Path,
    output_dir: Path,
    scenario_path: Path | None,
) -> None:
    sys.path.insert(0, str(isolated_root / "src"))
    sys.path.insert(0, str(isolated_root / "examples/gas_phase_polymerization"))
    logging.disable(logging.CRITICAL)
    from modular_simulation.components import ControllerMode
    from run_simulation import system  # type: ignore[import-not-found]

    args = dict(DEFAULT_ARGS)
    if scenario_path is not None:
        overrides = json.loads(scenario_path.read_text())
        unknown = set(overrides) - (set(DEFAULT_ARGS) | {
            "pressure_precondition_targets_kpa",
            "high_pressure_precondition_cap_kpa",
            "high_pressure_comonomer_sp_ramp_rate_per_h",
            "high_pressure_hydrogen_sp_ramp_rate_per_h",
            "high_pressure_ramp_only_when_pressure_capped",
            "scenario_name",
        })
        if unknown:
            raise ValueError(f"Unknown scenario arguments: {', '.join(sorted(unknown))}")
        args.update(overrides)
    rng = np.random.default_rng(args["seed"])
    system.show_progress = False
    _put_all_loops_on_highest_cascade(system)
    system.extend_controller_sp_trajectory("filtered_pressure", args["pressure_baseline_sp_kpa"])
    system.extend_controller_sp_trajectory(
        "filtered_pressure_vent", args["pressure_baseline_sp_kpa"]
    )
    process = system.process_model

    for index, sensor in enumerate(system.sensors):
        sensor._generator = np.random.default_rng(args["seed"] + index)

    dt_seconds = float(system.dt)
    record_every = round(args["sample_period_seconds"] / dt_seconds)
    first_switch_hour = args["startup_hours"] + args["grade_2210_stabilization_hours"]
    total_hours = first_switch_hour + 6 * args["transition_spacing_hours"]
    total_steps = round(total_hours * 3600.0 / dt_seconds)
    startup_end_step = round(args["startup_hours"] * 3600.0 / dt_seconds)
    switch_steps = {
        round(
            (first_switch_hour + index * args["transition_spacing_hours"]) * 3600.0 / dt_seconds
        ): index
        for index in range(6)
    }
    target_low, target_high = args["pressure_precondition_target_range_kpa"]
    if "pressure_precondition_targets_kpa" in args:
        pressure_targets = [float(value) for value in args["pressure_precondition_targets_kpa"]]
        if len(pressure_targets) != 6:
            raise ValueError("pressure_precondition_targets_kpa must contain six values")
        if not all(target_low <= value <= target_high for value in pressure_targets):
            raise ValueError("Pressure precondition targets must remain in the approved range")
    else:
        pressure_target_rng = np.random.default_rng(args["seed"] + 30_000)
        pressure_targets = pressure_target_rng.uniform(target_low, target_high, size=6)
        pressure_targets = target_low + (
            (pressure_targets - pressure_targets.min())
            / (pressure_targets.max() - pressure_targets.min())
            * (target_high - target_low)
        )
        pressure_targets = pressure_targets.round(1).tolist()
    uncapped_pressure_targets = list(pressure_targets)
    pressure_target_was_capped = [False] * len(pressure_targets)
    if "high_pressure_precondition_cap_kpa" in args:
        pressure_cap = float(args["high_pressure_precondition_cap_kpa"])
        if not target_low <= pressure_cap <= target_high:
            raise ValueError("High-pressure precondition cap must remain in the approved range")
        for index in range(0, len(pressure_targets), 2):
            capped_target = min(pressure_targets[index], pressure_cap)
            pressure_target_was_capped[index] = capped_target < pressure_targets[index]
            pressure_targets[index] = capped_target
    args["pressure_precondition_targets_kpa"] = pressure_targets
    args["uncapped_pressure_precondition_targets_kpa"] = uncapped_pressure_targets
    args["pressure_precondition_target_was_capped"] = pressure_target_was_capped
    catalyst_fraction_rng = np.random.default_rng(args["seed"] + 40_000)
    catalyst_fraction_low, catalyst_fraction_high = args["catalyst_site1_fraction_range"]
    catalyst_site1_fractions = catalyst_fraction_rng.uniform(
        catalyst_fraction_low, catalyst_fraction_high, size=6
    ).round(4).tolist()
    args["catalyst_site1_fractions"] = catalyst_site1_fractions
    switch_hours = [
        first_switch_hour + index * args["transition_spacing_hours"] for index in range(6)
    ]
    precondition_handoff_steps = {
        round(
            (switch_hour - args["nitrogen_precondition_auto_settle_hours"])
            * 3600.0
            / dt_seconds
        ): index
        for index, switch_hour in enumerate(switch_hours)
    }
    context_change_steps = {
        round(
            (
                first_switch_hour
                + index * args["transition_spacing_hours"]
                + args["transition_spacing_hours"] / 2.0
            )
            * 3600.0
            / dt_seconds
        ): index + 1
        for index in range(5)
    }
    vent = HydrogenErrorVentController(
        args["pressure_low_limit_kpa"],
        args["pressure_high_limit_kpa"],
        args["vent_close_margin_kpa"],
        args["vent_reopen_hysteresis_kpa"],
        args["vent_high_reset_margin_kpa"],
        args["vent_hydrogen_error_threshold"],
        args["vent_max_kg_h"],
    )
    efficiency_rng = np.random.default_rng(args["seed"] + 10_000)
    efficiency = float(args["pds_efficiency_nominal"])
    efficiency_mean = float(args["pds_efficiency_means"][0])
    poison_rng = np.random.default_rng(args["seed"] + 20_000)
    poison_feed_g_h = float(args["poison_feed_means_g_h"][0])
    poison_mean_g_h = poison_feed_g_h
    catalyst_site1_fraction = float(catalyst_site1_fractions[0])
    process.cat_type1_site_fraction = catalyst_site1_fraction
    efficiency_dt_hours = dt_seconds / 3600.0
    active_preconditioning_index: int | None = None
    nitrogen_precondition_base_kg_h = float(process.F_n2) * 3.6
    records: list[dict[str, Any]] = []
    switches: list[dict[str, Any]] = []
    next_lab_hour = 0.0

    for step_index in range(total_steps + 1):
        campaign_hour = system.time / 3600.0
        preconditioning_index = next(
            (
                index
                for index, switch_hour in enumerate(switch_hours)
                if switch_hour - args["nitrogen_precondition_hours"]
                <= campaign_hour
                < switch_hour - args["nitrogen_precondition_auto_settle_hours"]
            ),
            None,
        )
        nitrogen_preconditioning_active = preconditioning_index is not None
        pressure_precondition_target = (
            pressure_targets[preconditioning_index]
            if preconditioning_index is not None
            else float("nan")
        )
        if nitrogen_preconditioning_active:
            if preconditioning_index != active_preconditioning_index:
                active_preconditioning_index = preconditioning_index
                nitrogen_precondition_base_kg_h = float(process.F_n2) * 3.6
            nitrogen_element = system.control_element_mv_dictionary["F_n2"]
            nitrogen_element.mv_range = (
                args["nitrogen_precondition_min_kg_h"] / 3.6,
                args["nitrogen_precondition_max_kg_h"] / 3.6,
            )
            nitrogen_feed_kg_h = float(
                np.clip(
                    nitrogen_precondition_base_kg_h
                    + args["nitrogen_precondition_gain_kg_h_per_kpa"]
                    * (pressure_precondition_target - float(process.pressure)),
                    args["nitrogen_precondition_min_kg_h"],
                    args["nitrogen_precondition_max_kg_h"],
                )
            )
            system.extend_control_element_mv_trajectory("F_n2", nitrogen_feed_kg_h / 3.6)
        if step_index in precondition_handoff_steps:
            handoff_index = precondition_handoff_steps[step_index]
            nitrogen_element = system.control_element_mv_dictionary["F_n2"]
            nitrogen_element.mv_range = (
                args["nitrogen_flow_min_kg_h"] / 3.6,
                args["nitrogen_flow_max_kg_h"] / 3.6,
            )
            nitrogen_element.change_control_mode(ControllerMode.AUTO)
            system.extend_controller_sp_trajectory(
                "filtered_pressure", pressure_targets[handoff_index]
            )
            active_preconditioning_index = None
        if step_index == startup_end_step:
            # Follow the example's native startup first.  Once it has established a
            # baseline, move the outer property loops to 2210 and leave every inner
            # ratio controller in cascade.
            system.extend_controller_sp_trajectory("cumm_density", RECIPES["2210"].density)
            system.extend_controller_sp_trajectory("cumm_MI", RECIPES["2210"].mfr)
            system.extend_control_element_mv_trajectory("F_vent", 0.0)
        if step_index in context_change_steps:
            context_index = context_change_steps[step_index]
            efficiency_mean = float(args["pds_efficiency_means"][context_index])
            poison_mean_g_h = float(args["poison_feed_means_g_h"][context_index])
            catalyst_site1_fraction = float(catalyst_site1_fractions[context_index])
            process.cat_type1_site_fraction = catalyst_site1_fraction
        if step_index in switch_steps:
            transition_index = switch_steps[step_index]
            nitrogen_element = system.control_element_mv_dictionary["F_n2"]
            nitrogen_element.mv_range = (
                args["nitrogen_flow_min_kg_h"] / 3.6,
                args["nitrogen_flow_max_kg_h"] / 3.6,
            )
            if nitrogen_element.mode != ControllerMode.AUTO:
                nitrogen_element.change_control_mode(ControllerMode.AUTO)
            system.extend_controller_sp_trajectory(
                "filtered_pressure", pressure_targets[transition_index]
            )
            active_preconditioning_index = None
            start_code, end_code = (
                ("2210", "1630") if transition_index % 2 == 0 else ("1630", "2210")
            )
            concentration_ramp_rates = {
                "rM2": float(args.get("high_pressure_comonomer_sp_ramp_rate_per_h", 0.0)),
                "rH2": float(args.get("high_pressure_hydrogen_sp_ramp_rate_per_h", 0.0)),
            }
            ramp_only_when_capped = bool(
                args.get("high_pressure_ramp_only_when_pressure_capped", False)
            )
            concentration_ramp_active = end_code == "1630" and (
                not ramp_only_when_capped or pressure_target_was_capped[transition_index]
            )
            for controller_tag, rate_per_hour in concentration_ramp_rates.items():
                controller = system.controller_dictionary[controller_tag]
                controller.setpoint_ramp_rate = (
                    rate_per_hour / 3600.0
                    if concentration_ramp_active and rate_per_hour > 0.0
                    else None
                )
            destination = RECIPES[end_code]
            for tag, target in (
                ("cumm_density", destination.density),
                ("cumm_MI", destination.mfr),
            ):
                system.extend_controller_sp_trajectory(tag, target)
            switches.append(
                {
                    "campaign_hour": campaign_hour,
                    "timestamp": (CAMPAIGN_START + timedelta(hours=campaign_hour)).isoformat(),
                    "start_recipe": start_code,
                    "end_recipe": end_code,
                    "baseline_pressure_kpa": float(process.pressure),
                    "baseline_production_rate_t_h": float(process.mass_prod_rate),
                    "baseline_catalyst_feed_kg_h": float(process.F_cat) * 3.6,
                    "baseline_density_kg_m3": float(
                        system.point_registry["cumm_density"].data.value
                    ),
                    "baseline_mfr_g_10min": float(
                        system.point_registry["cumm_MI"].data.value
                    ),
                    "discharge_efficiency_at_start": efficiency,
                    "poison_feed_g_h_at_start": poison_feed_g_h,
                    "perturbations": {
                        "pds_efficiency_at_switch": round(efficiency, 4),
                        "pds_efficiency_mean": efficiency_mean,
                        "poison_feed_g_h_at_switch": round(poison_feed_g_h, 6),
                        "poison_feed_mean_g_h": poison_mean_g_h,
                        "catalyst_site1_fraction": catalyst_site1_fraction,
                        "pressure_precondition_target_kpa": pressure_targets[transition_index],
                        "pressure_precondition_target_uncapped_kpa": (
                            uncapped_pressure_targets[transition_index]
                        ),
                        "pressure_precondition_target_was_capped": (
                            pressure_target_was_capped[transition_index]
                        ),
                        "hydrogen_error_vent_threshold": args["vent_hydrogen_error_threshold"],
                        "comonomer_sp_ramp_rate_per_h": (
                            concentration_ramp_rates["rM2"]
                            if concentration_ramp_active
                            else 0.0
                        ),
                        "hydrogen_sp_ramp_rate_per_h": (
                            concentration_ramp_rates["rH2"]
                            if concentration_ramp_active
                            else 0.0
                        ),
                    },
                }
            )

        if step_index >= startup_end_step:
            efficiency += (
                args["pds_efficiency_reversion_per_h"]
                * (efficiency_mean - efficiency)
                * efficiency_dt_hours
            )
            efficiency += (
                args["pds_efficiency_volatility_per_sqrt_h"]
                * math.sqrt(efficiency_dt_hours)
                * efficiency_rng.normal()
            )
            absolute_lower, absolute_upper = args["pds_efficiency_bounds"]
            deviation = args["pds_efficiency_max_deviation_fraction"]
            efficiency_lower = max(absolute_lower, efficiency_mean * (1.0 - deviation))
            efficiency_upper = min(absolute_upper, efficiency_mean * (1.0 + deviation))
            efficiency = float(np.clip(efficiency, efficiency_lower, efficiency_upper))
            process.discharge_efficiency = efficiency
            poison_feed_g_h += (
                args["poison_reversion_per_h"]
                * (poison_mean_g_h - poison_feed_g_h)
                * efficiency_dt_hours
            )
            poison_feed_g_h += (
                args["poison_volatility_g_h_per_sqrt_h"]
                * math.sqrt(efficiency_dt_hours)
                * poison_rng.normal()
            )
            poison_feed_g_h = float(np.clip(poison_feed_g_h, *args["poison_bounds_g_h"]))
            process.F_impurity = poison_feed_g_h / 3600.0
        current_rm2_measured = float(system.point_registry["rM2"].data.value)
        current_rh2_measured = float(system.point_registry["rH2"].data.value)
        current_rm2_sp_request = float(
            system.controller_dictionary["rM2"]._requested_sp.value
        )
        current_rh2_sp_request = float(
            system.controller_dictionary["rH2"]._requested_sp.value
        )
        current_rh2_sp = float(system.point_registry["rH2.sp"].data.value)
        hydrogen_ratio_error = current_rh2_measured - current_rh2_sp
        hydrogen_error_vent_demand = False
        if step_index >= startup_end_step:
            vent_flow = vent.update(float(process.pressure), current_rh2_measured, current_rh2_sp)
            hydrogen_error_vent_demand = vent.hydrogen_error_demand_active
            system.extend_control_element_mv_trajectory("F_vent", vent_flow)

        if step_index % record_every == 0:
            predicted_mfr = float(system.point_registry["cumm_MI"].data.value)
            predicted_density = float(system.point_registry["cumm_density"].data.value)
            lab_mfr = np.nan
            lab_density = np.nan
            if campaign_hour + 1e-9 >= next_lab_hour:
                lab_mfr = predicted_mfr * (
                    1.0 + rng.normal(0.0, args["lab_mfr_relative_error_std"])
                )
                lab_density = predicted_density + rng.normal(
                    0.0, args["lab_density_error_std_kg_m3"]
                )
                next_lab_hour += args["lab_sample_interval_hours"]
            timestamp = CAMPAIGN_START + timedelta(hours=campaign_hour)
            records.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "campaign_hour": campaign_hour,
                    "total_pressure_kpa": float(process.pressure),
                    "pressure_low_limit_kpa": args["pressure_low_limit_kpa"],
                    "pressure_high_limit_kpa": args["pressure_high_limit_kpa"],
                    "pressure_control_sp_kpa": float(
                        system.controller_dictionary["filtered_pressure"].sp_trajectory(
                            system.time
                        )
                    ),
                    "ethylene_partial_pressure_kpa": float(
                        system.point_registry["pM1"].data.value
                    ),
                    "ethylene_partial_pressure_sp_kpa": 700.0,
                    "predicted_density_kg_m3": predicted_density,
                    "density_supervisory_target_kg_m3": float(
                        system.controller_dictionary["cumm_density"].sp_trajectory(system.time)
                    ),
                    "lab_density_kg_m3": lab_density,
                    "comonomer_mole_ratio": current_rm2_measured,
                    "comonomer_mole_ratio_sp_request": current_rm2_sp_request,
                    "comonomer_mole_ratio_sp": float(system.point_registry["rM2.sp"].data.value),
                    "predicted_mfr_g_10min": predicted_mfr,
                    "mfr_supervisory_target_g_10min": float(
                        system.controller_dictionary["cumm_MI"].sp_trajectory(system.time)
                    ),
                    "lab_mfr_g_10min": lab_mfr,
                    "hydrogen_mole_ratio": current_rh2_measured,
                    "hydrogen_mole_ratio_sp_request": current_rh2_sp_request,
                    "hydrogen_mole_ratio_sp": current_rh2_sp,
                    "hydrogen_mole_ratio_error": hydrogen_ratio_error,
                    "catalyst_feed_kg_h": float(process.F_cat) * 3.6,
                    "ethylene_feed_kg_h": float(process.F_m1) * 3.6,
                    "comonomer_feed_kg_h": float(process.F_m2) * 3.6,
                    "hydrogen_feed_kg_h": float(process.F_h2) * 3.6,
                    "nitrogen_feed_kg_h": float(process.F_n2) * 3.6,
                    "nitrogen_preconditioning_active": nitrogen_preconditioning_active,
                    "pressure_precondition_target_kpa": pressure_precondition_target,
                    "vent_flow_kg_h": float(process.F_vent),
                    "vent_requested_kg_h": (
                        args["vent_max_kg_h"]
                        if hydrogen_error_vent_demand or vent.high_pressure_override_active
                        else 0.0
                    ),
                    "vent_hydrogen_error_demand_active": hydrogen_error_vent_demand,
                    "vent_override_active": bool(
                        vent.low_pressure_override_active
                        and (hydrogen_error_vent_demand or vent.high_pressure_override_active)
                    ),
                    "vent_high_pressure_override_active": bool(vent.high_pressure_override_active),
                    "discharge_efficiency": float(process.discharge_efficiency),
                    "discharge_efficiency_mean": efficiency_mean,
                    "poison_feed_g_h": poison_feed_g_h,
                    "poison_feed_mean_g_h": poison_mean_g_h,
                    "catalyst_site1_fraction": catalyst_site1_fraction,
                    "discharge_valve_position": float(process.discharge_valve_position),
                    "production_rate_t_h": float(process.mass_prod_rate),
                    "bed_level_m": float(process.bed_level),
                }
            )

        if step_index < total_steps:
            system.step()

    campaign = pd.DataFrame.from_records(records)
    _build_exports(campaign, switches, args, output_dir)
    print(f"Generated {len(switches)} transitions from one {total_hours:.0f} h campaign.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--scenario", type=Path)
    parsed = parser.parse_args()
    if parsed.isolated_root is None:
        _run_in_isolated_environment(parsed.output_dir, parsed.scenario)
    else:
        _run_campaign(parsed.isolated_root, parsed.output_dir, parsed.scenario)


if __name__ == "__main__":
    main()
