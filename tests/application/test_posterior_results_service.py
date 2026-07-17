"""Tests for the application-layer posterior results facade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cosmofit.analysis import InvalidAnalysisSettingError
from cosmofit.application import (
    PosteriorPlotRequest,
    PosteriorResultsLoadOptions,
    PosteriorResultsService,
)
from tests.support.posterior_run_fixtures import create_run_fixture


def test_load_run_uses_managed_temporary_analysis_directory(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorResultsService()

    loaded = service.load_run(
        run_directory,
        options=PosteriorResultsLoadOptions(ignore_rows=0.1),
    )

    assert loaded.run_analysis.run_directory == run_directory
    assert loaded.run_analysis.run_label == "analysis-test"
    assert loaded.run_analysis.datasets == ("cosmic_chronometers",)
    assert loaded.summary.settings.ignore_rows == 0.1
    assert (
        loaded.run_analysis.analysis_directory
        != run_directory / "analysis" / "getdist"
    )
    assert loaded.run_analysis.analysis_directory.is_dir()


def test_refresh_summary_updates_credible_levels(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorResultsService()
    service.load_run(run_directory, options=PosteriorResultsLoadOptions())

    loaded = service.refresh_summary((0.95,))

    assert loaded.summary.settings.confidence_levels == (0.95,)
    assert len(loaded.summary.sampled_parameters[0].credible_intervals) == 1


def test_generate_and_export_current_plot(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorResultsService()
    service.load_run(run_directory, options=PosteriorResultsLoadOptions())

    plot = service.generate_plot(
        PosteriorPlotRequest(
            kind="2d",
            parameters=("H0", "Om"),
            confidence_levels=(0.68, 0.95),
            title="Posterior 2D",
            legend_label="Run A",
        )
    )
    exported_png = service.export_current_plot(tmp_path / "posterior.png")
    exported_pdf = service.export_current_plot(tmp_path / "posterior.pdf")

    assert plot.export.png_path.is_file()
    assert plot.export.pdf_path.is_file()
    assert exported_png.is_file()
    assert exported_pdf.is_file()


def test_current_plot_and_exports_share_same_generated_plot_request(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om", "w0"))
    service = PosteriorResultsService()
    service.load_run(run_directory, options=PosteriorResultsLoadOptions())

    request = PosteriorPlotRequest(
        kind="triangle",
        parameters=("H0", "Om", "w0"),
        confidence_levels=(0.68, 0.95),
        title="Ejemplo",
        legend_label="Prueba",
    )
    plot = service.generate_plot(request)
    current_plot = service.current_plot()

    assert current_plot is not None
    assert current_plot.kind == request.kind
    assert current_plot.parameters == request.parameters
    assert current_plot.confidence_levels == request.confidence_levels
    assert current_plot.title == request.title
    assert current_plot.legend_label == request.legend_label
    assert current_plot.export.png_path == plot.export.png_path
    assert current_plot.export.pdf_path == plot.export.pdf_path


def test_export_summary_formats_preserve_metadata(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorResultsService()
    service.load_run(
        run_directory,
        options=PosteriorResultsLoadOptions(ignore_rows=0.2, confidence_levels=(0.95,)),
    )

    json_artifact = service.export_summary_json(tmp_path / "summary.json")
    csv_artifact = service.export_summary_csv(tmp_path / "summary.csv")

    payload = json.loads(json_artifact.output_path.read_text(encoding="utf-8"))
    assert payload["analysis_settings"]["ignore_rows"] == 0.2
    assert payload["analysis_settings"]["confidence_levels"] == [0.95]
    assert csv_artifact.output_path.is_file()


def test_triangle_plot_requires_at_least_two_parameters(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorResultsService()
    service.load_run(run_directory, options=PosteriorResultsLoadOptions())

    with pytest.raises(InvalidAnalysisSettingError, match="Triangle plots require"):
        service.generate_plot(
            PosteriorPlotRequest(
                kind="triangle",
                parameters=("H0",),
                confidence_levels=(0.68, 0.95),
            )
        )


def test_clear_removes_session_directory(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorResultsService()
    loaded = service.load_run(run_directory, options=PosteriorResultsLoadOptions())
    analysis_directory = loaded.run_analysis.analysis_directory

    service.clear()

    assert not analysis_directory.exists()
    assert service.loaded_results() is None
    assert service.current_plot() is None
