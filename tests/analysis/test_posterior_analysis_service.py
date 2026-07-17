"""Tests for GetDist-backed posterior analysis on completed run artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from getdist import plots
from matplotlib.axes import Axes
from matplotlib.legend import Legend

from cosmofit.analysis import (
    AnalysisPlotSelectionError,
    InvalidAnalysisSettingError,
    InvalidMathTextError,
    MalformedRunDirectoryError,
    MultipleChainRootsError,
    PosteriorAnalysisService,
    RunNotSuccessfulError,
)
from cosmofit.analysis.mathtext import (
    is_matplotlib_usetex_enabled,
    validate_mathtext,
)
from cosmofit.analysis.service import (
    _apply_plot_axis_labels,
    _finalize_plot_layout,
    _scientific_axes,
)
from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
    serialize_run_config,
)


def test_open_run_discovers_chain_root_and_sampled_parameters(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("Om", "w0"),
        fixed_parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="fixed",
                unit="km/s/Mpc",
                value=70.0,
            ),
        ),
    )
    service = PosteriorAnalysisService()

    run_analysis = service.open_run(run_directory)

    assert run_analysis.chain_root == run_directory / "chains" / "chain"
    assert run_analysis.run_label == "analysis-test"
    assert run_analysis.datasets == ("cosmic_chronometers",)
    assert service.parameter_names() == ("Om", "w0")
    metadata = {item.symbol: item for item in service.parameter_metadata()}
    assert metadata["Om"].kind == "sampled"
    assert metadata["w0"].kind == "sampled"
    assert metadata["chi2"].kind == "derived"
    assert run_analysis.fixed_parameters[0].symbol == "H0"


def test_open_run_supports_multiple_chain_files(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0", "Om"),
        chain_count=2,
    )
    service = PosteriorAnalysisService()

    run_analysis = service.open_run(run_directory)

    assert run_analysis.diagnostics.chain_count == 2
    assert len(run_analysis.diagnostics.chain_files) == 2


def test_parameter_names_preserve_selected_sampled_order(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("wa", "Om", "H0"),
    )
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    assert service.parameter_names() == ("wa", "Om", "H0")


def test_parameter_metadata_marks_nuisance_parameters_when_present(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0", "Om"),
        nuisance_symbols=("nuisance_a",),
    )
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    metadata = {item.symbol: item for item in service.parameter_metadata()}
    assert metadata["nuisance_a"].kind == "nuisance"


def test_summarize_returns_intervals_and_maximum_posterior(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0", "Om"),
    )
    service = PosteriorAnalysisService(ignore_rows=0.1)
    service.open_run(run_directory)

    summary = service.summarize((0.68, 0.95))

    assert [item.symbol for item in summary.sampled_parameters] == ["H0", "Om"]
    assert summary.diagnostics.ignore_rows == 0.1
    assert all(
        item.maximum_posterior is not None for item in summary.sampled_parameters
    )
    assert len(summary.sampled_parameters[0].credible_intervals) == 2


def test_plot_1d_generates_png_and_pdf(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.plot_1d("H0")

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()
    assert (
        plot_paths.png_path.parent == run_directory / "analysis" / "getdist" / "plots"
    )
    assert plot_paths.png_path.stat().st_size > 0
    assert plot_paths.pdf_path.stat().st_size > 0


def test_plot_2d_generates_png_and_pdf(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.plot_2d("H0", "Om")

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()


def test_plain_text_title_is_supported(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.plot_1d("H0", title="Posterior constraints")

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()


def test_valid_mathtext_title_is_supported(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.plot_1d("H0", title=r"Posterior constraints on $H_0$")

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()


def test_valid_greek_parameter_label_is_used_for_metadata(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("Om",),
        display_names={"Om": r"$\Omega_m$"},
    )
    service = PosteriorAnalysisService()

    run_analysis = service.open_run(run_directory)
    plot_paths = service.plot_1d("Om")

    assert run_analysis.parameter_metadata[0].latex_label == r"$\Omega_m$"
    assert plot_paths.png_path.is_file()


def test_subscript_and_superscript_labels_are_supported(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0", "wa"),
        display_names={
            "H0": r"$H_0$",
            "wa": r"$w_a^2$",
        },
    )
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.triangle_plot(("H0", "wa"), title=r"$H_0$ vs $w_a^2$")

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()


def test_malformed_mathtext_is_rejected_cleanly(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("Om",),
        display_names={"Om": r"$\Omega_m"},
    )
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    with pytest.raises(InvalidMathTextError, match="parameter display label 'Om'"):
        service.plot_1d("Om")


def test_validate_mathtext_rejects_unmatched_opening_dollar() -> None:
    with pytest.raises(
        InvalidMathTextError,
        match="plot title: unbalanced MathText dollar delimiters",
    ):
        validate_mathtext(r"$H_0", field_name="plot title")


def test_validate_mathtext_rejects_unmatched_closing_dollar() -> None:
    with pytest.raises(
        InvalidMathTextError,
        match="legend label: unbalanced MathText dollar delimiters",
    ):
        validate_mathtext(r"H_0$", field_name="legend label")


def test_validate_mathtext_accepts_valid_balanced_mathtext() -> None:
    validate_mathtext(r"$\Omega_m$", field_name="plot title")


def test_validate_mathtext_accepts_multiple_balanced_segments() -> None:
    validate_mathtext(
        r"Posterior for $\Lambda$CDM and $H_0$",
        field_name="legend label",
    )


def test_validate_mathtext_rejects_malformed_command() -> None:
    with pytest.raises(InvalidMathTextError, match="parameter display label 'Om'"):
        validate_mathtext(r"$\badcommand$", field_name="parameter display label 'Om'")


def test_validate_mathtext_ignores_escaped_literal_dollar_sign() -> None:
    validate_mathtext(r"Cost is \$10^{-3}", field_name="legend label")


def test_validate_mathtext_accepts_plain_text_without_mathtext() -> None:
    validate_mathtext("Plain text", field_name="plot title")


def test_mathtext_plotting_does_not_require_external_latex(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.plot_1d("H0", title=r"$H_0$")

    assert plot_paths.png_path.is_file()
    assert is_matplotlib_usetex_enabled() is False


def test_triangle_plot_supports_five_parameters_and_selected_order(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("q5", "q2", "q4", "q1", "q3"),
    )
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plot_paths = service.triangle_plot(("q4", "q1", "q5", "q2", "q3"))

    assert plot_paths.png_path.is_file()
    assert plot_paths.pdf_path.is_file()
    assert plot_paths.png_path.name == "triangle_q4_q1_q5_q2_q3.png"


def test_triangle_plot_uses_figure_level_suptitle_and_reserved_top_margin(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om", "w0"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plotter = _render_plot_for_layout(
        service,
        kind="triangle",
        parameters=("H0", "Om", "w0"),
        title="Ejemplo",
        legend_label=None,
    )

    try:
        assert plotter.fig._suptitle is not None
        assert plotter.fig._suptitle.get_text() == "Ejemplo"
        assert plotter.fig.subplotpars.top < 0.93
        assert _axes_with_title(plotter, "Ejemplo") == []
        _assert_suptitle_does_not_overlap_top_row_axes(plotter)
    finally:
        plotter.fig.clear()


def test_triangle_plot_legend_is_figure_level_outside_scientific_axes(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om", "w0"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plotter = _render_plot_for_layout(
        service,
        kind="triangle",
        parameters=("H0", "Om", "w0"),
        title="Ejemplo",
        legend_label="Prueba",
    )

    try:
        legends = _figure_legends(plotter)
        assert len(legends) == 1
        assert legends[0].get_texts()[0].get_text() == "Prueba"
        assert _axes_legends(plotter) == []
        _assert_legend_does_not_overlap_triangle_axes(plotter)
        _assert_legend_does_not_overlap_lower_right_diagonal_axis(plotter)
    finally:
        plotter.fig.clear()


def test_triangle_plot_omits_empty_legend_label_cleanly(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plotter = _render_plot_for_layout(
        service,
        kind="triangle",
        parameters=("H0", "Om"),
        title="Ejemplo",
        legend_label=None,
    )

    try:
        assert _figure_legends(plotter) == []
        assert _axes_legends(plotter) == []
    finally:
        plotter.fig.clear()


def test_triangle_plot_supports_mathtext_title_and_legend_without_overlap(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om", "w0"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plotter = _render_plot_for_layout(
        service,
        kind="triangle",
        parameters=("H0", "Om", "w0"),
        title=r"Posterior for $\Lambda$CDM",
        legend_label=r"$\Lambda$CDM",
    )

    try:
        assert plotter.fig._suptitle is not None
        assert plotter.fig._suptitle.get_text() == r"Posterior for $\Lambda$CDM"
        legends = _figure_legends(plotter)
        assert len(legends) == 1
        assert legends[0].get_texts()[0].get_text() == r"$\Lambda$CDM"
        _assert_suptitle_does_not_overlap_top_row_axes(plotter)
        _assert_legend_does_not_overlap_triangle_axes(plotter)
    finally:
        plotter.fig.clear()


def test_1d_and_2d_titles_remain_figure_level_without_regression(
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    plotter_1d = _render_plot_for_layout(
        service,
        kind="1d",
        parameters=("H0",),
        title="Ejemplo",
        legend_label="Prueba",
    )
    plotter_2d = _render_plot_for_layout(
        service,
        kind="2d",
        parameters=("H0", "Om"),
        title=r"Posterior for $\Lambda$CDM",
        legend_label=r"$\Lambda$CDM",
    )

    try:
        assert plotter_1d.fig._suptitle is not None
        assert _axes_with_title(plotter_1d, "Ejemplo") == []
        assert plotter_2d.fig._suptitle is not None
        assert _axes_with_title(plotter_2d, r"Posterior for $\Lambda$CDM") == []
    finally:
        plotter_1d.fig.clear()
        plotter_2d.fig.clear()


def test_duplicate_parameter_selection_is_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    with pytest.raises(AnalysisPlotSelectionError, match="Duplicate"):
        service.plot_2d("H0", "H0")


def test_duplicate_triangle_parameter_selection_is_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om", "w0"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    with pytest.raises(AnalysisPlotSelectionError, match="Duplicate"):
        service.triangle_plot(("H0", "Om", "H0"))


def test_unknown_parameter_selection_is_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    with pytest.raises(AnalysisPlotSelectionError, match="Unknown or non-sampled"):
        service.plot_1d("missing")


def test_invalid_ignore_rows_is_rejected() -> None:
    with pytest.raises(InvalidAnalysisSettingError, match="ignore_rows"):
        PosteriorAnalysisService(ignore_rows=1.0)


def test_missing_chain_files_are_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0",),
        write_chains=False,
    )
    service = PosteriorAnalysisService()

    with pytest.raises(MalformedRunDirectoryError, match="no chain text files"):
        service.open_run(run_directory)


def test_failed_run_status_is_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(
        tmp_path,
        sampled_symbols=("H0",),
        status_state="failed",
    )
    service = PosteriorAnalysisService()

    with pytest.raises(RunNotSuccessfulError, match="state='failed'"):
        service.open_run(run_directory)


def test_malformed_run_directory_is_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    (run_directory / "normalized_config.json").unlink()
    service = PosteriorAnalysisService()

    with pytest.raises(MalformedRunDirectoryError, match="normalized_config.json"):
        service.open_run(run_directory)


def test_multiple_chain_roots_are_rejected(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    chains_directory = run_directory / "chains"
    (chains_directory / "other.updated.yaml").write_text(
        (chains_directory / "chain.updated.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (chains_directory / "other.1.txt").write_text(
        (chains_directory / "chain.1.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    service = PosteriorAnalysisService()

    with pytest.raises(MultipleChainRootsError, match="multiple chain roots"):
        service.open_run(run_directory)


def test_export_summary_json_creates_expected_payload(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService(ignore_rows=0.2)
    service.open_run(run_directory)

    output_path = service.export_summary_json(confidence_levels=(0.68,))

    with output_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["source_run_directory"] == str(run_directory)
    assert payload["analysis_settings"]["ignore_rows"] == 0.2
    assert [item["symbol"] for item in payload["sampled_parameters"]] == ["H0", "Om"]


def test_export_summary_csv_creates_expected_rows(tmp_path: Path) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0", "Om"))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    output_path = service.export_summary_csv(confidence_levels=(0.68, 0.95))

    with output_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["parameter_symbol"] for row in rows] == ["H0", "Om"]
    assert "cl_0p68_lower" in rows[0]
    assert Path(rows[0]["chain_root"]) == run_directory / "chains" / "chain"


def test_failed_second_open_clears_previous_loaded_state(tmp_path: Path) -> None:
    first_run = create_run_fixture(tmp_path / "first", sampled_symbols=("H0", "Om"))
    second_run = create_run_fixture(tmp_path / "second", sampled_symbols=("w0",))
    (second_run / "normalized_config.json").unlink()
    service = PosteriorAnalysisService()
    service.open_run(first_run)

    with pytest.raises(MalformedRunDirectoryError):
        service.open_run(second_run)

    with pytest.raises(InvalidAnalysisSettingError, match="No run is open"):
        service.parameter_names()
    assert not (second_run / "analysis" / "getdist").exists()


def test_failed_plot_export_does_not_leave_partial_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_directory = create_run_fixture(tmp_path, sampled_symbols=("H0",))
    service = PosteriorAnalysisService()
    service.open_run(run_directory)

    class FakeFigure:
        def suptitle(self, _title: str) -> None:
            return None

    class FakePlotter:
        def __init__(self) -> None:
            self.fig = FakeFigure()
            self.export_calls = 0

        def plot_1d(self, *_args, **_kwargs) -> None:
            return None

        def export(self, path: str) -> None:
            self.export_calls += 1
            if self.export_calls == 1:
                Path(path).write_text("partial", encoding="utf-8")
                return
            raise RuntimeError("pdf export failed")

    monkeypatch.setattr(
        "cosmofit.analysis.service.plots.get_subplot_plotter",
        FakePlotter,
    )
    monkeypatch.setattr("cosmofit.analysis.service.plt.close", lambda _figure: None)

    with pytest.raises(RuntimeError, match="pdf export failed"):
        service.plot_1d("H0")

    plots_directory = run_directory / "analysis" / "getdist" / "plots"
    assert not (plots_directory / "1d_H0.png").exists()
    assert not (plots_directory / "1d_H0.pdf").exists()


def test_analysis_package_does_not_import_pyside6() -> None:
    source_files = sorted(Path("src/cosmofit/analysis").glob("*.py"))

    assert source_files
    for path in source_files:
        assert "PySide6" not in path.read_text(encoding="utf-8")


def create_run_fixture(
    tmp_path: Path,
    *,
    sampled_symbols: tuple[str, ...],
    fixed_parameters: tuple[ParameterConfig, ...] = (),
    nuisance_symbols: tuple[str, ...] = (),
    display_names: dict[str, str] | None = None,
    chain_count: int = 1,
    write_chains: bool = True,
    status_state: str = "succeeded",
) -> Path:
    run_directory = tmp_path / "run"
    chains_directory = run_directory / "chains"
    logs_directory = run_directory / "logs"
    chains_directory.mkdir(parents=True)
    logs_directory.mkdir()

    sampled_parameters = tuple(
        ParameterConfig(
            name=(display_names or {}).get(symbol, symbol),
            symbol=symbol,
            role="sampled",
            prior=UniformPriorConfig(minimum=-5.0, maximum=5.0),
            reference=0.0,
            proposal=0.2,
        )
        for symbol in sampled_symbols
    )
    run_config = RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=(
                "H0*sqrt(Om*(1+z)**3 + 1-Om)"
                if "H0" in sampled_symbols
                else "70*sqrt(0.3*(1+z)**3 + 0.7)"
            ),
            allowed_functions=("sqrt",),
        ),
        parameters=fixed_parameters + sampled_parameters,
        datasets=(
            CosmicChronometerDatasetConfig(
                kind="cosmic_chronometers",
                data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
            ),
        ),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=7,
            burn_in=0,
            max_samples=100,
            learn_proposal=False,
            Rminus1_stop=0.2,
            Rminus1_cl_stop=0.2,
        ),
        runtime=RuntimeConfig(
            run_label="analysis-test",
            output_directory=run_directory,
            overwrite=True,
        ),
    )

    write_json(
        run_directory / "normalized_config.json",
        serialize_run_config(run_config),
    )
    write_json(
        run_directory / "status.json",
        {"state": status_state, "run_directory": str(run_directory)},
    )
    write_json(run_directory / "summary.json", {"progress_rows": 0})
    write_json(run_directory / "metadata.json", {"python_version": "3.13.5"})
    write_yaml(run_directory / "input.yaml", serialize_run_config(run_config))
    write_yaml(run_directory / "cobaya_input.yaml", {"output": "chain"})
    write_yaml(run_directory / "updated_cobaya_input.yaml", {"output": "chain"})
    for log_name in ("worker.log", "cobaya.stdout.log", "cobaya.stderr.log"):
        (logs_directory / log_name).write_text("", encoding="utf-8")

    updated_yaml = {
        "params": {},
        "likelihood": {
            "mock_like": {
                "type": [],
                "speed": -1,
                "stop_at_error": False,
                "version": None,
                "input_params": [],
                "output_params": [],
            }
        },
        "sampler": {
            "mcmc": {
                "sampler_type": "mcmc",
                "burn_in": 0,
                "max_samples": 100,
                "Rminus1_stop": 0.2,
                "Rminus1_cl_stop": 0.2,
                "Rminus1_cl_level": 0.95,
                "version": "3.6.2",
            }
        },
        "output": "chain",
        "stop_at_error": True,
        "version": "3.6.2",
    }
    for parameter in fixed_parameters:
        updated_yaml["params"][parameter.symbol] = {"value": parameter.value}
    for parameter in sampled_parameters:
        updated_yaml["params"][parameter.symbol] = {
            "prior": {"min": -5.0, "max": 5.0},
            "ref": 0.0,
            "proposal": 0.2,
        }
    for nuisance_symbol in nuisance_symbols:
        updated_yaml["params"][nuisance_symbol] = {
            "prior": {"min": -3.0, "max": 3.0},
            "ref": 0.0,
            "proposal": 0.1,
        }
    write_yaml(chains_directory / "chain.updated.yaml", updated_yaml)
    write_yaml(chains_directory / "chain.input.yaml", updated_yaml)
    write_yaml(
        chains_directory / "chain.checkpoint",
        {
            "sampler": {
                "mcmc": {"converged": True, "Rminus1_last": 0.01, "burn_in": 0.0}
            }
        },
    )
    (chains_directory / "chain.progress").write_text("", encoding="utf-8")
    (chains_directory / "chain.covmat").write_text("", encoding="utf-8")

    if write_chains:
        rows = build_chain_rows(
            sampled_symbols=sampled_symbols,
            nuisance_symbols=nuisance_symbols,
            chain_count=chain_count,
        )
        for chain_index, chain_rows in enumerate(rows, start=1):
            write_chain_file(
                chains_directory / f"chain.{chain_index}.txt",
                sampled_symbols=sampled_symbols,
                nuisance_symbols=nuisance_symbols,
                rows=chain_rows,
            )

    return run_directory


def _render_plot_for_layout(
    service: PosteriorAnalysisService,
    *,
    kind: str,
    parameters: tuple[str, ...],
    title: str | None,
    legend_label: str | None,
):
    plotter = plots.get_subplot_plotter()
    if kind == "1d":
        plotter.plot_1d(service._samples, parameters[0])  # noqa: SLF001
    elif kind == "2d":
        plotter.plot_2d(
            service._samples,  # noqa: SLF001
            parameters[0],
            parameters[1],
            filled=True,
        )
    else:
        plotter.triangle_plot(
            service._samples,  # noqa: SLF001
            list(parameters),
            filled=True,
        )
    _apply_plot_axis_labels(
        plotter,
        run_analysis=service._require_run_analysis(),  # noqa: SLF001
        selected_symbols=parameters,
    )
    _finalize_plot_layout(
        plotter,
        plot_kind=kind,
        title=title,
        legend_label=legend_label,
    )
    plotter.fig.canvas.draw()
    return plotter


def _figure_legends(plotter) -> list[Legend]:
    return list(plotter.fig.legends)


def _axes_legends(plotter) -> list[Legend]:
    legends: list[Legend] = []
    for axis in _scientific_axes(plotter):
        legend = axis.get_legend()
        if legend is not None:
            legends.append(legend)
    return legends


def _axes_with_title(plotter, title: str) -> list[Axes]:
    return [axis for axis in _scientific_axes(plotter) if axis.get_title() == title]


def _assert_suptitle_does_not_overlap_top_row_axes(plotter) -> None:
    suptitle = plotter.fig._suptitle
    assert suptitle is not None
    renderer = plotter.fig.canvas.get_renderer()
    title_bbox = suptitle.get_window_extent(renderer)
    for axis in _top_row_axes(plotter):
        assert not title_bbox.overlaps(axis.get_window_extent(renderer))


def _assert_legend_does_not_overlap_triangle_axes(plotter) -> None:
    legends = _figure_legends(plotter)
    assert len(legends) == 1
    renderer = plotter.fig.canvas.get_renderer()
    legend_bbox = legends[0].get_window_extent(renderer)
    for axis in _scientific_axes(plotter):
        assert not legend_bbox.overlaps(axis.get_window_extent(renderer))


def _assert_legend_does_not_overlap_lower_right_diagonal_axis(plotter) -> None:
    legends = _figure_legends(plotter)
    assert len(legends) == 1
    renderer = plotter.fig.canvas.get_renderer()
    legend_bbox = legends[0].get_window_extent(renderer)
    assert not legend_bbox.overlaps(
        _lower_right_diagonal_axis(plotter).get_window_extent(renderer)
    )


def _top_row_axes(plotter) -> list[Axes]:
    scientific_axes = _scientific_axes(plotter)
    renderer = plotter.fig.canvas.get_renderer()
    max_top = max(axis.get_window_extent(renderer).y1 for axis in scientific_axes)
    return [
        axis
        for axis in scientific_axes
        if abs(axis.get_window_extent(renderer).y1 - max_top) < 1.0
    ]


def _lower_right_diagonal_axis(plotter) -> Axes:
    subplots = np.asarray(plotter.subplots, dtype=object)
    axis = subplots[-1, -1]
    assert isinstance(axis, Axes)
    return axis


def build_chain_rows(
    *,
    sampled_symbols: tuple[str, ...],
    nuisance_symbols: tuple[str, ...],
    chain_count: int,
) -> list[list[tuple[float, ...]]]:
    rng = np.random.default_rng(12345)
    parameter_symbols = sampled_symbols + nuisance_symbols
    means = np.linspace(-0.5, 0.5, num=len(parameter_symbols), endpoint=True)
    sample_count = 240
    raw_samples = rng.normal(
        loc=means,
        scale=0.2,
        size=(sample_count, len(parameter_symbols)),
    )
    rows: list[tuple[float, ...]] = []
    for row_index, sample in enumerate(raw_samples):
        chi2 = float(np.sum((sample - means) ** 2))
        minuslogpost = 1.0 + 0.5 * chi2
        weight = 1.0 + float(row_index % 3 == 0)
        row = (
            weight,
            minuslogpost,
            *[float(value) for value in sample],
            0.0,
            0.0,
            chi2,
            chi2,
        )
        rows.append(row)
    if chain_count == 1:
        return [rows]
    midpoint = len(rows) // 2
    return [rows[:midpoint], rows[midpoint:]]


def write_chain_file(
    path: Path,
    *,
    sampled_symbols: tuple[str, ...],
    nuisance_symbols: tuple[str, ...],
    rows: list[tuple[float, ...]],
) -> None:
    parameter_columns = list(sampled_symbols + nuisance_symbols)
    header = (
        "#        weight    minuslogpost"
        + "".join(f"{name:>16}" for name in parameter_columns)
        + "   minuslogprior minuslogprior__0            chi2      chi2__mock_like\n"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(header)
        for row in rows:
            handle.write(" ".join(f"{value: .8f}" for value in row) + "\n")


def write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_yaml(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
