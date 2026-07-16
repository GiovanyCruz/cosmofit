"""Stable GetDist-backed analysis API for completed CosmoFit runs."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from getdist import loadMCSamples, plots

from cosmofit.analysis.errors import (
    AnalysisPlotSelectionError,
    InvalidAnalysisSettingError,
)
from cosmofit.analysis.locator import LocatedRunResult, locate_run_result
from cosmofit.analysis.models import (
    AnalysisSettings,
    AnalysisSummary,
    ChainDiagnostics,
    CredibleInterval,
    FixedParameterValue,
    PlotExportResult,
    PosteriorParameterMetadata,
    PosteriorParameterSummary,
    RunAnalysis,
)

_DEFAULT_CONFIDENCE_LEVELS = (0.68, 0.95)


class PosteriorAnalysisService:
    """Open completed runs, summarize posterior dimensions, and export plots."""

    def __init__(
        self,
        *,
        ignore_rows: float = 0.0,
        output_directory: Path | None = None,
        filled_contours: bool = True,
    ) -> None:
        self._ignore_rows = _validate_ignore_rows(ignore_rows)
        self._output_directory = (
            output_directory.resolve() if output_directory else None
        )
        self._filled_contours = filled_contours
        self._located_run: LocatedRunResult | None = None
        self._samples: Any = None
        self._run_analysis: RunAnalysis | None = None

    def open_run(self, run_directory: Path) -> RunAnalysis:
        """Load a completed run directory and discover its selectable parameters."""

        located_run = locate_run_result(run_directory)
        analysis_directory = (
            self._output_directory
            if self._output_directory is not None
            else located_run.run_directory / "analysis" / "getdist"
        ).resolve()
        analysis_directory.mkdir(parents=True, exist_ok=True)

        samples = loadMCSamples(
            str(located_run.chain_root),
            no_cache=True,
            settings={"ignore_rows": self._ignore_rows},
        )
        parameter_metadata = _build_parameter_metadata(located_run, samples)
        selectable_parameters = tuple(
            metadata.symbol
            for metadata in parameter_metadata
            if metadata.kind in {"sampled", "nuisance"}
        )
        diagnostics = _build_chain_diagnostics(
            located_run,
            samples=samples,
            ignore_rows=self._ignore_rows,
        )
        fixed_parameters = tuple(
            _fixed_parameter_values(located_run.normalized_config.parameters)
        )
        run_analysis = RunAnalysis(
            run_directory=located_run.run_directory,
            chain_root=located_run.chain_root,
            analysis_directory=analysis_directory,
            settings=AnalysisSettings(
                ignore_rows=self._ignore_rows,
                confidence_levels=_DEFAULT_CONFIDENCE_LEVELS,
                filled_contours=self._filled_contours,
            ),
            selectable_parameters=selectable_parameters,
            parameter_metadata=parameter_metadata,
            fixed_parameters=fixed_parameters,
            diagnostics=diagnostics,
        )
        self._located_run = located_run
        self._samples = samples
        self._run_analysis = run_analysis
        return run_analysis

    def parameter_names(self) -> tuple[str, ...]:
        """Return selectable sampled posterior dimensions in preserved order."""

        return self._require_run_analysis().selectable_parameters

    def parameter_metadata(self) -> tuple[PosteriorParameterMetadata, ...]:
        """Return metadata for all posterior dimensions known to GetDist."""

        return self._require_run_analysis().parameter_metadata

    def summarize(
        self, confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS
    ) -> AnalysisSummary:
        """Return posterior summaries for selectable sampled parameters."""

        run_analysis = self._require_run_analysis()
        levels = _validate_confidence_levels(confidence_levels)
        self._samples.updateSettings({"contours": list(levels)})
        marge_stats = self._samples.getMargeStats()
        metadata_by_symbol = {
            metadata.symbol: metadata for metadata in run_analysis.parameter_metadata
        }
        maximum_posterior_index = _maximum_posterior_index(self._samples)
        summaries: list[PosteriorParameterSummary] = []
        for symbol in run_analysis.selectable_parameters:
            parameter_stats = marge_stats.parWithName(symbol)
            metadata = metadata_by_symbol[symbol]
            intervals = tuple(
                CredibleInterval(
                    confidence_level=level,
                    lower=float(limit.lower),
                    upper=float(limit.upper),
                    limit_type=limit.limitType(),
                )
                for level, limit in zip(levels, parameter_stats.limits, strict=True)
            )
            column = _parameter_column_index(self._samples, symbol)
            values = self._samples.samples[:, column]
            summaries.append(
                PosteriorParameterSummary(
                    symbol=symbol,
                    display_name=metadata.display_name,
                    latex_label=metadata.latex_label,
                    kind=metadata.kind,
                    unit=metadata.unit,
                    mean=float(parameter_stats.mean),
                    standard_deviation=float(parameter_stats.err),
                    median=_weighted_quantile(values, self._samples.weights, 0.5),
                    maximum_posterior=(
                        float(self._samples.samples[maximum_posterior_index, column])
                        if maximum_posterior_index is not None
                        else None
                    ),
                    credible_intervals=intervals,
                )
            )
        return AnalysisSummary(
            run_directory=run_analysis.run_directory,
            chain_root=run_analysis.chain_root,
            analysis_directory=run_analysis.analysis_directory,
            settings=AnalysisSettings(
                ignore_rows=run_analysis.settings.ignore_rows,
                confidence_levels=levels,
                filled_contours=run_analysis.settings.filled_contours,
            ),
            sampled_parameters=tuple(summaries),
            fixed_parameters=run_analysis.fixed_parameters,
            diagnostics=run_analysis.diagnostics,
        )

    def plot_1d(
        self,
        parameter: str,
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        title: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for a one-dimensional marginal plot."""

        symbol = self._validate_selection([parameter], expected_count=1)[0]
        return self._export_plot(
            name=f"1d_{symbol}",
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.plot_1d(self._samples, symbol),
            title=title,
        )

    def plot_2d(
        self,
        parameter_x: str,
        parameter_y: str,
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        title: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for a two-dimensional contour plot."""

        symbols = self._validate_selection([parameter_x, parameter_y], expected_count=2)
        return self._export_plot(
            name=f"2d_{symbols[0]}_{symbols[1]}",
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.plot_2d(
                self._samples,
                symbols[0],
                symbols[1],
                filled=self._filled_contours,
            ),
            title=title,
        )

    def triangle_plot(
        self,
        parameters: tuple[str, ...] | list[str],
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        title: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for an arbitrary-order triangle plot."""

        symbols = self._validate_selection(parameters)
        return self._export_plot(
            name="triangle_" + "_".join(symbols),
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.triangle_plot(
                self._samples,
                list(symbols),
                filled=self._filled_contours,
            ),
            title=title,
        )

    def export_summary_json(
        self,
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        output_path: Path | None = None,
    ) -> Path:
        """Export summary metadata and posterior statistics to JSON."""

        summary = self.summarize(confidence_levels)
        path = (
            output_path.resolve()
            if output_path is not None
            else summary.analysis_directory / "summary.json"
        )
        payload = {
            "source_run_directory": str(summary.run_directory),
            "chain_root": str(summary.chain_root),
            "analysis_directory": str(summary.analysis_directory),
            "analysis_settings": {
                "ignore_rows": summary.settings.ignore_rows,
                "confidence_levels": list(summary.settings.confidence_levels),
                "filled_contours": summary.settings.filled_contours,
            },
            "sampled_parameters": [asdict(item) for item in summary.sampled_parameters],
            "fixed_parameters": [asdict(item) for item in summary.fixed_parameters],
            "diagnostics": _serialize_dataclass_paths(summary.diagnostics),
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    def export_summary_csv(
        self,
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        output_path: Path | None = None,
    ) -> Path:
        """Export posterior summaries to CSV with stable field names."""

        summary = self.summarize(confidence_levels)
        path = (
            output_path.resolve()
            if output_path is not None
            else summary.analysis_directory / "summary.csv"
        )
        level_tokens = [_confidence_level_token(level) for level in confidence_levels]
        fieldnames = [
            "source_run_directory",
            "chain_root",
            "ignore_rows",
            "parameter_symbol",
            "parameter_name",
            "latex_label",
            "parameter_kind",
            "unit",
            "mean",
            "standard_deviation",
            "median",
            "maximum_posterior",
        ]
        for token in level_tokens:
            fieldnames.extend(
                [f"cl_{token}_lower", f"cl_{token}_upper", f"cl_{token}_limit_type"]
            )
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for parameter in summary.sampled_parameters:
                row = {
                    "source_run_directory": str(summary.run_directory),
                    "chain_root": str(summary.chain_root),
                    "ignore_rows": summary.settings.ignore_rows,
                    "parameter_symbol": parameter.symbol,
                    "parameter_name": parameter.display_name,
                    "latex_label": parameter.latex_label,
                    "parameter_kind": parameter.kind,
                    "unit": parameter.unit or "",
                    "mean": parameter.mean,
                    "standard_deviation": parameter.standard_deviation,
                    "median": parameter.median,
                    "maximum_posterior": parameter.maximum_posterior,
                }
                for interval, token in zip(
                    parameter.credible_intervals, level_tokens, strict=True
                ):
                    row[f"cl_{token}_lower"] = interval.lower
                    row[f"cl_{token}_upper"] = interval.upper
                    row[f"cl_{token}_limit_type"] = interval.limit_type
                writer.writerow(row)
        return path

    def _validate_selection(
        self,
        parameters: tuple[str, ...] | list[str],
        *,
        expected_count: int | None = None,
    ) -> tuple[str, ...]:
        selectable = self.parameter_names()
        symbols = tuple(parameters)
        if not symbols:
            raise AnalysisPlotSelectionError("At least one parameter must be selected.")
        if expected_count is not None and len(symbols) != expected_count:
            raise AnalysisPlotSelectionError(
                "Expected exactly "
                f"{expected_count} parameter(s), received {len(symbols)}."
            )
        seen: set[str] = set()
        for symbol in symbols:
            if symbol not in selectable:
                raise AnalysisPlotSelectionError(
                    f"Unknown or non-sampled parameter '{symbol}'. "
                    f"Available parameters: {', '.join(selectable)}."
                )
            if symbol in seen:
                raise AnalysisPlotSelectionError(
                    f"Duplicate parameter selection '{symbol}' is not allowed."
                )
            seen.add(symbol)
        return symbols

    def _export_plot(
        self,
        *,
        name: str,
        confidence_levels: tuple[float, ...],
        render: Any,
        title: str | None,
    ) -> PlotExportResult:
        run_analysis = self._require_run_analysis()
        levels = _validate_confidence_levels(confidence_levels)
        self._samples.updateSettings({"contours": list(levels)})
        plotter = plots.get_subplot_plotter()
        render(plotter)
        if title:
            plotter.fig.suptitle(title)
        output_directory = run_analysis.analysis_directory / "plots"
        output_directory.mkdir(parents=True, exist_ok=True)
        png_path = output_directory / f"{name}.png"
        pdf_path = output_directory / f"{name}.pdf"
        try:
            plotter.export(str(png_path))
            plotter.export(str(pdf_path))
        finally:
            plt.close(plotter.fig)
        return PlotExportResult(png_path=png_path, pdf_path=pdf_path)

    def _require_run_analysis(self) -> RunAnalysis:
        if self._run_analysis is None or self._samples is None:
            raise InvalidAnalysisSettingError(
                "No run is open. Call open_run(run_directory) before "
                "requesting analysis."
            )
        return self._run_analysis


def _build_parameter_metadata(
    located_run: LocatedRunResult, samples: Any
) -> tuple[PosteriorParameterMetadata, ...]:
    parameter_definitions = {
        parameter.symbol: parameter
        for parameter in located_run.normalized_config.parameters
    }
    metadata: list[PosteriorParameterMetadata] = []
    for parameter_info in samples.getParamNames().names:
        parameter_definition = parameter_definitions.get(parameter_info.name)
        if getattr(parameter_info, "isDerived", False):
            kind = "derived"
        elif parameter_definition is None:
            kind = "nuisance"
        else:
            kind = "sampled"
        metadata.append(
            PosteriorParameterMetadata(
                symbol=parameter_info.name,
                latex_label=parameter_info.label,
                kind=kind,
                display_name=(
                    parameter_definition.name
                    if parameter_definition is not None
                    else parameter_info.name
                ),
                unit=(
                    parameter_definition.unit
                    if parameter_definition is not None
                    else None
                ),
            )
        )
    ordered_metadata = _ordered_sample_metadata(metadata, located_run)
    return tuple(ordered_metadata)


def _ordered_sample_metadata(
    metadata: list[PosteriorParameterMetadata], located_run: LocatedRunResult
) -> list[PosteriorParameterMetadata]:
    run_order = {
        parameter.symbol: index
        for index, parameter in enumerate(located_run.normalized_config.parameters)
    }
    known = [item for item in metadata if item.symbol in run_order]
    nuisance = [item for item in metadata if item.kind == "nuisance"]
    derived = [item for item in metadata if item.kind == "derived"]
    known.sort(key=lambda item: run_order[item.symbol])
    return known + nuisance + derived


def _build_chain_diagnostics(
    located_run: LocatedRunResult, *, samples: Any, ignore_rows: float
) -> ChainDiagnostics:
    checkpoint_sampler = ((located_run.checkpoint or {}).get("sampler") or {}).get(
        "mcmc"
    ) or {}
    return ChainDiagnostics(
        sample_rows=int(samples.samples.shape[0]),
        chain_count=len(located_run.chain_files),
        total_weight=float(np.sum(samples.weights)),
        ignore_rows=ignore_rows,
        chain_root=located_run.chain_root,
        chain_files=located_run.chain_files,
        checkpoint_path=located_run.chain_root.with_suffix(".checkpoint")
        if located_run.chain_root.with_suffix(".checkpoint").is_file()
        else None,
        converged=_optional_bool(checkpoint_sampler.get("converged")),
        rminus1_last=_optional_float(checkpoint_sampler.get("Rminus1_last")),
        checkpoint_burn_in=_optional_float(checkpoint_sampler.get("burn_in")),
        progress_rows=_optional_int(located_run.summary.get("progress_rows")),
        maximum_posterior_minuslogpost=_minimum_loglike(samples),
    )


def _fixed_parameter_values(parameters: tuple[Any, ...]) -> list[FixedParameterValue]:
    fixed_parameters: list[FixedParameterValue] = []
    for parameter in parameters:
        if parameter.role != "fixed":
            continue
        assert parameter.value is not None
        fixed_parameters.append(
            FixedParameterValue(
                symbol=parameter.symbol,
                display_name=parameter.name,
                unit=parameter.unit,
                value=parameter.value,
            )
        )
    return fixed_parameters


def _validate_ignore_rows(ignore_rows: float) -> float:
    if not 0.0 <= ignore_rows < 1.0:
        raise InvalidAnalysisSettingError(
            "ignore_rows must be between 0 and 1 "
            f"(inclusive of 0, exclusive of 1); got {ignore_rows}."
        )
    return ignore_rows


def _validate_confidence_levels(levels: tuple[float, ...]) -> tuple[float, ...]:
    if not levels:
        raise InvalidAnalysisSettingError("At least one confidence level is required.")
    for level in levels:
        if not 0.0 < level < 1.0:
            raise InvalidAnalysisSettingError(
                f"Confidence levels must lie strictly between 0 and 1; got {level}."
            )
    if tuple(sorted(levels)) != levels:
        raise InvalidAnalysisSettingError(
            "Confidence levels must be provided in ascending order."
        )
    if len(set(levels)) != len(levels):
        raise InvalidAnalysisSettingError("Confidence levels must be unique.")
    return levels


def _parameter_column_index(samples: Any, symbol: str) -> int:
    for index, parameter_info in enumerate(samples.getParamNames().names):
        if parameter_info.name == symbol:
            return index
    raise AnalysisPlotSelectionError(f"Parameter '{symbol}' is not present in samples.")


def _weighted_quantile(
    values: np.ndarray, weights: np.ndarray, quantile: float
) -> float | None:
    if values.size == 0:
        return None
    order = np.argsort(values)
    ordered_values = values[order]
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    if cumulative[-1] <= 0:
        return None
    target = quantile * cumulative[-1]
    return float(ordered_values[np.searchsorted(cumulative, target, side="left")])


def _maximum_posterior_index(samples: Any) -> int | None:
    if getattr(samples, "loglikes", None) is None or len(samples.loglikes) == 0:
        return None
    return int(np.argmin(samples.loglikes))


def _minimum_loglike(samples: Any) -> float | None:
    index = _maximum_posterior_index(samples)
    if index is None:
        return None
    return float(samples.loglikes[index])


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _confidence_level_token(level: float) -> str:
    return str(level).replace(".", "p")


def _serialize_dataclass_paths(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, tuple):
        return [_serialize_dataclass_paths(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: _serialize_dataclass_paths(item) for key, item in asdict(value).items()
        }
    return value
