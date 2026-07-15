"""Validated expression tree nodes for safe H(z) evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumberNode:
    """A numeric literal."""

    value: float


@dataclass(frozen=True)
class SymbolNode:
    """A declared symbol such as ``z`` or a model parameter."""

    name: str


@dataclass(frozen=True)
class UnaryOperationNode:
    """A unary arithmetic operation."""

    operator: str
    operand: ExpressionNode


@dataclass(frozen=True)
class BinaryOperationNode:
    """A binary arithmetic operation."""

    operator: str
    left: ExpressionNode
    right: ExpressionNode


@dataclass(frozen=True)
class FunctionCallNode:
    """A call to an approved mathematical function."""

    function_name: str
    arguments: tuple[ExpressionNode, ...]


type ExpressionNode = (
    NumberNode
    | SymbolNode
    | UnaryOperationNode
    | BinaryOperationNode
    | FunctionCallNode
)
