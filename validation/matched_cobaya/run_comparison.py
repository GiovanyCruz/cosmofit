"""Controlled native-seed comparison on the historical real 18-point CC data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from workflow import (
    OUTPUTS,
    REAL_CC_DATASET,
    REAL_CC_DATASET_SHA256,
    SUMMARIES,
    analyze_run,
    canonical_science_config,
    checksum,
    compare_science_configs,
    flatten_result,
    run_cosmofit,
    run_direct_cobaya,
    write_rows,
)

HISTORICAL_WIDTH_DIFFERENCES = {"H0": 6.1324, "Om": 4.6342}
RESULTS_CSV = Path(__file__).resolve().parents[1] / "results" / "real_cc_ess_pairs.csv"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=314159)
    args = parser.parse_args()
    count = 2 if args.smoke else args.n_seeds
    if count <= 0:
        parser.error("--n-seeds must be positive")
    if checksum(REAL_CC_DATASET) != REAL_CC_DATASET_SHA256:
        raise RuntimeError(
            "The real-CC dataset checksum does not match the historical input."
        )

    root = OUTPUTS / "real_cc_seed_repeatability"
    rows: list[dict[str, Any]] = []
    ess_rows: list[dict[str, Any]] = []
    for seed in range(args.seed_base, args.seed_base + count):
        pair = root / f"seed-{seed}"
        cosmofit_config = canonical_science_config(
            REAL_CC_DATASET, native_cobaya_seed=seed
        )
        direct_config = canonical_science_config(
            REAL_CC_DATASET, native_cobaya_seed=seed
        )
        differences = compare_science_configs(cosmofit_config, direct_config)
        pair.mkdir(parents=True, exist_ok=True)
        _write_json(
            pair / "configuration_comparison.json",
            {
                "cosmofit": cosmofit_config,
                "direct_cobaya": direct_config,
                "differences": differences,
                "architectural_difference": (
                    "CosmoFit uses its generic background theory and CC adapter; "
                    "direct Cobaya uses an external direct Gaussian likelihood."
                ),
            },
        )
        if differences:
            raise RuntimeError(f"Seed {seed} configuration mismatch: {differences}")

        paths = {
            "cosmofit": pair / "cosmofit",
            "direct_cobaya": pair / "direct_cobaya",
        }
        codes = {
            "cosmofit": run_cosmofit(
                REAL_CC_DATASET,
                paths["cosmofit"],
                seed=seed,
                label=f"matched-cobaya-real-cc-seed-{seed}",
                dataset_name="cosmic-chronometers-18",
            ),
            "direct_cobaya": run_direct_cobaya(
                REAL_CC_DATASET, paths["direct_cobaya"], seed=seed
            ),
        }
        results: dict[str, dict[str, Any]] = {}
        for workflow, path in paths.items():
            if codes[workflow] == 0:
                result = analyze_run(path, ignore_rows=0.3)
                results[workflow] = result
                rows.append(flatten_result(result, seed=seed, workflow=workflow))
            else:
                rows.append(
                    {
                        "random_seed": seed,
                        "workflow": workflow,
                        "run_status": "failed",
                        "run_directory": str(path),
                    }
                )
        if set(results) == {"cosmofit", "direct_cobaya"}:
            ess_rows.append(_ess_row(seed, results))

    write_rows(rows, "real_cc_seed_comparison")
    _write_csv(RESULTS_CSV, ess_rows)
    _write_json(
        root / "aggregate.json",
        report := {
            "dataset": str(REAL_CC_DATASET),
            "dataset_sha256": REAL_CC_DATASET_SHA256,
            "analysis": "GetDist weighted covariance with ignore_rows=0.3",
            "historical_width_differences_percent": HISTORICAL_WIDTH_DIFFERENCES,
            "paired_statistics": _paired_statistics(ess_rows),
            "workflow_statistics": _workflow_statistics(rows),
            "ess_pairs": ess_rows,
        },
    )
    _write_comparison_report(SUMMARIES / "real_cc_comparison_report.md", report)
    return 0


def _ess_row(seed: int, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cosmofit, direct = results["cosmofit"], results["direct_cobaya"]
    return {
        "seed": seed,
        "ESS_H0_CosmoFit": cosmofit["effective_sample_size_H0"],
        "ESS_H0_direct": direct["effective_sample_size_H0"],
        "delta_sigma_H0_percent": _relative_to_direct(cosmofit, direct, "H0"),
        "ESS_Om_CosmoFit": cosmofit["effective_sample_size_Om"],
        "ESS_Om_direct": direct["effective_sample_size_Om"],
        "delta_sigma_Om_percent": _relative_to_direct(cosmofit, direct, "Om"),
    }


def _relative_to_direct(
    cosmofit: dict[str, Any], direct: dict[str, Any], parameter: str
) -> float:
    first = cosmofit[parameter]["sigma"]
    second = direct[parameter]["sigma"]
    return 100.0 * abs(first - second) / second


def _paired_statistics(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for parameter in ("H0", "Om"):
        values = np.array([row[f"delta_sigma_{parameter}_percent"] for row in rows])
        result[parameter] = {
            "values": values.tolist(),
            "mean": _mean(values),
            "standard_deviation": _std(values),
            "minimum": float(np.min(values)) if len(values) else None,
            "maximum": float(np.max(values)) if len(values) else None,
            "median": float(np.median(values)) if len(values) else None,
        }
    return result


def _workflow_statistics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for workflow in ("cosmofit", "direct_cobaya"):
        selected = [
            row
            for row in rows
            if row.get("workflow") == workflow
            and row.get("run_status") == "succeeded"
            and row.get("converged") is True
        ]
        output[workflow] = {}
        for parameter in ("H0", "Om"):
            sigmas = np.array([row[f"{parameter}_posterior_sigma"] for row in selected])
            ess = np.array(
                [row[f"effective_sample_size_{parameter}"] for row in selected]
            )
            output[workflow][parameter] = {
                "mean_posterior_sigma": _mean(sigmas),
                "standard_deviation_posterior_sigma": _std(sigmas),
                "coefficient_of_variation": _coefficient_of_variation(sigmas),
                "mean_ess": _mean(ess),
                "minimum_ess": float(np.min(ess)) if len(ess) else None,
                "mean_accepted_sample_count": _mean(
                    np.array([row["accepted_sample_count"] for row in selected])
                ),
            }
    return output


def _mean(values: np.ndarray) -> float | None:
    return float(np.mean(values)) if len(values) else None


def _std(values: np.ndarray) -> float | None:
    return float(np.std(values, ddof=1)) if len(values) > 1 else None


def _coefficient_of_variation(values: np.ndarray) -> float | None:
    mean, standard_deviation = _mean(values), _std(values)
    if mean in (None, 0.0) or standard_deviation is None:
        return None
    return standard_deviation / mean


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_comparison_report(path: Path, report: dict[str, Any]) -> None:
    paired = report["paired_statistics"]
    lines = [
        "# Real-CC matched-seed comparison",
        "",
        "## 1. Historical single-pair real-CC comparison",
        "",
        "Historical width differences: H0=6.1324%, Om=4.6342%.",
        "",
        "## 2. Controlled repeated-seed real-CC comparison",
        "",
        f"Dataset SHA-256: `{report['dataset_sha256']}`.",
        f"H0 paired differences: {paired['H0']['values']}%.",
        f"Om paired differences: {paired['Om']['values']}%.",
        "",
        "## 3. Synthetic 20-realization recovery experiment",
        "",
        "Separate experiment; not included in these real-CC statistics.",
        "",
        "## 4. Synthetic paired-seed experiment",
        "",
        "Separate experiment; not included in these real-CC statistics.",
        "",
        "ESS differences are reported descriptively and do not establish causation.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
