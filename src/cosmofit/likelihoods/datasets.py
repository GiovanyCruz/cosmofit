"""Dataset models and loaders for cosmic chronometer likelihoods."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
HUBBLE_RATE_UNIT = "km/s/Mpc"
REDSHIFT_UNIT = "dimensionless"


class LikelihoodValidationError(ValueError):
    """Base class for user-facing likelihood validation failures."""


class DatasetValidationError(LikelihoodValidationError):
    """Raised when a dataset definition is malformed or unphysical."""


@dataclass(frozen=True)
class BibliographicMetadata:
    """Optional provenance metadata for a dataset."""

    citation: str | None = None
    doi: str | None = None
    bibcode: str | None = None


@dataclass(frozen=True)
class CosmicChronometersDataset:
    """Validated cosmic chronometer data in km/s/Mpc."""

    z: FloatArray
    hubble_observed: FloatArray
    sigma: FloatArray | None = None
    covariance: FloatArray | None = None
    redshift_unit: str = REDSHIFT_UNIT
    hubble_unit: str = HUBBLE_RATE_UNIT
    name: str | None = None
    bibliography: BibliographicMetadata | None = None
    _covariance_cholesky: FloatArray | None = None

    def __post_init__(self) -> None:
        z = _as_1d_float_array(self.z, field_name="z")
        hubble_observed = _as_1d_float_array(
            self.hubble_observed,
            field_name="hubble_observed",
        )
        if z.size == 0:
            raise DatasetValidationError(
                "Cosmic chronometer datasets must contain at least one data point."
            )
        if z.shape != hubble_observed.shape:
            raise DatasetValidationError(
                "z and hubble_observed must have matching lengths."
            )
        if np.any(z < 0.0):
            raise DatasetValidationError("Redshifts must be non-negative.")
        if np.any(hubble_observed <= 0.0):
            raise DatasetValidationError(
                "Observed H(z) values must be strictly positive."
            )
        if self.redshift_unit != REDSHIFT_UNIT:
            raise DatasetValidationError(
                f"redshift_unit must be '{REDSHIFT_UNIT}'."
            )
        if self.hubble_unit != HUBBLE_RATE_UNIT:
            raise DatasetValidationError(
                f"hubble_unit must be '{HUBBLE_RATE_UNIT}'."
            )

        has_sigma = self.sigma is not None
        has_covariance = self.covariance is not None
        if has_sigma == has_covariance:
            raise DatasetValidationError(
                "Provide exactly one uncertainty representation: sigma or covariance."
            )

        sigma: FloatArray | None = None
        covariance: FloatArray | None = None
        covariance_cholesky: FloatArray | None = None
        if has_sigma:
            sigma = _as_1d_float_array(self.sigma, field_name="sigma")
            if sigma.shape != z.shape:
                raise DatasetValidationError(
                    "z, hubble_observed, and sigma must have matching lengths."
                )
            if np.any(sigma <= 0.0):
                raise DatasetValidationError(
                    "Uncertainties must be strictly positive."
                )
        else:
            covariance = _as_2d_float_array(
                self.covariance,
                field_name="covariance",
            )
            covariance_cholesky = _validate_covariance(
                covariance,
                expected_size=z.size,
            )

        object.__setattr__(self, "z", z)
        object.__setattr__(self, "hubble_observed", hubble_observed)
        object.__setattr__(self, "sigma", sigma)
        object.__setattr__(self, "covariance", covariance)
        object.__setattr__(self, "_covariance_cholesky", covariance_cholesky)

    def whiten_residuals(self, residuals: object) -> FloatArray:
        """Return C^(-1/2) DeltaH without forming an explicit inverse."""

        residual_vector = _as_1d_float_array(residuals, field_name="residuals")
        if residual_vector.shape != self.z.shape:
            raise DatasetValidationError(
                "residuals must match the dataset length."
            )

        if self.sigma is not None:
            return residual_vector / self.sigma

        if self._covariance_cholesky is None:
            raise DatasetValidationError("Missing covariance factorization.")

        return np.linalg.solve(self._covariance_cholesky, residual_vector)


def load_cosmic_chronometers_csv(
    path: str | Path,
    *,
    name: str | None = None,
    bibliography: BibliographicMetadata | None = None,
    redshift_unit: str = REDSHIFT_UNIT,
    hubble_unit: str = HUBBLE_RATE_UNIT,
) -> CosmicChronometersDataset:
    """Load an independent cosmic chronometer CSV with columns z,H,sigma."""

    csv_path = Path(path)
    header = csv_path.read_text(encoding="utf-8").splitlines()
    if not header:
        raise DatasetValidationError("CSV file is empty.")
    normalized_header = ",".join(part.strip() for part in header[0].split(","))
    if normalized_header != "z,H,sigma":
        raise DatasetValidationError(
            "Cosmic chronometer CSV header must be exactly 'z,H,sigma'."
        )

    try:
        data = np.loadtxt(csv_path, delimiter=",", skiprows=1, ndmin=2)
    except ValueError as exc:
        raise DatasetValidationError(
            f"Could not parse cosmic chronometer CSV '{csv_path}'."
        ) from exc

    if data.shape[1] != 3:
        raise DatasetValidationError(
            "Cosmic chronometer CSV must contain exactly three columns."
        )

    return CosmicChronometersDataset(
        z=data[:, 0],
        hubble_observed=data[:, 1],
        sigma=data[:, 2],
        name=name or csv_path.stem,
        bibliography=bibliography,
        redshift_unit=redshift_unit,
        hubble_unit=hubble_unit,
    )


def _as_1d_float_array(values: object, *, field_name: str) -> FloatArray:
    raw_array = np.asarray(values)
    if np.iscomplexobj(raw_array):
        raise DatasetValidationError(f"{field_name} must contain only real values.")

    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError(
            f"{field_name} must contain only finite real values."
        ) from exc

    if array.ndim != 1:
        raise DatasetValidationError(f"{field_name} must be a one-dimensional array.")
    if np.any(~np.isfinite(array)):
        raise DatasetValidationError(
            f"{field_name} must contain only finite real values."
        )
    return array.astype(float, copy=False)


def _as_2d_float_array(values: object, *, field_name: str) -> FloatArray:
    raw_array = np.asarray(values)
    if np.iscomplexobj(raw_array):
        raise DatasetValidationError(f"{field_name} must contain only real values.")

    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError(
            f"{field_name} must contain only finite real values."
        ) from exc

    if array.ndim != 2:
        raise DatasetValidationError(f"{field_name} must be a two-dimensional array.")
    if np.any(~np.isfinite(array)):
        raise DatasetValidationError(
            f"{field_name} must contain only finite real values."
        )
    return array.astype(float, copy=False)


def _validate_covariance(
    covariance: FloatArray,
    *,
    expected_size: int,
) -> FloatArray:
    rows, columns = covariance.shape
    if rows != columns:
        raise DatasetValidationError("covariance must be square.")
    if rows != expected_size:
        raise DatasetValidationError(
            "covariance dimensions must match the number of data points."
        )
    if not np.allclose(covariance, covariance.T, rtol=0.0, atol=1e-12):
        raise DatasetValidationError("covariance must be symmetric.")

    try:
        return np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise DatasetValidationError(
            "covariance must be non-singular and positive definite."
        ) from exc
