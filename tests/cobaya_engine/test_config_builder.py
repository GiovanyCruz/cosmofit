"""Tests for Cobaya input translation."""

from __future__ import annotations

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
from cosmofit.cobaya_engine.config_builder import build_cobaya_input


def test_sampled_parameter_translation_contains_uniform_prior_reference_and_proposal(
) -> None:
    cobaya_input = build_cobaya_input(_run_config())

    assert cobaya_input.info["params"]["H0"] == {
        "prior": {"min": 50.0, "max": 90.0},
        "ref": 70.0,
        "proposal": 1.0,
    }


def test_fixed_parameter_translation_uses_value_block() -> None:
    cobaya_input = build_cobaya_input(_run_config())

    assert cobaya_input.info["params"]["Om"] == {"value": 0.3}


def test_generated_configuration_contains_no_pyside6_dependency() -> None:
    cobaya_input = build_cobaya_input(_run_config())

    assert "PySide6" not in str(cobaya_input.info)


def _run_config() -> RunConfig:
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
            ParameterConfig(name="Om", symbol="Om", role="fixed", value=0.3),
        ),
        dataset=CosmicChronometerDatasetConfig(
            kind="cosmic_chronometers",
            data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
            name="synthetic-cc",
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=9, max_samples=10),
        runtime=RuntimeConfig(
            run_label="config-builder",
            output_directory=Path("outputs/config-builder"),
        ),
    )
