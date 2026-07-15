"""Reusable generic Cobaya Theory for flat background H(z) models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from cobaya.log import LoggedError
from cobaya.theory import Theory

from cosmofit.application import (
    ModelConfig,
    ParameterConfig,
    UniformPriorConfig,
    build_background_model,
)
from cosmofit.cosmology.validators import CosmologyValidationError

HUBBLE_UNITS = frozenset({"km/s/Mpc", "1/Mpc"})
SUPPORTED_PRODUCTS = frozenset(
    {"Hubble", "angular_diameter_distance", "comoving_radial_distance"}
)


class GenericBackgroundTheory(Theory):
    """Expose a validated user H(z) model through Cobaya's Theory API."""

    model_expression: str
    model_expression_unit: str
    model_redshift_symbol: str
    model_allowed_functions: list[str]
    parameter_definitions: list[dict[str, Any]]

    def initialize_with_params(self) -> None:
        self._background_model = _build_background_model_from_options(
            model_expression=self.model_expression,
            model_expression_unit=self.model_expression_unit,
            model_redshift_symbol=self.model_redshift_symbol,
            model_allowed_functions=tuple(self.model_allowed_functions),
            parameter_definitions=self.parameter_definitions,
        )
        self._requested_redshifts: dict[str, np.ndarray] = {}

    def get_can_support_params(self) -> tuple[str, ...]:
        return tuple(
            parameter.symbol
            for parameter in _deserialize_parameters(self.parameter_definitions)
        )

    def must_provide(self, **requirements):
        super().must_provide(**requirements)
        if not hasattr(self, "_requested_redshifts"):
            self._requested_redshifts = {}
        for product, options in requirements.items():
            if product not in SUPPORTED_PRODUCTS:
                raise LoggedError(
                    self.log,
                    "Unknown required product '%s' for GenericBackgroundTheory.",
                    product,
                )
            if not isinstance(options, Mapping) or "z" not in options:
                raise LoggedError(
                    self.log,
                    "Requirement '%s' must provide a mapping with key 'z'.",
                    product,
                )
            self._requested_redshifts[product] = _combine_redshifts(
                self._requested_redshifts.get(product),
                options["z"],
            )
        return None

    def calculate(self, state, want_derived=True, **params_values_dict):
        try:
            background_model = self._ensure_background_model()
            bound_model = background_model.bind(params_values_dict)
            current_redshifts: dict[str, np.ndarray] = {}
            for product, redshifts in self._requested_redshifts.items():
                current_redshifts[product] = np.array(redshifts, copy=True)
                if product == "Hubble":
                    state["Hubble"] = np.asarray(bound_model.hz(redshifts), dtype=float)
                elif product == "angular_diameter_distance":
                    state["angular_diameter_distance"] = np.asarray(
                        bound_model.angular_diameter_distance(redshifts),
                        dtype=float,
                    )
                elif product == "comoving_radial_distance":
                    state["comoving_radial_distance"] = np.asarray(
                        bound_model.comoving_radial_distance(redshifts),
                        dtype=float,
                    )
            state["current_redshifts"] = current_redshifts
            return True
        except CosmologyValidationError as exc:
            self.log.debug(
                "Invalid cosmology point rejected by GenericBackgroundTheory: %s",
                exc,
            )
            return False

    def get_Hubble(
        self,
        z: float | np.ndarray,
        units: str = "km/s/Mpc",
    ) -> float | np.ndarray:
        if units not in HUBBLE_UNITS:
            raise LoggedError(
                self.log,
                "Units not known for H: '%s'. Try instead one of %r.",
                units,
                sorted(HUBBLE_UNITS),
            )
        hubble = self._subset_requested_result("Hubble", z)
        if units == "1/Mpc":
            return hubble / 299792.458
        return hubble

    def get_angular_diameter_distance(
        self,
        z: float | np.ndarray,
    ) -> float | np.ndarray:
        return self._subset_requested_result("angular_diameter_distance", z)

    def get_comoving_radial_distance(self, z: float | np.ndarray) -> float | np.ndarray:
        return self._subset_requested_result("comoving_radial_distance", z)

    def _ensure_background_model(self):
        if hasattr(self, "_background_model"):
            return self._background_model
        self._background_model = _build_background_model_from_options(
            model_expression=self.model_expression,
            model_expression_unit=self.model_expression_unit,
            model_redshift_symbol=self.model_redshift_symbol,
            model_allowed_functions=tuple(self.model_allowed_functions),
            parameter_definitions=self.parameter_definitions,
        )
        return self._background_model

    def _subset_requested_result(
        self,
        product: str,
        z: float | np.ndarray,
    ) -> float | np.ndarray:
        requested = np.asarray(z, dtype=float)
        scalar = requested.ndim == 0
        requested_values = np.atleast_1d(requested).astype(float)
        available_z = self.current_state["current_redshifts"][product]
        values = self.current_state[product]
        indices = []
        for redshift in requested_values:
            matches = np.where(available_z == redshift)[0]
            if matches.size == 0:
                raise LoggedError(
                    self.log,
                    "%s not computed for requested z=%r. Available z are %r.",
                    product,
                    redshift,
                    available_z,
                )
            indices.append(int(matches[0]))
        result = np.asarray(values, dtype=float)[indices]
        if scalar:
            return float(result[0])
        return result


