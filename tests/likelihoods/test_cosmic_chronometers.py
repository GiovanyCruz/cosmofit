"""Unit tests for the cosmic chronometer likelihood."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cosmofit.cosmology import flat_lcdm_example
from cosmofit.likelihoods import (
    BibliographicMetadata,
    CosmicChronometersDataset,
    CosmicChronometersLikelihood,
    DatasetValidationError,
    load_cosmic_chronometers_csv,
)


class StubHubbleModel:
    """Simple model stub for controlled likelihood tests."""

    def __init__(self, predictions: np.ndarray) -> None:
        self._predictions = predictions

    def hz(
        self,
        z: float | np.ndarray,
        parameter_values: dict[str, float],
    ) -> np.ndarray:
        return np.array(self._predictions, copy=True)


def test_diagonal_uncertainties_chi2_matches_reference() -> None:
    dataset = CosmicChronometersDataset(
        z=np.array([0.1, 0.2, 0.4]),
        hubble_observed=np.array([70.0, 76.0, 88.0]),
        sigma=np.array([2.0, 4.0, 5.0]),
        name="synthetic-diagonal",
    )
    likelihood = CosmicChronometersLikelihood(dataset)
    model = StubHubbleModel(np.array([68.0, 80.0, 83.0]))

    chi2 = likelihood.chi2(model, {})
    loglike = likelihood.loglike(model, {})

    expected = ((2.0 / 2.0) ** 2) + ((-4.0 / 4.0) ** 2) + ((5.0 / 5.0) ** 2)
    assert chi2 == pytest.approx(expected)
    assert loglike == pytest.approx(-0.5 * expected)


def test_full_covariance_chi2_matches_linear_solve_reference() -> None:
    covariance = np.array(
        [
            [4.0, 1.2, 0.3],
            [1.2, 9.0, 0.6],
            [0.3, 0.6, 16.0],
        ]
    )
    dataset = CosmicChronometersDataset(
        z=np.array([0.1, 0.2, 0.4]),
        hubble_observed=np.array([70.0, 76.0, 88.0]),
        covariance=covariance,
        name="synthetic-covariance",
    )
    likelihood = CosmicChronometersLikelihood(dataset)
    model = StubHubbleModel(np.array([68.0, 80.0, 83.0]))

    delta_h = np.array([2.0, -4.0, 5.0])
    expected = float(delta_h @ np.linalg.solve(covariance, delta_h))

    assert likelihood.chi2(model, {}) == pytest.approx(expected)


def test_zero_residual_gives_zero_chi2_and_loglike() -> None:
    dataset = CosmicChronometersDataset(
        z=np.array([0.0, 0.5]),
        hubble_observed=np.array([70.0, 90.0]),
        sigma=np.array([3.0, 3.5]),
    )
    likelihood = CosmicChronometersLikelihood(dataset)
    model = StubHubbleModel(np.array([70.0, 90.0]))

    assert likelihood.chi2(model, {}) == pytest.approx(0.0)
    assert likelihood.loglike(model, {}) == pytest.approx(0.0)


def test_dataset_rejects_malformed_array_dimensions() -> None:
    with pytest.raises(DatasetValidationError, match="one-dimensional"):
        CosmicChronometersDataset(
            z=np.array([[0.1, 0.2]]),
            hubble_observed=np.array([70.0, 80.0]),
            sigma=np.array([2.0, 2.0]),
        )


def test_dataset_rejects_mismatched_lengths() -> None:
    with pytest.raises(DatasetValidationError, match="matching lengths"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0]),
            sigma=np.array([2.0]),
        )


def test_dataset_rejects_non_positive_uncertainties() -> None:
    with pytest.raises(DatasetValidationError, match="strictly positive"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            sigma=np.array([2.0, 0.0]),
        )


def test_dataset_rejects_non_finite_values() -> None:
    with pytest.raises(DatasetValidationError, match="finite real values"):
        CosmicChronometersDataset(
            z=np.array([0.1, np.nan]),
            hubble_observed=np.array([70.0, 80.0]),
            sigma=np.array([2.0, 3.0]),
        )


def test_dataset_rejects_complex_observed_values() -> None:
    with pytest.raises(DatasetValidationError, match="real values"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0 + 1.0j, 80.0]),
            sigma=np.array([2.0, 2.0]),
        )


def test_dataset_rejects_invalid_covariance_shape() -> None:
    with pytest.raises(DatasetValidationError, match="must be square"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            covariance=np.array([[4.0, 0.1, 0.0], [0.1, 9.0, 0.0]]),
        )


def test_dataset_rejects_covariance_dimension_mismatch() -> None:
    with pytest.raises(DatasetValidationError, match="number of data points"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            covariance=np.eye(3),
        )


def test_dataset_rejects_non_symmetric_covariance() -> None:
    with pytest.raises(DatasetValidationError, match="symmetric"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            covariance=np.array([[4.0, 1.0], [0.5, 9.0]]),
        )


def test_dataset_rejects_singular_covariance() -> None:
    with pytest.raises(DatasetValidationError, match="positive definite"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            covariance=np.array([[4.0, 2.0], [2.0, 1.0]]),
        )


def test_dataset_rejects_complex_covariance_values() -> None:
    with pytest.raises(DatasetValidationError, match="real values"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            covariance=np.array(
                [[4.0 + 1.0j, 0.1], [0.1, 9.0]],
                dtype=complex,
            ),
        )


def test_dataset_rejects_empty_input() -> None:
    with pytest.raises(DatasetValidationError, match="at least one data point"):
        CosmicChronometersDataset(
            z=np.array([]),
            hubble_observed=np.array([]),
            sigma=np.array([]),
        )


def test_dataset_rejects_invalid_hubble_units() -> None:
    with pytest.raises(DatasetValidationError, match="hubble_unit"):
        CosmicChronometersDataset(
            z=np.array([0.1, 0.2]),
            hubble_observed=np.array([70.0, 80.0]),
            sigma=np.array([2.0, 2.0]),
            hubble_unit="s^-1",
        )


def test_csv_loading_reads_independent_dataset_format() -> None:
    fixture_path = Path("tests/fixtures/cosmic_chronometers_synth.csv")

    dataset = load_cosmic_chronometers_csv(
        fixture_path,
        name="fixture",
        bibliography=BibliographicMetadata(citation="Synthetic dataset"),
    )

    assert dataset.name == "fixture"
    assert dataset.hubble_unit == "km/s/Mpc"
    assert dataset.bibliography is not None
    np.testing.assert_allclose(dataset.z, np.array([0.10, 0.30, 0.60]))
    np.testing.assert_allclose(dataset.hubble_observed, np.array([72.0, 81.0, 98.0]))
    np.testing.assert_allclose(dataset.sigma, np.array([3.0, 4.5, 5.5]))


def test_likelihood_rejects_complex_theoretical_predictions() -> None:
    dataset = CosmicChronometersDataset(
        z=np.array([0.1, 0.2]),
        hubble_observed=np.array([70.0, 80.0]),
        sigma=np.array([2.0, 2.0]),
    )
    likelihood = CosmicChronometersLikelihood(dataset)
    model = StubHubbleModel(np.array([70.0 + 1.0j, 80.0]))

    with pytest.raises(DatasetValidationError, match="real values"):
        likelihood.chi2(model, {})


def test_likelihood_rejects_invalid_theoretical_predictions() -> None:
    dataset = CosmicChronometersDataset(
        z=np.array([0.1, 0.2]),
        hubble_observed=np.array([70.0, 80.0]),
        sigma=np.array([2.0, 2.0]),
    )
    likelihood = CosmicChronometersLikelihood(dataset)
    model = StubHubbleModel(np.array([np.nan, 80.0]))

    with pytest.raises(DatasetValidationError, match="finite values"):
        likelihood.chi2(model, {})


def test_likelihood_is_compatible_with_existing_flat_lcdm_model() -> None:
    model = flat_lcdm_example()
    z = np.array([0.0, 0.5, 1.0])
    parameters = {"H0": 70.0, "Om": 0.3}
    hubble_observed = np.asarray(model.hz(z, parameters), dtype=float)
    dataset = CosmicChronometersDataset(
        z=z,
        hubble_observed=hubble_observed,
        sigma=np.array([2.0, 2.5, 3.0]),
        name="lcdm-self-consistent",
    )
    likelihood = CosmicChronometersLikelihood(dataset)

    assert likelihood.chi2(model, parameters) == pytest.approx(0.0)
