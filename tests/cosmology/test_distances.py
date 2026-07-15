"""Regression tests for flat-background distance observables."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from cosmofit.cosmology import (
    SPEED_OF_LIGHT_KM_PER_S,
    NumericalValidationError,
    ParameterDefinitionError,
    flat_lcdm_example,
)


def test_flat_lcdm_distances_match_independent_reference_values() -> None:
    bound = flat_lcdm_example().bind({"H0": 70.0, "Om": 0.3})
    z = 1.0

    assert bound.hz(z) == pytest.approx(123.24771803161305)
    assert bound.comoving_radial_distance(z) == pytest.approx(3303.8288058874678)
    assert bound.angular_diameter_distance(z) == pytest.approx(1651.9144029437339)
    assert bound.luminosity_distance(z) == pytest.approx(6607.6576117749355)
    assert bound.distance_modulus(z) == pytest.approx(44.10023765554372)


def test_distances_match_independent_quad_reference() -> None:
    bound = flat_lcdm_example().bind({"H0": 67.4, "Om": 0.315})
    z = np.array([0.1, 0.5, 1.0])
    expected = np.array([_quad_distance(redshift, H0=67.4, Om=0.315) for redshift in z])

    np.testing.assert_allclose(bound.comoving_radial_distance(z), expected)


def test_etherington_relation_scalar_and_array_consistency() -> None:
    bound = flat_lcdm_example().bind({"H0": 70.0, "Om": 0.3})
    z = np.array([0.1, 0.4, 1.0])

    luminosity = np.asarray(bound.luminosity_distance(z), dtype=float)
    angular = np.asarray(bound.angular_diameter_distance(z), dtype=float)
    np.testing.assert_allclose(luminosity, (1.0 + z) ** 2 * angular)
    assert bound.luminosity_distance(0.4) == pytest.approx(luminosity[1])
    assert bound.angular_diameter_distance(0.4) == pytest.approx(angular[1])


def test_unsorted_and_repeated_redshifts_are_supported() -> None:
    bound = flat_lcdm_example().bind({"H0": 70.0, "Om": 0.3})
    z = np.array([1.0, 0.0, 0.5, 0.5, 0.1])

    result = np.asarray(bound.comoving_radial_distance(z), dtype=float)
    expected = np.asarray(
        [
            bound.comoving_radial_distance(1.0),
            0.0,
            bound.comoving_radial_distance(0.5),
            bound.comoving_radial_distance(0.5),
            bound.comoving_radial_distance(0.1),
        ],
        dtype=float,
    )

    np.testing.assert_allclose(result, expected)


def test_invalid_redshift_inputs_are_rejected() -> None:
    bound = flat_lcdm_example().bind({"H0": 70.0, "Om": 0.3})

    with pytest.raises(ParameterDefinitionError, match="non-negative"):
        bound.comoving_radial_distance(-0.1)
    with pytest.raises(ParameterDefinitionError, match="finite"):
        bound.comoving_radial_distance(np.array([0.1, np.nan]))
    with pytest.raises(ParameterDefinitionError, match="one-dimensional"):
        bound.comoving_radial_distance(np.array([[0.1, 0.2]]))


def test_distance_modulus_is_undefined_at_zero_redshift() -> None:
    bound = flat_lcdm_example().bind({"H0": 70.0, "Om": 0.3})

    with pytest.raises(NumericalValidationError, match="undefined"):
        bound.distance_modulus(0.0)


def _quad_distance(z: float, *, H0: float, Om: float) -> float:
    integral, _ = quad(
        lambda redshift: SPEED_OF_LIGHT_KM_PER_S
        / (H0 * np.sqrt(Om * (1.0 + redshift) ** 3 + 1.0 - Om)),
        0.0,
        z,
        epsabs=1.0e-12,
        epsrel=1.0e-12,
    )
    return integral
