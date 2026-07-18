"""Synthetic parameter-recovery validation for flat LCDM."""

from __future__ import annotations

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

EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"


def main() -> int:
    run_directory = (
        Path("outputs/synthetic_recovery_cc_lcdm")
        / _default_run_label()
    )

    run_config = RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=EXPRESSION,
            allowed_functions=("sqrt",),
        ),
        parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="sampled",
                unit="km/s/Mpc",
                prior=UniformPriorConfig(
                    minimum=50.0,
                    maximum=90.0,
                ),
                reference=70.0,
                proposal=1.0,
            ),
            ParameterConfig(
                name="Om",
                symbol="Om",
                role="sampled",
                prior=UniformPriorConfig(
                    minimum=0.05,
                    maximum=0.60,
                ),
                reference=0.30,
                proposal=0.02,
            ),
        ),
        datasets=(
            CosmicChronometerDatasetConfig(
                kind="cosmic_chronometers",
                data_path=_dataset_path(),
                name="synthetic-recovery-cc",
            ),
        ),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=20260717,
            max_samples=10000,
            burn_in=200,
            learn_proposal=True,
            Rminus1_stop=0.01,
            Rminus1_cl_stop=0.05,
        ),
        runtime=RuntimeConfig(
            run_label="synthetic-recovery-cc-lcdm",
            output_directory=run_directory,
            overwrite=False,
        ),
    )

    result = run_in_subprocess(run_config)
    print(result.artifacts.run_directory)
    return result.return_code


def _dataset_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "data"
        / "cosmic_chronometers_synthetic_recovery_input.csv"
    )


def _default_run_label() -> str:
    return (
        "synthetic-recovery-cc-lcdm-"
        + datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    )


if __name__ == "__main__":
    sys.exit(main())
