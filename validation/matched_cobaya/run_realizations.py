"""Run independent CC synthetic-realization recovery experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow import (
    OUTPUTS,
    aggregate_realizations,
    analyze_run,
    flatten_result,
    generate_dataset,
    run_cosmofit,
    write_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--n-realizations", type=int, default=20)
    parser.add_argument("--seed-base", type=int, default=20260718)
    args = parser.parse_args()
    count = 3 if args.smoke else args.n_realizations
    if count <= 0:
        parser.error("--n-realizations must be positive")
    rows = []
    for number in range(1, count + 1):
        seed = args.seed_base + number - 1
        directory = OUTPUTS / "realizations" / f"realization-{number:03d}-seed-{seed}"
        dataset = directory / "dataset" / "synthetic_cc.csv"
        if not dataset.exists():
            generate_dataset(dataset, seed=seed)
        code = run_cosmofit(
            dataset,
            directory / "cosmofit",
            seed=seed,
            label=f"matched-cobaya-realization-{number:03d}",
        )
        if code == 0:
            rows.append(
                flatten_result(
                    analyze_run(directory / "cosmofit"),
                    realization=number,
                    seed=seed,
                    workflow="cosmofit",
                )
            )
        else:
            rows.append(
                {
                    "realization": number,
                    "random_seed": seed,
                    "workflow": "cosmofit",
                    "run_status": "failed",
                    "run_directory": str(directory / "cosmofit"),
                }
            )
    write_rows(rows, "realizations")
    Path(OUTPUTS / "realizations" / "aggregate.json").write_text(
        json.dumps(aggregate_realizations(rows), indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
