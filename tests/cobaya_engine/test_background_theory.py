"""Tests for the generic Cobaya background Theory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
    build_background_model,
)
from cosmofit.cobaya_engine.background_theory import GenericBackgroundTheory
from cosmofit.cobaya_engine.config_builder import build_cobaya_input


def test_must_provide_collects_unique_sorted_redshifts() -> None:
    theory = _build_theory(_run_config())

    theory.must_provide(Hubble={"z": np.array([0.6, 0.1, 0.6])})
    theory.must_provide(Hubble={"z": np.array([0.3, 0.1])})

    np.testing.assert_allclose(
        theory._requested_redshifts["Hubble"],
        np.array([0.1, 0.3, 0.6]),
    )


def test_theory_matches_pure_background_model_and_unit_conversion() -> None:
    run_config = _run_config()
    theory = _build_theory(run_config)
    pure_model = build_background_model(run_config).bind({"H0": 70.0, "Om": 0.3})
    requested_z = np.array([0.0, 0.5, 1.0])
    theory.must_provide(
        Hubble={"z": requested_z},
        angular_diameter_distance={"z": requested_z},
        comoving_radial_distance={"z": requested_z},
    )

    assert theory.check_cache_and_compute({"H0": 70.0, "Om": 0.3}, want_derived=False)

    np.testing.assert_allclose(
        theory.get_Hubble(requested_z, units="km/s/Mpc"),
        pure_model.hz(requested_z),
    )
    np.testing.assert_allclose(
        theory.get_Hubble(requested_z, units="1/Mpc"),
        np.asarray(pure_model.hz(requested_z), dtype=float) / 299792.458,
    )
    np.testing.assert_allclose(
        theory.get_angular_diameter_distance(requested_z),
        pure_model.angular_diameter_distance(requested_z),
    )
    np.testing.assert_allclose(
        theory.get_comoving_radial_distance(requested_z),
        pure_model.comoving_radial_distance(requested_z),
    )


def test_theory_returns_false_for_invalid_points() -> None:
    theory = _build_theory(_run_config(expression="H0*(Om-(1+z))"))
    theory.must_provide(Hubble={"z": np.array([0.1, 0.3])})

    assert (
        theory.check_cache_and_compute(
            {"H0": 70.0, "Om": 0.3},
            want_derived=False,
        )
        is False
    )


def _build_theory(run_config: RunConfig) -> GenericBackgroundTheory:
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
    return theory


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
            ),
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=11),
        runtime=RuntimeConfig(
            run_label="theory-test",
            output_directory=Path("outputs/theory-test"),
        ),
    )
