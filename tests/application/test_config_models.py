"""Tests for application-level Cobaya run configuration models."""

from __future__ import annotations

from pathlib import Path

import pytest

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    SupernovaDatasetConfig,
    UniformPriorConfig,
    deserialize_run_config,
    serialize_run_config,
)
from cosmofit.cosmology.validators import ParameterDefinitionError


def test_sampled_parameter_requires_prior_reference_and_positive_proposal() -> None:
    with pytest.raises(ParameterDefinitionError, match="requires a prior"):
        ParameterConfig(
            name="Om",
            symbol="Om",
            role="sampled",
            reference=0.3,
            proposal=0.02,
        )


def test_run_config_round_trips_through_serialization() -> None:
    run_config = _example_run_config()

    restored = deserialize_run_config(serialize_run_config(run_config))

    assert restored == run_config


def test_run_config_supports_mixed_dataset_selection() -> None:
    run_config = _example_run_config()

    assert run_config.datasets == (
        CosmicChronometerDatasetConfig(
            kind="cosmic_chronometers",
            data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
        ),
        SupernovaDatasetConfig(kind="sn.pantheonplus"),
    )


def test_supernova_absolute_magnitude_mode_requires_future_contract() -> None:
    with pytest.raises(ParameterDefinitionError, match="Mb parameter contract"):
        SupernovaDatasetConfig(
            kind="sn.pantheonplus",
            use_absolute_magnitude=True,
        )


def _example_run_config() -> RunConfig:
    return RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression="H0*sqrt(Om*(1+z)**3 + 1-Om)",
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
                role="fixed",
                value=0.3,
            ),
        ),
        datasets=(
            CosmicChronometerDatasetConfig(
                kind="cosmic_chronometers",
                data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
            ),
            SupernovaDatasetConfig(kind="sn.pantheonplus"),
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=1234, max_samples=10),
        runtime=RuntimeConfig(
            run_label="example",
            output_directory=Path("outputs/example"),
        ),
    )
