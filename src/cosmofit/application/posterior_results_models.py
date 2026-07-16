"""Application-layer models for posterior results loading and export."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cosmofit.analysis.models import AnalysisSummary, PlotExportResult, RunAnalysis


@dataclass(frozen=True)
class PosteriorResultsLoadOptions:
    """Stable options for loading and summarizing one completed run."""

    ignore_rows: float = 0.0
    confidence_levels: tuple[float, ...] = (0.68, 0.95)
    filled_contours: bool = True


@dataclass(frozen=True)
class LoadedPosteriorResults:
    """Loaded posterior metadata and summary for one completed run."""

    run_analysis: RunAnalysis
    summary: AnalysisSummary


PlotKind = Literal["1d", "2d", "triangle"]


@dataclass(frozen=True)
class PosteriorPlotRequest:
    """Validated plot request parameters for one rendered plot."""

    kind: PlotKind
    parameters: tuple[str, ...]
    confidence_levels: tuple[float, ...]
    title: str | None = None
    legend_label: str | None = None


@dataclass(frozen=True)
class PosteriorPlotArtifact:
    """Generated plot files plus the request metadata used to render them."""

    kind: PlotKind
    parameters: tuple[str, ...]
    confidence_levels: tuple[float, ...]
    ignore_rows: float
    title: str | None
    legend_label: str | None
    export: PlotExportResult


@dataclass(frozen=True)
class SummaryExportArtifact:
    """Exported summary file metadata."""

    format: Literal["json", "csv"]
    output_path: Path
    confidence_levels: tuple[float, ...]
    ignore_rows: float
