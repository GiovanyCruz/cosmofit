"""Restricted AST parser for user-provided H(z) expressions."""

from __future__ import annotations

import ast
from collections.abc import Iterable

from cosmofit.cosmology.expression_ast import (
    BinaryOperationNode,
    ExpressionNode,
    FunctionCallNode,
    NumberNode,
    SymbolNode,
    UnaryOperationNode,
)
from cosmofit.cosmology.validators import ExpressionValidationError

ALLOWED_FUNCTIONS: tuple[str, ...] = ("sqrt", "exp", "log", "sin", "cos")
_FUNCTION_ARITY: dict[str, int] = {name: 1 for name in ALLOWED_FUNCTIONS}
_ALLOWED_BINARY_OPERATORS: dict[type[ast.operator], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
}
_ALLOWED_UNARY_OPERATORS: dict[type[ast.unaryop], str] = {
    ast.UAdd: "+",
    ast.USub: "-",
}


class HzExpressionParser:
    """Parse an H(z) expression into a validated internal expression tree."""

    def __init__(
        self,
        *,
        redshift_symbol: str = "z",
        allowed_functions: Iterable[str] = ALLOWED_FUNCTIONS,
    ) -> None:
        self._redshift_symbol = redshift_symbol
        self._allowed_functions = tuple(allowed_functions)

    def parse(self, expression: str, parameter_names: Iterable[str]) -> ExpressionNode:
        """Validate and convert a user expression into an expression tree."""
        try:
            parsed = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ExpressionValidationError(
                f"Invalid H(z) expression syntax: {exc.msg}."
            ) from exc

        allowed_symbols = set(parameter_names)
        allowed_symbols.add(self._redshift_symbol)
        return self._convert_node(parsed.body, allowed_symbols)

    def _convert_node(
        self,
        node: ast.AST,
        allowed_symbols: set[str],
    ) -> ExpressionNode:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ExpressionValidationError(
                    "Only real numeric constants are allowed."
                )
            return NumberNode(float(node.value))

        if isinstance(node, ast.Name):
            if node.id not in allowed_symbols:
                raise ExpressionValidationError(f"Unknown symbol '{node.id}'.")
            return SymbolNode(node.id)

        if isinstance(node, ast.BinOp):
            operator = _ALLOWED_BINARY_OPERATORS.get(type(node.op))
            if operator is None:
                raise ExpressionValidationError(
                    "Only arithmetic binary operations are allowed."
                )
            return BinaryOperationNode(
                operator=operator,
                left=self._convert_node(node.left, allowed_symbols),
                right=self._convert_node(node.right, allowed_symbols),
            )

        if isinstance(node, ast.UnaryOp):
            operator = _ALLOWED_UNARY_OPERATORS.get(type(node.op))
            if operator is None:
                raise ExpressionValidationError(
                    "Only unary plus and minus are allowed."
                )
            return UnaryOperationNode(
                operator=operator,
                operand=self._convert_node(node.operand, allowed_symbols),
            )

        if isinstance(node, ast.Call):
            if node.keywords:
                raise ExpressionValidationError("Keyword arguments are not allowed.")
            if not isinstance(node.func, ast.Name):
                raise ExpressionValidationError(
                    "Only direct calls to approved functions are allowed."
                )
            if node.func.id not in self._allowed_functions:
                raise ExpressionValidationError(
                    f"Function '{node.func.id}' is not in the approved function list."
                )
            expected_arity = _FUNCTION_ARITY[node.func.id]
            if len(node.args) != expected_arity:
                raise ExpressionValidationError(
                    f"Function '{node.func.id}' requires exactly "
                    f"{expected_arity} argument(s)."
                )
            return FunctionCallNode(
                function_name=node.func.id,
                arguments=tuple(
                    self._convert_node(argument, allowed_symbols)
                    for argument in node.args
                ),
            )

        if isinstance(node, ast.Attribute):
            raise ExpressionValidationError("Attribute access is not allowed.")
        if isinstance(node, ast.Subscript):
            raise ExpressionValidationError("Subscript access is not allowed.")
        if isinstance(node, ast.Lambda):
            raise ExpressionValidationError("Lambda expressions are not allowed.")
        if isinstance(node, ast.IfExp):
            raise ExpressionValidationError("Conditional expressions are not allowed.")
        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            raise ExpressionValidationError("Collection literals are not allowed.")
        if isinstance(
            node,
            (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
        ):
            raise ExpressionValidationError("Comprehensions are not allowed.")

        raise ExpressionValidationError(
            f"Unsupported expression element: {type(node).__name__}."
        )
