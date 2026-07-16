"""Dataclasses for posterior analysis metadata, summaries, and exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SampleSetKind = Literal["sampled", "nuisance", "derived"]


@dataclass(frozen=True)
class AnalysisSettings:
    """Stable analysis settings preserved in exports."""

    ignore_rows: float
    confidence_levels: tuple[float, ...]
    filled_contours: bool = True


@dataclass(frozen=True)
class CredibleInterval:
    """Credible interval for a single confidence level."""

    confidence_level: float
    lower: float
    upper: float
    limit_type: str


@dataclass(frozen=True)
class PosteriorParameterMetadata:
    """Metadata for one posterior dimension reported by GetDist."""

    symbol: str
    latex_label: str
    kind: SampleSetKind
    display_name: str
    unit: str | None


@dataclass(frozen=True)
class PosteriorParameterSummary:
    """Posterior summary for one sampled or nuisance parameter."""

    symbol: str
    display_name: str
    latex_label: str
    kind: SampleSetKind
    unit: str | None
    mean: float
    standard_deviation: float
    median: float | None
    maximum_posterior: float | None
    credible_intervals: tuple[CredibleInterval, ...]


@dataclass(frozen=True)
class FixedParameterValue:
    """Preserved fixed-parameter metadata from the original run configuration."""

    symbol: str
    display_name: str
    unit: str | None
    value: float


@dataclass(frozen=True)
class ChainDiagnostics:
    """Available diagnostics and convergence metadata from Cobaya artifacts."""

    sample_rows: int
    chain_count: int
    total_weight: float
    ignore_rows: float
    chain_root: Path
    chain_files: tuple[Path, ...]
    checkpoint_path: Path | None
    converged: bool | None
    rminus1_last: float | None
    checkpoint_burn_in: float | None
    progress_rows: int | None
    maximum_posterior_minuslogpost: float | None


@dataclass(frozen=True)
class AnalysisSummary:
    """Summary export payload for one analyzed run."""

    run_directory: Path
    chain_root: Path
    analysis_directory: Path
    settings: AnalysisSettings
    sampled_parameters: tuple[PosteriorParameterSummary, ...]
    fixed_parameters: tuple[FixedParameterValue, ...]
    diagnostics: ChainDiagnostics


@dataclass(frozen=True)
class PlotExportResult:
    """Generated plot file paths for one plot request."""

    png_path: Path
    pdf_path: Path


@dataclass(frozen=True)
class RunAnalysis:
    """Loaded run artifacts and parameter metadata for later summaries and plots."""

    run_directory: Path
    run_label: str
    datasets: tuple[str, ...]
    chain_root: Path
    analysis_directory: Path
    settings: AnalysisSettings
    selectable_parameters: tuple[str, ...]
    parameter_metadata: tuple[PosteriorParameterMetadata, ...]
    fixed_parameters: tuple[FixedParameterValue, ...]
    diagnostics: ChainDiagnostics
