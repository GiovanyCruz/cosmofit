"""Cobaya likelihood adapters that consume the shared background Theory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from cobaya.likelihood import Likelihood

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    build_cosmic_chronometers_likelihood,
)
from cosmofit.likelihoods.datasets import DatasetValidationError


class CosmicChronometersCobayaLikelihood(Likelihood):
    """Thin Cobaya adapter for the pure cosmic chronometer likelihood."""

    dataset_path: str
    dataset_name: str

    def initialize_with_params(self) -> None:
        self._ensure_likelihood()

    def get_requirements(self) -> dict[str, dict[str, np.ndarray]]:
        likelihood = self._ensure_likelihood()
        return {"Hubble": {"z": likelihood.dataset.z}}

    def logp(self, **params_values: float) -> float:
        del params_values
        likelihood = self._ensure_likelihood()
        try:
            predictions = np.asarray(
                self.provider.get_Hubble(
                    likelihood.dataset.z,
                    units="km/s/Mpc",
                ),
                dtype=float,
            )
            residuals = likelihood.dataset.hubble_observed - predictions
            whitened = likelihood.dataset.whiten_residuals(residuals)
            return float(-0.5 * (whitened @ whitened))
        except DatasetValidationError:
            return -np.inf

    def _ensure_likelihood(self):
        if hasattr(self, "_likelihood"):
            return self._likelihood
        dataset_config = CosmicChronometerDatasetConfig(
            kind="cosmic_chronometers",
            data_path=Path(self.dataset_path),
            name=self.dataset_name,
        )
        self._likelihood = build_cosmic_chronometers_likelihood(dataset_config)
        return self._likelihood
