"""Stable GetDist-backed analysis API for completed CosmoFit runs."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from dataclasses import asdict
from hashlib import sha1
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from getdist import loadMCSamples, plots
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.legend import Legend
from matplotlib.text import Text

from cosmofit.analysis.errors import (
    AnalysisPlotSelectionError,
    InvalidAnalysisSettingError,
)
from cosmofit.analysis.locator import LocatedRunResult, locate_run_result
from cosmofit.analysis.mathtext import validate_mathtext
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

        self.clear()
        located_run = locate_run_result(run_directory)
        analysis_directory = (
            self._output_directory
            if self._output_directory is not None
            else located_run.run_directory / "analysis" / "getdist"
        ).resolve()

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
        analysis_directory.mkdir(parents=True, exist_ok=True)
        run_analysis = RunAnalysis(
            run_directory=located_run.run_directory,
            run_label=located_run.normalized_config.runtime.run_label,
            datasets=tuple(
                dataset.kind for dataset in located_run.normalized_config.datasets
            ),
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

    def clear(self) -> None:
        """Drop any loaded run and cached GetDist samples."""

        self._located_run = None
        self._samples = None
        self._run_analysis = None

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
        legend_label: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for a one-dimensional marginal plot."""

        symbol = self._validate_selection([parameter], expected_count=1)[0]
        return self._export_plot(
            name=_plot_name("1d", (symbol,)),
            plot_kind="1d",
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.plot_1d(self._samples, symbol),
            selected_symbols=(symbol,),
            title=title,
            legend_label=legend_label,
        )

    def plot_2d(
        self,
        parameter_x: str,
        parameter_y: str,
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        title: str | None = None,
        legend_label: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for a two-dimensional contour plot."""

        symbols = self._validate_selection([parameter_x, parameter_y], expected_count=2)
        return self._export_plot(
            name=_plot_name("2d", symbols),
            plot_kind="2d",
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.plot_2d(
                self._samples,
                symbols[0],
                symbols[1],
                filled=self._filled_contours,
            ),
            selected_symbols=symbols,
            title=title,
            legend_label=legend_label,
        )

    def triangle_plot(
        self,
        parameters: tuple[str, ...] | list[str],
        *,
        confidence_levels: tuple[float, ...] = _DEFAULT_CONFIDENCE_LEVELS,
        title: str | None = None,
        legend_label: str | None = None,
    ) -> PlotExportResult:
        """Generate PNG and PDF exports for an arbitrary-order triangle plot."""

        symbols = self._validate_selection(parameters)
        return self._export_plot(
            name=_plot_name("triangle", symbols),
            plot_kind="triangle",
            confidence_levels=confidence_levels,
            render=lambda plotter: plotter.triangle_plot(
                self._samples,
                list(symbols),
                filled=self._filled_contours,
            ),
            selected_symbols=symbols,
            title=title,
            legend_label=legend_label,
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
        _write_json_atomic(path, payload)
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
        with _temporary_output_path(path) as temporary_path:
            with temporary_path.open("w", encoding="utf-8", newline="") as handle:
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
            temporary_path.replace(path)
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
        plot_kind: str,
        confidence_levels: tuple[float, ...],
        render: Any,
        selected_symbols: tuple[str, ...],
        title: str | None,
        legend_label: str | None,
    ) -> PlotExportResult:
        run_analysis = self._require_run_analysis()
        levels = _validate_confidence_levels(confidence_levels)
        self._samples.updateSettings({"contours": list(levels)})
        _validate_plot_text(
            run_analysis=run_analysis,
            selected_symbols=selected_symbols,
            title=title,
            legend_label=legend_label,
        )
        plotter = plots.get_subplot_plotter()
        output_directory = run_analysis.analysis_directory / "plots"
        output_directory.mkdir(parents=True, exist_ok=True)
        png_path = output_directory / f"{name}.png"
        pdf_path = output_directory / f"{name}.pdf"
        try:
            render(plotter)
            _apply_plot_axis_labels(
                plotter,
                run_analysis=run_analysis,
                selected_symbols=selected_symbols,
            )
            _finalize_plot_layout(
                plotter,
                plot_kind=plot_kind,
                title=title,
                legend_label=legend_label,
            )
            with (
                _temporary_output_path(png_path) as temporary_png_path,
                _temporary_output_path(pdf_path) as temporary_pdf_path,
            ):
                plotter.export(str(temporary_png_path))
                plotter.export(str(temporary_pdf_path))
                temporary_png_path.replace(png_path)
                temporary_pdf_path.replace(pdf_path)
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
                latex_label=(
                    parameter_definition.name
                    if parameter_definition is not None
                    else parameter_info.label
                ),
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


def _validate_plot_text(
    *,
    run_analysis: RunAnalysis,
    selected_symbols: tuple[str, ...],
    title: str | None,
    legend_label: str | None,
) -> None:
    validate_mathtext(title, field_name="plot title")
    validate_mathtext(legend_label, field_name="legend label")
    metadata_by_symbol = {
        metadata.symbol: metadata for metadata in run_analysis.parameter_metadata
    }
    for symbol in selected_symbols:
        metadata = metadata_by_symbol[symbol]
        validate_mathtext(
            metadata.latex_label,
            field_name=f"parameter display label '{symbol}'",
        )


def _apply_plot_axis_labels(
    plotter: Any,
    *,
    run_analysis: RunAnalysis,
    selected_symbols: tuple[str, ...],
) -> None:
    metadata_by_symbol = {
        metadata.symbol: metadata for metadata in run_analysis.parameter_metadata
    }
    replacements = {
        symbol: metadata_by_symbol[symbol].latex_label for symbol in selected_symbols
    }
    for axis in getattr(plotter.fig, "axes", []):
        xlabel = axis.get_xlabel()
        ylabel = axis.get_ylabel()
        replacement_x = replacements.get(_label_lookup_key(xlabel))
        replacement_y = replacements.get(_label_lookup_key(ylabel))
        if replacement_x is not None:
            axis.set_xlabel(replacement_x)
        if replacement_y is not None:
            axis.set_ylabel(replacement_y)


def _finalize_plot_layout(
    plotter: Any,
    *,
    plot_kind: str,
    title: str | None,
    legend_label: str | None,
) -> None:
    fig = plotter.fig
    _clear_existing_legends(fig)
    plotter.legend = None
    plotter.extra_artists = []

    scientific_axes = _scientific_axes(plotter)
    if not scientific_axes:
        if title:
            plotter.extra_artists.append(
                fig.suptitle(title, x=0.5, y=0.98, ha="center", wrap=True)
            )
        return

    top = 0.97
    right = 0.97
    if title:
        top = 0.82 if plot_kind == "triangle" else 0.9
    if plot_kind == "triangle" and legend_label:
        right = 0.78
    _resize_figure_to_preserve_axes_area(fig, top=top, right=right)
    if hasattr(fig, "subplots_adjust"):
        fig.subplots_adjust(top=top, right=right)
    _fit_axes_in_rect(scientific_axes, top=top, right=right)

    extra_artists: list[Artist] = []
    title_artist: Text | None = None
    legend_artist: Legend | None = None
    if title:
        title_artist = fig.suptitle(title, x=0.5, y=0.98, ha="center", wrap=True)
        extra_artists.append(title_artist)

    if plot_kind == "triangle" and legend_label:
        legend_artist = plotter.add_legend(
            [legend_label],
            figure=True,
            legend_loc="upper right",
            figure_legend_outside=False,
            bbox_to_anchor=(0.985, 0.94 if title else 0.98),
            bbox_transform=fig.transFigure,
            borderaxespad=0.0,
            legend_ncol=1,
        )
        extra_artists.append(legend_artist)
    elif legend_label:
        legend_artist = plotter.add_legend([legend_label])
        extra_artists.append(legend_artist)

    plotter.extra_artists = extra_artists
    _resolve_plot_layout_overlaps(
        plotter,
        plot_kind=plot_kind,
        title_artist=title_artist,
        legend_artist=legend_artist,
    )


def _resize_figure_to_preserve_axes_area(fig: Any, *, top: float, right: float) -> None:
    if not hasattr(fig, "subplotpars") or not hasattr(fig, "get_size_inches"):
        return
    subplotpars = fig.subplotpars
    original_width, original_height = fig.get_size_inches()
    width_scale = 1.0
    height_scale = 1.0
    if right < subplotpars.right and right > subplotpars.left:
        width_scale = (subplotpars.right - subplotpars.left) / (
            right - subplotpars.left
        )
    if top < subplotpars.top and top > subplotpars.bottom:
        height_scale = (subplotpars.top - subplotpars.bottom) / (
            top - subplotpars.bottom
        )
    fig.set_size_inches(
        original_width * width_scale,
        original_height * height_scale,
        forward=True,
    )


def _resolve_plot_layout_overlaps(
    plotter: Any,
    *,
    plot_kind: str,
    title_artist: Text | None,
    legend_artist: Legend | None,
) -> None:
    fig = plotter.fig
    if not hasattr(fig, "canvas") or not hasattr(fig, "subplotpars"):
        return
    for _ in range(3):
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        scientific_axes = _scientific_axes(plotter)
        if not scientific_axes:
            return
        updated = False
        if title_artist is not None and _artist_overlaps_axes(
            title_artist, scientific_axes, renderer
        ):
            figure_bbox = fig.get_window_extent(renderer)
            title_bbox = title_artist.get_window_extent(renderer)
            axes_top = max(
                axis.get_window_extent(renderer).y1 for axis in scientific_axes
            )
            required_gap = max(12.0, figure_bbox.height * 0.015)
            delta_fraction = (
                axes_top - (title_bbox.y0 - required_gap)
            ) / figure_bbox.height
            top = max(0.68, fig.subplotpars.top - max(delta_fraction, 0.04))
            _resize_figure_to_preserve_axes_area(
                fig,
                top=top,
                right=fig.subplotpars.right,
            )
            fig.subplots_adjust(top=top)
            _fit_axes_in_rect(
                scientific_axes,
                top=top,
                right=fig.subplotpars.right,
            )
            updated = True
        if (
            plot_kind == "triangle"
            and legend_artist is not None
            and _artist_overlaps_axes(legend_artist, scientific_axes, renderer)
        ):
            figure_bbox = fig.get_window_extent(renderer)
            legend_bbox = legend_artist.get_window_extent(renderer)
            axes_right = max(
                axis.get_window_extent(renderer).x1 for axis in scientific_axes
            )
            required_gap = max(12.0, figure_bbox.width * 0.015)
            delta_fraction = (
                axes_right - (legend_bbox.x0 - required_gap)
            ) / figure_bbox.width
            right = min(
                fig.subplotpars.right - 0.04,
                max(0.55, fig.subplotpars.right - max(delta_fraction, 0.05)),
            )
            _resize_figure_to_preserve_axes_area(
                fig,
                top=fig.subplotpars.top,
                right=right,
            )
            fig.subplots_adjust(right=right)
            _fit_axes_in_rect(
                scientific_axes,
                top=fig.subplotpars.top,
                right=right,
            )
            updated = True
        if not updated:
            break
    fig.canvas.draw()


def _artist_overlaps_axes(
    artist: Artist,
    axes: tuple[Axes, ...],
    renderer: Any,
) -> bool:
    artist_bbox = artist.get_window_extent(renderer)
    return any(artist_bbox.overlaps(axis.get_window_extent(renderer)) for axis in axes)


def _fit_axes_in_rect(axes: tuple[Axes, ...], *, top: float, right: float) -> None:
    if not axes:
        return
    positions = [axis.get_position().frozen() for axis in axes]
    min_left = min(position.x0 for position in positions)
    min_bottom = min(position.y0 for position in positions)
    max_right = max(position.x1 for position in positions)
    max_top = max(position.y1 for position in positions)
    current_width = max_right - min_left
    current_height = max_top - min_bottom
    target_width = right - min_left
    target_height = top - min_bottom
    if (
        current_width <= 0
        or current_height <= 0
        or target_width <= 0
        or target_height <= 0
    ):
        return
    scale_x = target_width / current_width
    scale_y = target_height / current_height
    for axis, position in zip(axes, positions, strict=True):
        axis.set_position(
            [
                min_left + (position.x0 - min_left) * scale_x,
                min_bottom + (position.y0 - min_bottom) * scale_y,
                position.width * scale_x,
                position.height * scale_y,
            ]
        )


def _clear_existing_legends(fig: Any) -> None:
    for legend in tuple(getattr(fig, "legends", ())):
        legend.remove()
    for axis in getattr(fig, "axes", ()):
        legend = axis.get_legend()
        if legend is not None:
            legend.remove()


def _scientific_axes(plotter: Any) -> tuple[Axes, ...]:
    subplots = getattr(plotter, "subplots", None)
    if subplots is None:
        return tuple(
            axis for axis in getattr(plotter.fig, "axes", ()) if isinstance(axis, Axes)
        )
    flattened = np.asarray(subplots, dtype=object).ravel()
    return tuple(axis for axis in flattened if isinstance(axis, Axes))


def _label_lookup_key(label: str) -> str:
    stripped = label.strip()
    if stripped.startswith("$") and stripped.endswith("$") and len(stripped) >= 2:
        stripped = stripped[1:-1]
    return stripped


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


def _plot_name(prefix: str, symbols: tuple[str, ...]) -> str:
    stem = prefix + "_" + "_".join(symbols)
    if len(stem) <= 120:
        return stem
    digest = sha1(stem.encode("utf-8")).hexdigest()[:12]
    visible_symbols = "_".join(symbols[:3])
    return f"{prefix}_{visible_symbols}_{digest}"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    with _temporary_output_path(path) as temporary_path:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary_path.replace(path)


class _temporary_output_path:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._temporary_path: Path | None = None

    def __enter__(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(
            prefix=self._path.stem + "-",
            suffix=self._path.suffix,
            dir=self._path.parent,
        )
        os.close(descriptor)
        Path(raw_path).unlink(missing_ok=True)
        self._temporary_path = Path(raw_path)
        return self._temporary_path

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        if self._temporary_path is not None:
            self._temporary_path.unlink(missing_ok=True)
