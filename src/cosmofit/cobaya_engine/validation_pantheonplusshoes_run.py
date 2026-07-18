"""Validation run for flat LCDM with Pantheon+SH0ES."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from cosmofit.application import (
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    SupernovaDatasetConfig,
    UniformPriorConfig,
)
from cosmofit.cobaya_engine.runner import run_in_subprocess

VALIDATION_EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"


def main(argv: list[str] | None = None) -> int:
    """Run flat LCDM against Pantheon+SH0ES."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "outputs/validation_pantheonplusshoes_lcdm"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
    )
    args = parser.parse_args(argv)

    run_directory = (
        args.output_root
        / _default_run_label()
    )

    run_config = RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=VALIDATION_EXPRESSION,
            allowed_functions=("sqrt",),
        ),
        parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="fixed",
                unit="km/s/Mpc",
                value=70.0,
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
            SupernovaDatasetConfig(
                kind="sn.pantheonplusshoes",
            ),
        ),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=20260718,
            max_samples=10000,
            burn_in=200,
            learn_proposal=True,
            Rminus1_stop=0.01,
            Rminus1_cl_stop=0.05,
        ),
        runtime=RuntimeConfig(
            run_label="validation-pantheonplusshoes-lcdm",
            output_directory=run_directory,
            overwrite=args.overwrite,
        ),
    )

    result = run_in_subprocess(run_config)
    print(result.artifacts.run_directory)
    return result.return_code


def _default_run_label() -> str:
    timestamp = datetime.now(
        tz=UTC
    ).strftime("%Y%m%dT%H%M%SZ")

    return (
        "validation-pantheonplusshoes-lcdm-"
        + timestamp
    )


if __name__ == "__main__":
    sys.exit(main())
