"""Integration tests for the minimal Cobaya smoke path."""

from __future__ import annotations

import json
from pathlib import Path

from cosmofit.cobaya_engine.smoke_run import main


def test_smoke_run_creates_artifacts_and_succeeds(tmp_path: Path) -> None:
    output_root = tmp_path / "smoke"

    exit_code = main(["--output-root", str(output_root)])

    assert exit_code == 0
    run_directories = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_directories) == 1
    run_directory = run_directories[0]
    assert (run_directory / "input.yaml").is_file()
    assert (run_directory / "normalized_config.json").is_file()
    assert (run_directory / "cobaya_input.yaml").is_file()
    assert (run_directory / "updated_cobaya_input.yaml").is_file()
    assert (run_directory / "summary.json").is_file()
    assert list(run_directory.rglob("*.py")) == []

    with (run_directory / "status.json").open(encoding="utf-8") as handle:
        status = json.load(handle)
    assert status["state"] == "succeeded"
