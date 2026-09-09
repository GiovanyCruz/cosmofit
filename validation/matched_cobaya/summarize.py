"""Build descriptive tables, plots, and a concise validation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from workflow import (
    OUTPUTS,
    PLOTS,
    SUMMARIES,
    aggregate_realizations,
    aggregate_seed_workflows,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--realizations", type=Path, default=SUMMARIES / "realizations.json"
    )
    parser.add_argument(
        "--seed-comparison", type=Path, default=SUMMARIES / "mcmc_seed_comparison.json"
    )
    args = parser.parse_args()
    realization_rows = _read_rows(args.realizations)
    seed_rows = _read_rows(args.seed_comparison)
    PLOTS.mkdir(parents=True, exist_ok=True)
    if realization_rows:
        _recovery_plot(realization_rows, "H0", 70.0, PLOTS / "recovered_H0")
        _recovery_plot(realization_rows, "Om", 0.30, PLOTS / "recovered_Om")
        _pull_plot(realization_rows, "H0", PLOTS / "H0_pulls")
        _pull_plot(realization_rows, "Om", PLOTS / "Om_pulls")
    report = {
        "realization_aggregate": aggregate_realizations(realization_rows),
        "mcmc_seed_aggregate": aggregate_seed_workflows(seed_rows),
        "interpretation": _interpretation(seed_rows),
        "plots_directory": str(PLOTS),
        "outputs_directory": str(OUTPUTS),
    }
    path = SUMMARIES / "validation_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report, SUMMARIES / "validation_report.md")
    print(path)
    return 0


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def _recovery_plot(
    rows: list[dict[str, Any]], parameter: str, fiducial: float, path: Path
) -> None:
    good = [
        row
        for row in rows
        if row.get("run_status") == "succeeded" and row.get("converged") is True
    ]
    numbers = [row["realization"] for row in good]
    means = [row[f"{parameter}_posterior_mean"] for row in good]
    errors = [row[f"{parameter}_posterior_sigma"] for row in good]
    figure, axis = plt.subplots(figsize=(7.2, 4.5))
    axis.errorbar(
        numbers,
        means,
        yerr=errors,
        fmt="o",
        capsize=3,
        color="tab:blue",
        label="posterior mean ± 1σ",
    )
    axis.axhline(fiducial, color="black", linestyle="--", label="fiducial")
    axis.set(
        xlabel="Realization",
        ylabel=parameter,
        title=f"Recovered {parameter} across independent CC realizations",
    )
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    _save(figure, path)


def _pull_plot(rows: list[dict[str, Any]], parameter: str, path: Path) -> None:
    pulls = [
        row[f"{parameter}_pull"]
        for row in rows
        if row.get("run_status") == "succeeded" and row.get("converged") is True
    ]
    figure, axis = plt.subplots(figsize=(6.5, 4.2))
    bins = max(3, min(10, len(pulls)))
    axis.hist(pulls, bins=bins, color="tab:orange", edgecolor="black")
    axis.axvline(0.0, color="black", linestyle="--")
    axis.set(
        xlabel=f"{parameter} pull",
        ylabel="Number of realizations",
        title=f"Distribution of {parameter} pulls",
    )
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    _save(figure, path)


def _save(figure: plt.Figure, path: Path) -> None:
    figure.savefig(path.with_suffix(".png"), dpi=180)
    figure.savefig(path.with_suffix(".pdf"))
    plt.close(figure)


def _interpretation(rows: list[dict[str, Any]]) -> str:
    aggregate = aggregate_seed_workflows(rows)
    pairs = aggregate["paired_relative_sigma_differences_percent"]
    if not pairs["H0"]["values"] or not pairs["Om"]["values"]:
        return (
            "No converged paired seed runs are available; no statement about "
            "finite-MCMC variability is made."
        )
    return (
        "The report presents observed paired width differences and their "
        "distribution. It makes no attribution of any historical difference "
        "unless the production seed experiment supports that inference."
    )


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    realization = report["realization_aggregate"]
    lines = [
        "# Matched-Cobaya validation report",
        "",
        (
            "This report is descriptive. Non-converged runs are excluded from "
            "aggregate recovery metrics."
        ),
        "",
        (
            "Independent converged realizations included: "
            f"{realization['included_realizations']}"
        ),
        f"Excluded realizations: {realization['excluded_realizations']}",
        "",
        "## Paired MCMC-width differences",
        "",
    ]
    for parameter, values in report["mcmc_seed_aggregate"][
        "paired_relative_sigma_differences_percent"
    ].items():
        lines.append(
            f"- {parameter}: values={values['values']}; mean={values['mean']}; "
            f"SD={values['standard_deviation']}"
        )
    lines.extend(["", report["interpretation"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
