"""Sensitivity of posterior summaries to GetDist ignore_rows."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from workflow import OUTPUTS, SUMMARIES, analyze_run


IGNORE_ROWS_VALUES = (0.0, 0.1, 0.2, 0.3)
SEEDS = range(314159, 314164)

OUTPUT_CSV = SUMMARIES / "ignore_rows_sensitivity.csv"
SUMMARY_CSV = SUMMARIES / "ignore_rows_sensitivity_summary.csv"


def main() -> int:
    root = OUTPUTS / "real_cc_seed_repeatability"

    rows: list[dict[str, object]] = []

    for seed in SEEDS:
        for workflow in ("cosmofit", "direct_cobaya"):
            run_directory = root / f"seed-{seed}" / workflow

            for ignore_rows in IGNORE_ROWS_VALUES:
                result = analyze_run(
                    run_directory,
                    ignore_rows=ignore_rows,
                )

                rows.append(
                    {
                        "seed": seed,
                        "workflow": workflow,
                        "ignore_rows": ignore_rows,
                        "converged": result["converged"],
                        "rminus1_last": result["rminus1_last"],
                        "H0_mean": result["H0"]["mean"],
                        "H0_sigma": result["H0"]["sigma"],
                        "Om_mean": result["Om"]["mean"],
                        "Om_sigma": result["Om"]["sigma"],
                        "ESS_H0": result["effective_sample_size_H0"],
                        "ESS_Om": result["effective_sample_size_Om"],
                        "retained_rows": result["retained_rows"],
                        "retained_total_weight": result["retained_total_weight"],
                    }
                )

    _write_csv(OUTPUT_CSV, rows)

    summary_rows = build_summary(rows)
    _write_csv(SUMMARY_CSV, summary_rows)

    print(f"Wrote: {OUTPUT_CSV}")
    print(f"Wrote: {SUMMARY_CSV}")

    print()
    print("Sensitivity relative to ignore_rows = 0:")
    for row in summary_rows:
        print(
            f"{row['workflow']:13s} "
            f"ignore_rows={row['ignore_rows']:.1f}  "
            f"dH0_mean={row['delta_H0_mean_percent']:.4f}%  "
            f"dH0_sigma={row['delta_H0_sigma_percent']:.4f}%  "
            f"dOm_mean={row['delta_Om_mean_percent']:.4f}%  "
            f"dOm_sigma={row['delta_Om_sigma_percent']:.4f}%"
        )

    return 0


def build_summary(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []

    for workflow in ("cosmofit", "direct_cobaya"):
        workflow_rows = [
            row
            for row in rows
            if row["workflow"] == workflow
        ]

        reference = [
            row
            for row in workflow_rows
            if float(row["ignore_rows"]) == 0.0
        ]

        ref_H0_mean = np.mean(
            [float(row["H0_mean"]) for row in reference]
        )
        ref_H0_sigma = np.mean(
            [float(row["H0_sigma"]) for row in reference]
        )
        ref_Om_mean = np.mean(
            [float(row["Om_mean"]) for row in reference]
        )
        ref_Om_sigma = np.mean(
            [float(row["Om_sigma"]) for row in reference]
        )

        for ignore_rows in IGNORE_ROWS_VALUES:
            selected = [
                row
                for row in workflow_rows
                if float(row["ignore_rows"]) == ignore_rows
            ]

            H0_mean = np.mean(
                [float(row["H0_mean"]) for row in selected]
            )
            H0_sigma = np.mean(
                [float(row["H0_sigma"]) for row in selected]
            )
            Om_mean = np.mean(
                [float(row["Om_mean"]) for row in selected]
            )
            Om_sigma = np.mean(
                [float(row["Om_sigma"]) for row in selected]
            )

            summary.append(
                {
                    "workflow": workflow,
                    "ignore_rows": ignore_rows,
                    "mean_H0": H0_mean,
                    "mean_H0_sigma": H0_sigma,
                    "mean_Om": Om_mean,
                    "mean_Om_sigma": Om_sigma,
                    "delta_H0_mean_percent": _percent_change(
                        H0_mean, ref_H0_mean
                    ),
                    "delta_H0_sigma_percent": _percent_change(
                        H0_sigma, ref_H0_sigma
                    ),
                    "delta_Om_mean_percent": _percent_change(
                        Om_mean, ref_Om_mean
                    ),
                    "delta_Om_sigma_percent": _percent_change(
                        Om_sigma, ref_Om_sigma
                    ),
                    "mean_ESS_H0": np.mean(
                        [float(row["ESS_H0"]) for row in selected]
                    ),
                    "mean_ESS_Om": np.mean(
                        [float(row["ESS_Om"]) for row in selected]
                    ),
                    "mean_retained_rows": np.mean(
                        [float(row["retained_rows"]) for row in selected]
                    ),
                }
            )

    return summary


def _percent_change(value: float, reference: float) -> float:
    return 100.0 * (value - reference) / reference


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
