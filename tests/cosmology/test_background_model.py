"""Unit tests for milestone-1 H(z) background models."""

from __future__ import annotations

import numpy as np
import pytest

from cosmofit.cosmology import (
    BackgroundModel,
    ExpressionValidationError,
    FixedParameter,
    NumericalValidationError,
    ParameterDefinitionError,
    PriorBounds,
    ProposalWidth,
    ReferenceValue,
    SampledParameter,
    flat_lcdm_example,
)


def test_flat_lcdm_example_matches_reference_scalar_evaluation() -> None:
    model = flat_lcdm_example()

    result = model.hz(1.0, {"H0": 70.0, "Om": 0.3})

    expected = 70.0 * np.sqrt(0.3 * (1.0 + 1.0) ** 3 + 1.0 - 0.3)
    assert result == pytest.approx(expected)


def test_hz_evaluates_scalar_and_array_inputs() -> None:
    model = flat_lcdm_example()

    scalar_result = model.hz(0.5, {"H0": 70.0, "Om": 0.3})
    array_result = model.hz(np.array([0.0, 0.5, 1.0]), {"H0": 70.0, "Om": 0.3})

    assert isinstance(scalar_result, float)
    assert isinstance(array_result, np.ndarray)
    np.testing.assert_allclose(
        array_result,
        70.0 * np.sqrt(0.3 * (1.0 + np.array([0.0, 0.5, 1.0])) ** 3 + 1.0 - 0.3),
    )


def test_model_rejects_undeclared_parameters_in_expression() -> None:
    with pytest.raises(ExpressionValidationError, match="Unknown symbol 'Ode'"):
        BackgroundModel(
            expression="H0*sqrt(Om*(1+z)**3 + Ode)",
            parameters=(
                SampledParameter(
                    name="H0",
                    prior=PriorBounds(minimum=50.0, maximum=90.0),
                    reference=ReferenceValue(67.4),
                    proposal_width=ProposalWidth(1.0),
                    unit="km/s/Mpc",
                ),
                SampledParameter(
                    name="Om",
                    prior=PriorBounds(minimum=0.0, maximum=1.0),
                    reference=ReferenceValue(0.315),
                    proposal_width=ProposalWidth(0.02),
                    unit=None,
                ),
            ),
        )


@pytest.mark.parametrize(
    "expression",
    [
        "H0*sqrt((1+z)",
        "H0 +",
        "if z > 0 else H0",
    ],
)
def test_model_rejects_malformed_expressions(expression: str) -> None:
    with pytest.raises(ExpressionValidationError):
        BackgroundModel(expression=expression, parameters=_example_parameters())


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("__import__('os')", "Function '__import__'"),
        ("open('file.txt')", "Function 'open'"),
        ("os.system('echo x')", "Only direct calls"),
        ("(1).__class__", "Attribute access"),
        ("z[0]", "Subscript access"),
        ("(lambda x: x)(z)", "Only direct calls"),
        ("sqrt(z, z)", "requires exactly 1 argument"),
    ],
)
def test_model_rejects_malicious_expressions(expression: str, message: str) -> None:
    with pytest.raises(ExpressionValidationError, match=message):
        BackgroundModel(expression=expression, parameters=_example_parameters())


@pytest.mark.parametrize(
    "expression",
    [
        "0",
        "H0 - H0",
        "sqrt(-1)",
        "1 / (z - z)",
        "log(0)",
    ],
)
def test_model_rejects_invalid_numerical_outputs(expression: str) -> None:
    model = BackgroundModel(expression=expression, parameters=_example_parameters())

    with pytest.raises(NumericalValidationError):
        model.hz(np.array([0.5, 1.0]), {"H0": 70.0, "Om": 0.3})


def test_model_rejects_missing_or_unknown_parameter_values() -> None:
    model = BackgroundModel(expression="H0*(1+z)", parameters=_example_parameters())

    with pytest.raises(ParameterDefinitionError, match="Missing values"):
        model.hz(0.5, {"H0": 70.0})

    with pytest.raises(ParameterDefinitionError, match="Unknown parameter values"):
        model.hz(0.5, {"H0": 70.0, "Om": 0.3, "extra": 1.0})


def test_model_rejects_non_finite_parameter_values() -> None:
    model = BackgroundModel(expression="H0*(1+z)", parameters=_example_parameters())

    with pytest.raises(ExpressionValidationError, match="finite real scalar"):
        model.hz(0.5, {"H0": np.inf, "Om": 0.3})


def test_fixed_parameter_model_evaluates_successfully() -> None:
    model = BackgroundModel(
        expression="H0*(1+z)",
        parameters=(FixedParameter(name="H0", value=70.0, unit="km/s/Mpc"),),
    )

    result = model.hz(np.array([0.0, 1.0]), {})

    np.testing.assert_allclose(result, np.array([70.0, 140.0]))


def test_fixed_parameter_cannot_be_overridden_at_evaluation_time() -> None:
    model = BackgroundModel(
        expression="H0*(1+z)",
        parameters=(FixedParameter(name="H0", value=70.0, unit="km/s/Mpc"),),
    )

    with pytest.raises(ParameterDefinitionError, match="must not be overridden"):
        model.hz(1.0, {"H0": 10.0})


def test_parameter_name_cannot_conflict_with_approved_function() -> None:
    with pytest.raises(ParameterDefinitionError, match="conflicts with an approved"):
        SampledParameter(
            name="sqrt",
            prior=PriorBounds(minimum=0.0, maximum=1.0),
            reference=ReferenceValue(0.3),
            proposal_width=ProposalWidth(0.02),
            unit=None,
        )


def _example_parameters() -> tuple[SampledParameter, SampledParameter]:
    return (
        SampledParameter(
            name="H0",
            prior=PriorBounds(minimum=50.0, maximum=90.0),
            reference=ReferenceValue(67.4),
            proposal_width=ProposalWidth(1.0),
            unit="km/s/Mpc",
        ),
        SampledParameter(
            name="Om",
            prior=PriorBounds(minimum=0.0, maximum=1.0),
            reference=ReferenceValue(0.315),
            proposal_width=ProposalWidth(0.02),
            unit=None,
        ),
    )
