"""Integration smoke test for the GetDist analysis utility."""

from __future__ import annotations

from pathlib import Path

from cosmofit.analysis.smoke_run import main as analysis_smoke_main
from cosmofit.cobaya_engine.smoke_run import main as cobaya_smoke_main


def test_analysis_smoke_run_on_completed_cobaya_run(tmp_path: Path) -> None:
    output_root = tmp_path / "smoke"

    cobaya_exit_code = cobaya_smoke_main(["--output-root", str(output_root)])

    assert cobaya_exit_code == 0
    run_directory = next(path for path in output_root.iterdir() if path.is_dir())
    analysis_exit_code = analysis_smoke_main(
        [str(run_directory), "--parameters", "H0,Om"]
    )

    assert analysis_exit_code == 0
    analysis_directory = run_directory / "analysis" / "getdist"
    assert (analysis_directory / "summary.json").is_file()
    assert (analysis_directory / "summary.csv").is_file()
    assert (analysis_directory / "plots" / "1d_H0.png").is_file()
    assert (analysis_directory / "plots" / "1d_H0.pdf").is_file()
    assert (analysis_directory / "plots" / "triangle_H0_Om.png").is_file()
    assert (analysis_directory / "plots" / "triangle_H0_Om.pdf").is_file()
