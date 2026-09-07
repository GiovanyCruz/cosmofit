"""Run paired CosmoFit/direct-Cobaya finite-chain seed experiment."""

from __future__ import annotations

import argparse
import json

from workflow import (
    FIXED_DATASET,
    OUTPUTS,
    aggregate_seed_workflows,
    analyze_run,
    canonical_science_config,
    compare_science_configs,
    flatten_result,
    run_cosmofit,
    run_direct_cobaya,
    write_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=314159)
    args = parser.parse_args()
    count = 2 if args.smoke else args.n_seeds
    if count <= 0:
        parser.error("--n-seeds must be positive")
    root = OUTPUTS / "seed_repeatability"
    science = canonical_science_config(FIXED_DATASET)
    differences = compare_science_configs(science, science)
    (root / "configuration_comparison.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "configuration_comparison.json").write_text(
        json.dumps(
            {"cosmofit": science, "direct_cobaya": science, "differences": differences},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if differences:
        raise RuntimeError(
            f"Scientifically meaningful configuration differences: {differences}"
        )
    rows = []
    for seed in range(args.seed_base, args.seed_base + count):
        pair = root / f"seed-{seed}"
        paths = {"cosmofit": pair / "cosmofit", "direct_cobaya": pair / "direct_cobaya"}
        codes = {
            "cosmofit": run_cosmofit(
                FIXED_DATASET,
                paths["cosmofit"],
                seed=seed,
                label=f"referee2-seed-{seed}",
            ),
            "direct_cobaya": run_direct_cobaya(
                FIXED_DATASET, paths["direct_cobaya"], seed=seed
            ),
        }
        for name, path in paths.items():
            rows.append(
                flatten_result(analyze_run(path), seed=seed, workflow=name)
                if codes[name] == 0
                else {
                    "random_seed": seed,
                    "workflow": name,
                    "run_status": "failed",
                    "run_directory": str(path),
                }
            )
    write_rows(rows, "mcmc_seed_comparison")
    (root / "aggregate.json").write_text(
        json.dumps(aggregate_seed_workflows(rows), indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
