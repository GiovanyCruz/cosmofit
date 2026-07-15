"""Immutable data models for milestone-1 cosmological background models."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import quad

from cosmofit.cosmology.expression_ast import ExpressionNode
from cosmofit.cosmology.expression_evaluator import evaluate_expression
from cosmofit.cosmology.expression_parser import ALLOWED_FUNCTIONS, HzExpressionParser
from cosmofit.cosmology.validators import (
    NumericalValidationError,
    ParameterDefinitionError,
)

FloatArray = NDArray[np.float64]
SPEED_OF_LIGHT_KM_PER_S = 299792.458


@dataclass(frozen=True)
class PriorBounds:
    """Uniform prior bounds for a sampled parameter."""

    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if self.minimum >= self.maximum:
            raise ParameterDefinitionError(
                "Prior minimum must be smaller than maximum."
            )


@dataclass(frozen=True)
class ReferenceValue:
    """Reference value used for sampler initialization."""

    value: float


@dataclass(frozen=True)
class ProposalWidth:
    """Proposal width used for sampled parameters."""

    value: float

    def __post_init__(self) -> None:
        if self.value <= 0.0:
            raise ParameterDefinitionError("Proposal width must be strictly positive.")


@dataclass(frozen=True)
class CosmologicalParameter:
    """Base metadata shared by fixed and sampled cosmological parameters."""

    name: str
    unit: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not self.name.isidentifier():
            raise ParameterDefinitionError(
                f"Parameter name '{self.name}' must be a valid identifier."
            )
        if self.name == "z":
            raise ParameterDefinitionError(
                "Parameter name 'z' is reserved for redshift."
            )
        if self.name in ALLOWED_FUNCTIONS:
            raise ParameterDefinitionError(
                f"Parameter name '{self.name}' conflicts with an approved "
                "function name."
            )


@dataclass(frozen=True)
class FixedParameter(CosmologicalParameter):
    """A cosmological parameter held fixed during inference."""

    value: float


@dataclass(frozen=True)
class SampledParameter(CosmologicalParameter):
    """A cosmological parameter varied during inference."""

    prior: PriorBounds
    reference: ReferenceValue
    proposal_width: ProposalWidth

    def __post_init__(self) -> None:
        super().__post_init__()
        if not (self.prior.minimum <= self.reference.value <= self.prior.maximum):
            raise ParameterDefinitionError(
                f"Reference value for '{self.name}' must lie within the prior bounds."
            )
        if self.proposal_width.value <= 0.0:
            raise ParameterDefinitionError(
                f"Proposal width for '{self.name}' must be strictly positive."
            )


Parameter = FixedParameter | SampledParameter


@dataclass(frozen=True)
class BackgroundModel:
    """A validated cosmological background model defined by H(z)."""

    expression: str
    parameters: tuple[Parameter, ...]
    redshift_symbol: str = "z"
    allowed_functions: tuple[str, ...] = ALLOWED_FUNCTIONS
    expression_unit: ClassVar[str] = "km/s/Mpc"
    _parsed_expression: ExpressionNode = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        if len(parameter_names) != len(set(parameter_names)):
            raise ParameterDefinitionError(
                "Parameter names must be unique within a model."
            )
        if self.redshift_symbol != "z":
            raise ParameterDefinitionError(
                "Milestone 1 reserves 'z' as the only redshift symbol."
            )

        parser = HzExpressionParser(
            redshift_symbol=self.redshift_symbol,
            allowed_functions=self.allowed_functions,
        )
        parsed_expression = parser.parse(self.expression, parameter_names)
        object.__setattr__(self, "_parsed_expression", parsed_expression)

    def hz(
        self,
        z: float | NDArray[float],
        parameter_values: Mapping[str, float],
    ) -> float | NDArray[float]:
        """Evaluate H(z) in km/s/Mpc for scalar or NumPy array redshift values."""
        return self._evaluate_hz(z, self.resolve_parameter_values(parameter_values))

    def bind(self, parameter_values: Mapping[str, float]) -> BoundBackgroundModel:
        """Bind concrete parameter values once and expose flat-distance observables."""

        return BoundBackgroundModel(
            model=self,
            parameter_values=self.resolve_parameter_values(parameter_values),
        )

    def resolve_parameter_values(
        self,
        parameter_values: Mapping[str, float],
    ) -> dict[str, float]:
        """Resolve fixed and sampled parameter values for one evaluation point."""

        resolved_values = {
            parameter.name: parameter.value
            for parameter in self.parameters
            if isinstance(parameter, FixedParameter)
        }
        fixed_parameter_names = set(resolved_values)
        for name, value in parameter_values.items():
            scalar_value = float(value)
            if not isfinite(scalar_value):
                raise ParameterDefinitionError(
                    f"Parameter '{name}' must be a finite real scalar."
                )
            if name in fixed_parameter_names:
                fixed_value = resolved_values[name]
                if scalar_value != fixed_value:
                    raise ParameterDefinitionError(
                        "Fixed parameters must not be overridden at evaluation time: "
                        f"{name}."
                    )
            resolved_values[name] = scalar_value

        sampled_parameter_names = {
            parameter.name
            for parameter in self.parameters
            if isinstance(parameter, SampledParameter)
        }
        expected_parameters = {parameter.name for parameter in self.parameters}
        provided_parameters = set(resolved_values)

        missing_parameters = sampled_parameter_names - provided_parameters
        if missing_parameters:
            missing_str = ", ".join(sorted(missing_parameters))
            raise ParameterDefinitionError(
                f"Missing values for model parameters: {missing_str}."
            )

        unknown_parameters = set(parameter_values) - expected_parameters
        if unknown_parameters:
            unknown_str = ", ".join(sorted(unknown_parameters))
            raise ParameterDefinitionError(
                f"Unknown parameter values supplied: {unknown_str}."
            )
        return resolved_values

    def _evaluate_hz(
        self,
        z: float | FloatArray,
        parameter_values: Mapping[str, float],
    ) -> float | FloatArray:
        return evaluate_expression(
            self._parsed_expression,
            z=z,
            parameter_values=parameter_values,
        )


@dataclass
class BoundBackgroundModel:
    """Flat background observables for one fixed parameter point."""

    model: BackgroundModel
    parameter_values: Mapping[str, float]
    _distance_cache_z: list[float] = field(default_factory=lambda: [0.0], init=False)
    _distance_cache_dc_mpc: dict[float, float] = field(
        default_factory=lambda: {0.0: 0.0},
        init=False,
        repr=False,
    )

    def hz(self, z: float | FloatArray) -> float | FloatArray:
        """Return H(z) in km/s/Mpc for scalar or one-dimensional redshift input."""

        values, scalar = _normalize_redshift_input(z)
        hz = np.asarray(
            self.model._evaluate_hz(values, self.parameter_values),
            dtype=float,
        )
        return _restore_input_shape(hz, scalar)

    def comoving_radial_distance(self, z: float | FloatArray) -> float | FloatArray:
        """Return the line-of-sight comoving distance in Mpc."""

        return self._evaluate_distance_observable(z, kind="comoving_radial_distance")

    def comoving_transverse_distance(self, z: float | FloatArray) -> float | FloatArray:
        """Return the transverse comoving distance in Mpc for flat geometry."""

        return self.comoving_radial_distance(z)

    def angular_diameter_distance(self, z: float | FloatArray) -> float | FloatArray:
        """Return the angular-diameter distance in Mpc."""

        values, scalar = _normalize_redshift_input(z)
        distance = self._comoving_radial_distance_array(values) / (1.0 + values)
        return _restore_input_shape(distance, scalar)

    def luminosity_distance(self, z: float | FloatArray) -> float | FloatArray:
        """Return the luminosity distance in Mpc."""

        values, scalar = _normalize_redshift_input(z)
        distance = self._comoving_radial_distance_array(values) * (1.0 + values)
        return _restore_input_shape(distance, scalar)

    def distance_modulus(self, z: float | FloatArray) -> float | FloatArray:
        """Return the geometric distance modulus in magnitudes."""

        values, scalar = _normalize_redshift_input(z)
        luminosity_distance = self._comoving_radial_distance_array(values) * (
            1.0 + values
        )
        if np.any(luminosity_distance <= 0.0):
            raise NumericalValidationError(
                "Distance modulus is undefined for zero luminosity distance."
            )
        distance_modulus = 5.0 * np.log10(luminosity_distance) + 25.0
        return _restore_input_shape(distance_modulus, scalar)

    def _evaluate_distance_observable(
        self,
        z: float | FloatArray,
        *,
        kind: str,
    ) -> float | FloatArray:
        values, scalar = _normalize_redshift_input(z)
        if kind != "comoving_radial_distance":
            raise AssertionError(f"Unsupported distance kind '{kind}'.")
        return _restore_input_shape(
            self._comoving_radial_distance_array(values),
            scalar,
        )

    def _comoving_radial_distance_array(self, z: FloatArray) -> FloatArray:
        unique_z, inverse = np.unique(z, return_inverse=True)
        distances = np.array(
            [
                self._get_or_compute_comoving_distance(float(redshift))
                for redshift in unique_z
            ],
            dtype=float,
        )
        return distances[inverse]

    def _get_or_compute_comoving_distance(self, z: float) -> float:
        if z in self._distance_cache_dc_mpc:
            return self._distance_cache_dc_mpc[z]

        insertion_index = bisect_left(self._distance_cache_z, z)
        lower_index = insertion_index - 1
        if lower_index < 0:
            raise NumericalValidationError("Comoving-distance cache lost z=0 anchor.")
        lower_z = self._distance_cache_z[lower_index]
        lower_distance = self._distance_cache_dc_mpc[lower_z]
        integral, _ = quad(
            self._inverse_hubble_integrand,
            lower_z,
            z,
            epsabs=1.0e-10,
            epsrel=1.0e-10,
            limit=200,
        )
        distance = lower_distance + integral
        self._distance_cache_z.insert(insertion_index, z)
        self._distance_cache_dc_mpc[z] = distance
        return distance

    def _inverse_hubble_integrand(self, redshift: float) -> float:
        hz_value = float(self.model._evaluate_hz(redshift, self.parameter_values))
        if not np.isfinite(hz_value) or hz_value <= 0.0:
            raise NumericalValidationError(
                f"H(z) must remain finite and strictly positive over the integration "
                f"range; got {hz_value!r} at z={redshift}."
            )
        return SPEED_OF_LIGHT_KM_PER_S / hz_value


def _normalize_redshift_input(z: float | FloatArray) -> tuple[FloatArray, bool]:
    array = np.asarray(z, dtype=float)
    scalar = array.ndim == 0
    if scalar:
        values = np.atleast_1d(array.astype(float))
    elif array.ndim == 1:
        values = array.astype(float, copy=False)
    else:
        raise ParameterDefinitionError(
            "Redshift input must be a scalar or one-dimensional array."
        )
    if np.any(~np.isfinite(values)):
        raise ParameterDefinitionError(
            "Redshift input must contain only finite values."
        )
    if np.any(values < 0.0):
        raise ParameterDefinitionError("Redshift input must be non-negative.")
    return values, scalar


def _restore_input_shape(values: FloatArray, scalar: bool) -> float | FloatArray:
    if scalar:
        return float(values[0])
    return values
