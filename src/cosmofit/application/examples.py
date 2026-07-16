"""Predefined application-level example configurations."""

from __future__ import annotations

from pathlib import Path

from cosmofit.application.config_models import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
)

LCDM_EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"


def build_lcdm_example_run_config(*, output_directory: Path) -> RunConfig:
    """Return the milestone LCDM example configuration."""

    return RunConfig(
        schema_version=1,
        model=ModelConfig(kind="hz_expression_flat", expression=LCDM_EXPRESSION),
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
                data_path=default_cosmic_chronometer_path(),
                name="synthetic-cc",
            ),
        ),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=314159,
            max_samples=2000,
            burn_in=0,
            learn_proposal=False,
            Rminus1_stop=0.01,
            Rminus1_cl_stop=0.2,
        ),
        runtime=RuntimeConfig(
            run_label="lcdm-example",
            output_directory=output_directory,
            overwrite=False,
        ),
    )


def default_cosmic_chronometer_path() -> Path:
    """Return the repository synthetic chronometer fixture path."""

    return (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "cosmic_chronometers_synth.csv"
    )
