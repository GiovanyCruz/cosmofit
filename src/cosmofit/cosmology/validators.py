"""Validation errors and helpers for cosmology models."""

from __future__ import annotations


class CosmologyValidationError(ValueError):
    """Base class for user-facing cosmology validation failures."""


class ParameterDefinitionError(CosmologyValidationError):
    """Raised when parameter declarations are inconsistent."""


class ExpressionValidationError(CosmologyValidationError):
    """Raised when an H(z) expression is malformed or unsafe."""


class NumericalValidationError(CosmologyValidationError):
    """Raised when evaluated H(z) values are not physically admissible."""