def _build_run_like_model_config(
    *,
    model_expression: str,
    model_expression_unit: str,
    model_redshift_symbol: str,
    model_allowed_functions: tuple[str, ...],
    parameter_definitions: list[dict[str, Any]],
):
    class _RunLike:
        model = ModelConfig(
            kind="hz_expression_flat",
            expression=model_expression,
            expression_unit=model_expression_unit,
            redshift_symbol=model_redshift_symbol,
            allowed_functions=model_allowed_functions,
        )
        parameters = tuple(_deserialize_parameters(parameter_definitions))

    return _RunLike()


def _build_background_model_from_options(
    *,
    model_expression: str,
    model_expression_unit: str,
    model_redshift_symbol: str,
    model_allowed_functions: tuple[str, ...],
    parameter_definitions: list[dict[str, Any]],
):
    return build_background_model(
        _build_run_like_model_config(
            model_expression=model_expression,
            model_expression_unit=model_expression_unit,
            model_redshift_symbol=model_redshift_symbol,
            model_allowed_functions=model_allowed_functions,
            parameter_definitions=parameter_definitions,
        )
    )


def _deserialize_parameters(
    parameter_definitions: list[dict[str, Any]],
) -> tuple[ParameterConfig, ...]:
    return tuple(
        ParameterConfig(
            name=item["name"],
            symbol=item["symbol"],
            role=item["role"],
            unit=item.get("unit"),
            value=item.get("value"),
            prior=(
                UniformPriorConfig(
                    minimum=item["prior"]["minimum"],
                    maximum=item["prior"]["maximum"],
                )
                if item.get("prior") is not None
                else None
            ),
            reference=item.get("reference"),
            proposal=item.get("proposal"),
        )
        for item in parameter_definitions
    )


def _combine_redshifts(
    existing: np.ndarray | None,
    requested: Any,
) -> np.ndarray:
    requested_array = np.asarray(requested, dtype=float)
    if requested_array.ndim == 0:
        requested_array = np.atleast_1d(requested_array)
    if requested_array.ndim != 1:
        raise ValueError("Requested redshifts must be scalar or one-dimensional.")
    if np.any(~np.isfinite(requested_array)):
        raise ValueError("Requested redshifts must be finite.")
    if np.any(requested_array < 0.0):
        raise ValueError("Requested redshifts must be non-negative.")
    if existing is None:
        return np.unique(requested_array.astype(float))
    return np.unique(np.concatenate([existing, requested_array.astype(float)]))
