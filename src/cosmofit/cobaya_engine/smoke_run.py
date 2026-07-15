"""Command-line smoke run for the milestone-1 flat LCDM cosmic chronometer path."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
)
from cosmofit.cobaya_engine.runner import run_in_subprocess

SMOKE_EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"


def main(argv: list[str] | None = None) -> int:
    """Run the predefined milestone-1 cosmic chronometer smoke test."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/smoke_cc_lcdm"),
        help="Parent directory for the isolated smoke-run artifact directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow reuse of an existing resolved run directory.",
    )
    args = parser.parse_args(argv)

    run_directory = args.output_root / _default_run_label()
    run_config = RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=SMOKE_EXPRESSION,
            allowed_functions=("sqrt",),
        ),
        parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="sampled",
                unit="km/s/Mpc",
                prior=UniformPriorConfig(minimum=50.0, maximum=90.0),
                reference=70.0,
                proposal=1.0,
            ),
            ParameterConfig(
                name="Om",
                symbol="Om",
                role="sampled",
                prior=UniformPriorConfig(minimum=0.1, maximum=0.5),
                reference=0.3,
                proposal=0.02,
            ),
        ),
        datasets=(
            CosmicChronometerDatasetConfig(
                kind="cosmic_chronometers",
                data_path=_fixture_path(),
                name="synthetic-cc",
            ),
        ),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=314159,
            max_samples=40,
            burn_in=0,
            learn_proposal=False,
            Rminus1_stop=5.0,
            Rminus1_cl_stop=5.0,
        ),
        runtime=RuntimeConfig(
            run_label="smoke-cc-lcdm",
            output_directory=run_directory,
            overwrite=args.overwrite,
        ),
    )

    result = run_in_subprocess(run_config)
    print(result.artifacts.run_directory)
    return result.return_code


def _fixture_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "cosmic_chronometers_synth.csv"
    )


def _default_run_label() -> str:
    return "smoke-cc-lcdm-" + datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
