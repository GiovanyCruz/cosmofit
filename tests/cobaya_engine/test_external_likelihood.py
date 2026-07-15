"""Tests for the Cobaya cosmic chronometer likelihood adapter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from cobaya.theory import Provider

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
from cosmofit.cobaya_engine.background_theory import GenericBackgroundTheory
from cosmofit.cobaya_engine.config_builder import build_cobaya_input
from cosmofit.cobaya_engine.external_likelihood import (
    CosmicChronometersCobayaLikelihood,
)


def test_external_likelihood_matches_existing_pure_likelihood() -> None:
    run_config = _run_config()
    pure_model = build_background_model(run_config)
    pure_likelihood = build_cosmic_chronometers_likelihood(run_config.datasets[0])
    expected = pure_likelihood.loglike(pure_model, {"H0": 70.0, "Om": 0.3})

    theory, external = _build_theory_and_likelihood(run_config)
    params = {"H0": 70.0, "Om": 0.3}
    provider = Provider(None, {"Hubble": theory})
    provider.set_current_input_params(params)
    theory.initialize_with_provider(provider)
    external.initialize_with_provider(provider)
    assert theory.check_cache_and_compute(dict(params), want_derived=False)

    assert external.logp() == pytest.approx(expected)


def test_invalid_physical_points_are_rejected_with_minus_infinity() -> None:
    run_config = _run_config(expression="H0*(Om-(1+z))")
    theory, external = _build_theory_and_likelihood(run_config)
    params = {"H0": 70.0, "Om": 0.3}
    provider = Provider(None, {"Hubble": theory})
    provider.set_current_input_params(params)
    theory.initialize_with_provider(provider)
    external.initialize_with_provider(provider)

    assert theory.check_cache_and_compute(dict(params), want_derived=False) is False


def test_configuration_requests_hubble_at_dataset_redshifts() -> None:
    run_config = _run_config()
    _, external = _build_theory_and_likelihood(run_config)

    requirements = external.get_requirements()

    np.testing.assert_allclose(
        requirements["Hubble"]["z"],
        np.array([0.10, 0.30, 0.60]),
    )


def _build_theory_and_likelihood(
    run_config: RunConfig,
) -> tuple[GenericBackgroundTheory, CosmicChronometersCobayaLikelihood]:
    cobaya_input = build_cobaya_input(run_config)
    theory_info = next(iter(cobaya_input.info["theory"].values()))
    theory = GenericBackgroundTheory(
        info=theory_info,
        name="background",
        initialize=False,
    )
    for key, value in theory_info.items():
        setattr(theory, key, value)
    theory.input_params = list(theory_info["input_params"])
    theory.initialize_with_params()
    theory.must_provide(
        **{"Hubble": {"z": np.array([0.10, 0.30, 0.60], dtype=float)}}
    )

    like_info = next(iter(cobaya_input.info["likelihood"].values()))
    likelihood = CosmicChronometersCobayaLikelihood(
        info=like_info,
        name="cc",
        initialize=False,
    )
    for key, value in like_info.items():
        setattr(likelihood, key, value)
    likelihood.initialize_with_params()
    return theory, likelihood


def _run_config(*, expression: str = "H0*sqrt(Om*(1+z)**3 + 1-Om)") -> RunConfig:
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
                data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
                name="synthetic-cc",
            ),
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=2),
        runtime=RuntimeConfig(
            run_label="external-like",
            output_directory=Path("outputs/external-like"),
        ),
    )
