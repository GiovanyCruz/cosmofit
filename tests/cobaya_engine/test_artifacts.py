"""Tests for Cobaya run-artifact safety and layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
)
from cosmofit.cobaya_engine.artifacts import prepare_run_artifacts


def test_prepare_run_artifacts_refuses_existing_directory_without_overwrite(
    tmp_path: Path,
) -> None:
    run_directory = tmp_path / "existing-run"
    run_directory.mkdir()
    run_config = _run_config(run_directory, overwrite=False)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        prepare_run_artifacts(run_config)


def test_prepare_run_artifacts_creates_expected_directories(tmp_path: Path) -> None:
    run_directory = tmp_path / "new-run"

    artifacts = prepare_run_artifacts(_run_config(run_directory, overwrite=False))

    assert artifacts.run_directory == run_directory
    assert artifacts.logs_directory.is_dir()
    assert artifacts.chains_directory.is_dir()


def _run_config(run_directory: Path, *, overwrite: bool) -> RunConfig:
    return RunConfig(
        schema_version=1,
        model=ModelConfig(kind="hz_expression_flat", expression="H0*(1+z)"),
        parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="sampled",
                prior=UniformPriorConfig(minimum=50.0, maximum=90.0),
                reference=70.0,
                proposal=1.0,
            ),
        ),
        dataset=CosmicChronometerDatasetConfig(
            kind="cosmic_chronometers",
            data_path=Path("tests/fixtures/cosmic_chronometers_synth.csv"),
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=7),
        runtime=RuntimeConfig(
            run_label="artifact-test",
            output_directory=run_directory,
            overwrite=overwrite,
        ),
    )
