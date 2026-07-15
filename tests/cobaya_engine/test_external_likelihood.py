"""Tests for the Cobaya external likelihood adapter."""

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
    UniformPriorConfig,
    build_background_model,
    build_cosmic_chronometers_likelihood,
)
from cosmofit.cobaya_engine.config_builder import build_cobaya_input
from cosmofit.cobaya_engine.external_likelihood import (
    CosmicChronometersCobayaLikelihood,
)


def test_external_likelihood_matches_existing_pure_likelihood() -> None:
    run_config = _run_config(expression="H0*sqrt(Om*(1+z)**3 + 1-Om)")
    pure_model = build_background_model(run_config)
    pure_likelihood = build_cosmic_chronometers_likelihood(run_config.dataset)
    expected = pure_likelihood.loglike(pure_model, {"H0": 70.0})

    external = _build_external_likelihood(run_config)

    assert external.logp(H0=70.0) == pytest.approx(expected)


def test_invalid_physical_points_are_rejected_with_minus_infinity() -> None:
    external = _build_external_likelihood(_run_config(expression="H0*(Om-(1+z))"))

    assert external.logp(H0=70.0) == float("-inf")


def test_configuration_errors_are_not_silently_converted_to_minus_infinity() -> None:
    external = _build_external_likelihood(_run_config(expression="H0*(1+z)"))

    with pytest.raises(KeyError):
        external.logp()


def _build_external_likelihood(
    run_config: RunConfig,
) -> CosmicChronometersCobayaLikelihood:
    cobaya_input = build_cobaya_input(run_config)
    info = next(iter(cobaya_input.info["likelihood"].values()))
    likelihood = CosmicChronometersCobayaLikelihood(
        info=info,
        name="cc",
        initialize=False,
    )
    for key, value in info.items():
        setattr(likelihood, key, value)
    likelihood.initialize_with_params()
    return likelihood


def _run_config(*, expression: str) -> RunConfig:
    return RunConfig(
        schema_version=1,
        model=ModelConfig(kind="hz_expression_flat", expression=expression),
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
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=2),
        runtime=RuntimeConfig(
            run_label="external-like",
            output_directory=Path("outputs/external-like"),
        ),
    )
