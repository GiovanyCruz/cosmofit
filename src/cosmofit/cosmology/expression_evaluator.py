"""Closed NumPy-backed evaluation of validated H(z) expression trees."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from cosmofit.cosmology.expression_ast import (
    BinaryOperationNode,
    ExpressionNode,
    FunctionCallNode,
    NumberNode,
    SymbolNode,
    UnaryOperationNode,
)
from cosmofit.cosmology.validators import (
    ExpressionValidationError,
    NumericalValidationError,
)

FloatArray = NDArray[np.float64]

_FUNCTION_MAP = {
    "sqrt": np.sqrt,
    "exp": np.exp,
    "log": np.log,
    "sin": np.sin,
    "cos": np.cos,
}


def evaluate_expression(
    expression: ExpressionNode,
    *,
    z: float | FloatArray,
    parameter_values: Mapping[str, float],
) -> float | FloatArray:
    """Evaluate a validated expression for scalar or array redshift input."""
    z_array = np.array(z, dtype=float, copy=True)
    context: dict[str, float | FloatArray] = {"z": z_array}

    for name, value in parameter_values.items():
        scalar_value = float(value)
        if not np.isfinite(scalar_value):
            raise ExpressionValidationError(
                f"Parameter '{name}' must be a finite real scalar."
            )
        context[name] = scalar_value

    with np.errstate(all="ignore"):
        result = _evaluate_node(expression, context)
    validated = _validate_hz_output(np.asarray(result))

    if validated.ndim == 0:
        return float(validated)
    return validated


def _evaluate_node(
    node: ExpressionNode,
    context: Mapping[str, float | FloatArray],
) -> float | FloatArray:
    if isinstance(node, NumberNode):
        return node.value

    if isinstance(node, SymbolNode):
        try:
            return context[node.name]
        except KeyError as exc:
            raise ExpressionValidationError(
                f"Missing value for symbol '{node.name}'."
            ) from exc

    if isinstance(node, UnaryOperationNode):
        operand = _evaluate_node(node.operand, context)
        if node.operator == "+":
            return operand
        if node.operator == "-":
            return -operand
        raise AssertionError(f"Unexpected unary operator {node.operator!r}.")

    if isinstance(node, BinaryOperationNode):
        left = _evaluate_node(node.left, context)
        right = _evaluate_node(node.right, context)
        if node.operator == "+":
            return left + right
        if node.operator == "-":
            return left - right
        if node.operator == "*":
            return left * right
        if node.operator == "/":
            return left / right
        if node.operator == "**":
            return left**right
        raise AssertionError(f"Unexpected binary operator {node.operator!r}.")

    if isinstance(node, FunctionCallNode):
        function = _FUNCTION_MAP[node.function_name]
        arguments = tuple(
            _evaluate_node(argument, context) for argument in node.arguments
        )
        return function(*arguments)

    raise AssertionError(f"Unsupported node type {type(node).__name__}.")


def _validate_hz_output(result: FloatArray) -> FloatArray:
    if np.iscomplexobj(result):
        raise NumericalValidationError("H(z) must be real-valued.")
    if np.any(np.isnan(result)):
        raise NumericalValidationError("H(z) must not contain NaN values.")
    if np.any(np.isinf(result)):
        raise NumericalValidationError("H(z) must not contain infinite values.")
    if np.any(result <= 0.0):
        raise NumericalValidationError("H(z) must be strictly positive.")
    return result.astype(float, copy=False)
