"""Render the Stage 2 trend evidence as a presentation-sized PNG."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components import build_transition_figure, export_vlm_png, load_repository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transition_ids", nargs="*", default=["TR-01", "TR-03", "TR-05"])
    parser.add_argument("--focal-id", default="TR-05")
    parser.add_argument(
        "--layout",
        choices=("overview", "pressure_vent"),
        default="overview",
    )
    parser.add_argument("--start-hour", type=float)
    parser.add_argument("--end-hour", type=float)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".cache/review/workspace_overview.png",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    window = None
    if args.start_hour is not None or args.end_hour is not None:
        if args.start_hour is None or args.end_hour is None:
            raise SystemExit("--start-hour and --end-hour must be supplied together")
        window = (args.start_hour, args.end_hour)
    figure = build_transition_figure(
        load_repository(),
        args.transition_ids,
        args.focal_id,
        window,
        args.layout,
        simplified=True,
    )
    export_vlm_png(figure, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
