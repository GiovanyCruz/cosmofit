"""Immutable data models for milestone-1 cosmological background models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from numpy.typing import NDArray

from cosmofit.cosmology.expression_ast import ExpressionNode
from cosmofit.cosmology.expression_evaluator import evaluate_expression
from cosmofit.cosmology.expression_parser import ALLOWED_FUNCTIONS, HzExpressionParser
from cosmofit.cosmology.validators import ParameterDefinitionError


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
        parameter_values: dict[str, float],
    ) -> float | NDArray[float]:
        """Evaluate H(z) in km/s/Mpc for scalar or NumPy array redshift values."""
        resolved_values = {
            parameter.name: parameter.value
            for parameter in self.parameters
            if isinstance(parameter, FixedParameter)
        }
        fixed_parameter_names = set(resolved_values)
        overridden_fixed_parameters = fixed_parameter_names & set(parameter_values)
        if overridden_fixed_parameters:
            overridden_str = ", ".join(sorted(overridden_fixed_parameters))
            raise ParameterDefinitionError(
                f"Fixed parameters must not be overridden at evaluation time: "
                f"{overridden_str}."
            )
        resolved_values.update(parameter_values)

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

        return evaluate_expression(
            self._parsed_expression,
            z=z,
            parameter_values=resolved_values,
        )
