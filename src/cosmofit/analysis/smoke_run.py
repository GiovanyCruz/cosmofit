"""Command-line smoke utility for GetDist analysis of a completed run."""

from __future__ import annotations

import argparse
from pathlib import Path

from cosmofit.analysis.service import PosteriorAnalysisService


def main(argv: list[str] | None = None) -> int:
    """Analyze an existing completed run and emit summary and plot artifacts."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "run_directory",
        type=Path,
        help="Completed CosmoFit run directory.",
    )
    parser.add_argument(
        "--parameters",
        default=None,
        help="Optional comma-separated sampled parameter list for triangle plotting.",
    )
    parser.add_argument(
        "--ignore-rows",
        type=float,
        default=0.0,
        help="Fraction of initial rows to ignore when loading chains.",
    )
    args = parser.parse_args(argv)

    service = PosteriorAnalysisService(ignore_rows=args.ignore_rows)
    run_analysis = service.open_run(args.run_directory)
    summary_json = service.export_summary_json()
    summary_csv = service.export_summary_csv()

    generated_paths: list[Path] = [summary_json, summary_csv]
    for parameter in service.parameter_names():
        plot_paths = service.plot_1d(parameter)
        generated_paths.extend([plot_paths.png_path, plot_paths.pdf_path])

    selected_parameters = (
        tuple(item.strip() for item in args.parameters.split(",") if item.strip())
        if args.parameters
        else run_analysis.selectable_parameters
    )
    if len(selected_parameters) >= 2:
        triangle_paths = service.triangle_plot(selected_parameters)
        generated_paths.extend([triangle_paths.png_path, triangle_paths.pdf_path])

    for path in generated_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
