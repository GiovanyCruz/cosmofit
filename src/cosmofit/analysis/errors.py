"""Typed analysis errors for run-location, loading, and export failures."""

from __future__ import annotations

from pathlib import Path


class AnalysisError(ValueError):
    """Base error for analysis failures with a stable machine-readable code."""

    code = "analysis_error"

    def __init__(self, message: str, *, run_directory: Path | None = None) -> None:
        super().__init__(message)
        self.run_directory = run_directory


class InvalidAnalysisSettingError(AnalysisError):
    """Raised when analysis settings are invalid."""

    code = "invalid_analysis_setting"


class InvalidMathTextError(InvalidAnalysisSettingError):
    """Raised when a Matplotlib MathText label cannot be rendered safely."""

    code = "invalid_mathtext"

    def __init__(self, *, field_name: str, details: str) -> None:
        super().__init__(
            f"Invalid Matplotlib MathText in {field_name}: {details}"
        )
        self.field_name = field_name
        self.details = details


class MalformedRunDirectoryError(AnalysisError):
    """Raised when a run directory is incomplete or malformed."""

    code = "malformed_run_directory"


class RunNotSuccessfulError(AnalysisError):
    """Raised when a run directory does not represent a completed successful run."""

    code = "run_not_successful"


class MultipleChainRootsError(AnalysisError):
    """Raised when more than one valid chain root is present in one run directory."""

    code = "multiple_chain_roots"


class AnalysisPlotSelectionError(AnalysisError):
    """Raised when plot parameter selection is invalid."""

    code = "invalid_plot_selection"
