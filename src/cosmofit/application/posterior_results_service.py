"""Application-layer facade for posterior result loading and exports."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from cosmofit.analysis.errors import InvalidAnalysisSettingError
from cosmofit.analysis.models import PlotExportResult
from cosmofit.analysis.service import PosteriorAnalysisService
from cosmofit.application.posterior_results_models import (
    LoadedPosteriorResults,
    PosteriorPlotArtifact,
    PosteriorPlotRequest,
    PosteriorResultsLoadOptions,
    SummaryExportArtifact,
)


class PosteriorResultsService:
    """Own one loaded posterior session behind an application-facing API."""

    def __init__(self) -> None:
        self._analysis_service: PosteriorAnalysisService | None = None
        self._loaded_results: LoadedPosteriorResults | None = None
        self._current_plot: PosteriorPlotArtifact | None = None
        self._session_directory: Path | None = None

    def clear(self) -> None:
        """Drop loaded analysis state and remove managed temporary artifacts."""

        self._analysis_service = None
        self._loaded_results = None
        self._current_plot = None
        if self._session_directory is not None:
            shutil.rmtree(self._session_directory, ignore_errors=True)
        self._session_directory = None

    def load_run(
        self,
        run_directory: Path,
        *,
        options: PosteriorResultsLoadOptions,
    ) -> LoadedPosteriorResults:
        """Open a completed run and compute the current summary."""

        self.clear()
        session_directory = Path(
            tempfile.mkdtemp(prefix="cosmofit-results-", suffix="-getdist")
        ).resolve()
        analysis_service = PosteriorAnalysisService(
            ignore_rows=options.ignore_rows,
            output_directory=session_directory,
            filled_contours=options.filled_contours,
        )
        try:
            run_analysis = analysis_service.open_run(run_directory)
            summary = analysis_service.summarize(options.confidence_levels)
        except Exception:
            shutil.rmtree(session_directory, ignore_errors=True)
            raise

        loaded = LoadedPosteriorResults(run_analysis=run_analysis, summary=summary)
        self._analysis_service = analysis_service
        self._loaded_results = loaded
        self._session_directory = session_directory
        return loaded

    def refresh_summary(
        self,
        confidence_levels: tuple[float, ...],
    ) -> LoadedPosteriorResults:
        """Refresh the summary using new credible levels for the loaded run."""

        analysis_service = self._require_analysis_service()
        run_analysis = self._require_loaded_results().run_analysis
        summary = analysis_service.summarize(confidence_levels)
        loaded = LoadedPosteriorResults(run_analysis=run_analysis, summary=summary)
        self._loaded_results = loaded
        return loaded

    def generate_plot(self, request: PosteriorPlotRequest) -> PosteriorPlotArtifact:
        """Render one plot for the currently loaded run."""

        analysis_service = self._require_analysis_service()
        loaded = self._require_loaded_results()
        parameters = _validate_plot_request(request)
        export: PlotExportResult
        if request.kind == "1d":
            export = analysis_service.plot_1d(
                parameters[0],
                confidence_levels=request.confidence_levels,
                title=request.title,
                legend_label=request.legend_label,
            )
        elif request.kind == "2d":
            export = analysis_service.plot_2d(
                parameters[0],
                parameters[1],
                confidence_levels=request.confidence_levels,
                title=request.title,
                legend_label=request.legend_label,
            )
        else:
            export = analysis_service.triangle_plot(
                parameters,
                confidence_levels=request.confidence_levels,
                title=request.title,
                legend_label=request.legend_label,
            )
        artifact = PosteriorPlotArtifact(
            kind=request.kind,
            parameters=parameters,
            confidence_levels=request.confidence_levels,
            ignore_rows=loaded.summary.settings.ignore_rows,
            title=request.title,
            legend_label=request.legend_label,
            export=export,
        )
        self._current_plot = artifact
        return artifact

    def export_summary_json(self, output_path: Path) -> SummaryExportArtifact:
        """Export the current summary as JSON to a user-selected path."""

        loaded = self._require_loaded_results()
        path = self._require_analysis_service().export_summary_json(
            confidence_levels=loaded.summary.settings.confidence_levels,
            output_path=output_path,
        )
        return SummaryExportArtifact(
            format="json",
            output_path=path,
            confidence_levels=loaded.summary.settings.confidence_levels,
            ignore_rows=loaded.summary.settings.ignore_rows,
        )

    def export_summary_csv(self, output_path: Path) -> SummaryExportArtifact:
        """Export the current summary as CSV to a user-selected path."""

        loaded = self._require_loaded_results()
        path = self._require_analysis_service().export_summary_csv(
            confidence_levels=loaded.summary.settings.confidence_levels,
            output_path=output_path,
        )
        return SummaryExportArtifact(
            format="csv",
            output_path=path,
            confidence_levels=loaded.summary.settings.confidence_levels,
            ignore_rows=loaded.summary.settings.ignore_rows,
        )

    def export_current_plot(self, output_path: Path) -> Path:
        """Copy the current plot artifact to a user-selected output path."""

        artifact = self._require_current_plot()
        source_path = (
            artifact.export.png_path
            if output_path.suffix.lower() == ".png"
            else artifact.export.pdf_path
        )
        if output_path.suffix.lower() not in {".png", ".pdf"}:
            raise InvalidAnalysisSettingError(
                "Plot export format must be .png or .pdf."
            )
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        shutil.copyfile(source_path, temporary_path)
        temporary_path.replace(output_path)
        return output_path

    def current_plot(self) -> PosteriorPlotArtifact | None:
        """Return metadata for the current generated plot, if any."""

        return self._current_plot

    def loaded_results(self) -> LoadedPosteriorResults | None:
        """Return the currently loaded run summary, if any."""

        return self._loaded_results

    def _require_analysis_service(self) -> PosteriorAnalysisService:
        if self._analysis_service is None:
            raise InvalidAnalysisSettingError(
                "No posterior run is loaded. Load a completed run first."
            )
        return self._analysis_service

    def _require_loaded_results(self) -> LoadedPosteriorResults:
        if self._loaded_results is None:
            raise InvalidAnalysisSettingError(
                "No posterior run is loaded. Load a completed run first."
            )
        return self._loaded_results

    def _require_current_plot(self) -> PosteriorPlotArtifact:
        if self._current_plot is None:
            raise InvalidAnalysisSettingError(
                "No plot is available. Generate a plot first."
            )
        return self._current_plot


def _validate_plot_request(request: PosteriorPlotRequest) -> tuple[str, ...]:
    parameters = tuple(request.parameters)
    if request.kind == "1d" and len(parameters) != 1:
        raise InvalidAnalysisSettingError(
            "1D plots require exactly one selected parameter."
        )
    if request.kind == "2d" and len(parameters) != 2:
        raise InvalidAnalysisSettingError(
            "2D plots require exactly two selected parameters."
        )
    if request.kind == "triangle" and len(parameters) < 2:
        raise InvalidAnalysisSettingError(
            "Triangle plots require at least two selected parameters."
        )
    return parameters
