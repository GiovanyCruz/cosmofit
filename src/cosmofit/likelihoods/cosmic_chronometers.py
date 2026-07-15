"""Cosmic chronometer H(z) likelihood implementation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from cosmofit.likelihoods.base import HubbleRateProvider
from cosmofit.likelihoods.datasets import (
    CosmicChronometersDataset,
    DatasetValidationError,
)


@dataclass(frozen=True)
class CosmicChronometersLikelihood:
    """Gaussian H(z) likelihood for cosmic chronometer measurements."""

    dataset: CosmicChronometersDataset

    def residuals(
        self,
        model: HubbleRateProvider,
        parameter_values: Mapping[str, float],
    ) -> np.ndarray:
        """Return observed minus theoretical H(z) in km/s/Mpc."""

        raw_prediction = model.hz(self.dataset.z, dict(parameter_values))
        if np.iscomplexobj(raw_prediction):
            raise DatasetValidationError(
                "Theoretical H(z) predictions must contain only real values."
            )

        predicted = np.asarray(raw_prediction, dtype=float)
        if predicted.ndim != 1:
            raise DatasetValidationError(
                "Theoretical H(z) predictions must be one-dimensional."
            )
        if predicted.shape != self.dataset.hubble_observed.shape:
            raise DatasetValidationError(
                "Theoretical H(z) predictions must match the dataset length."
            )
        if np.any(~np.isfinite(predicted)):
            raise DatasetValidationError(
                "Theoretical H(z) predictions must contain only finite values."
            )
        if np.any(predicted <= 0.0):
            raise DatasetValidationError(
                "Theoretical H(z) predictions must be strictly positive."
            )
        return self.dataset.hubble_observed - predicted

    def chi2(
        self,
        model: HubbleRateProvider,
        parameter_values: Mapping[str, float],
    ) -> float:
        """Return chi-square for the current model prediction."""

        delta_h = self.residuals(model, parameter_values)
        whitened = self.dataset.whiten_residuals(delta_h)
        return float(whitened @ whitened)

    def loglike(
        self,
        model: HubbleRateProvider,
        parameter_values: Mapping[str, float],
    ) -> float:
        """Return the Gaussian log-likelihood without normalization constants."""

        return -0.5 * self.chi2(model, parameter_values)
