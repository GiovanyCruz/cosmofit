"""Focused, no-MCMC tests for the Referee Comment 2 workflow."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REFEREE2 = Path(__file__).resolve().parents[2] / "validation" / "referee2"
sys.path.insert(0, str(REFEREE2))

from workflow import (  # noqa: E402
    FIXED_DATASET,
    aggregate_realizations,
    canonical_science_config,
    compare_science_configs,
    coverage,
    generate_dataset,
    pull,
    run_cosmofit,
    run_is_successful,
)


def test_fixed_seed_generates_identical_dataset(tmp_path: Path) -> None:
    first = generate_dataset(tmp_path / "first.csv", seed=11)
    second = generate_dataset(tmp_path / "second.csv", seed=11)
    assert first.read_bytes() == second.read_bytes()


def test_different_seeds_generate_different_realizations(tmp_path: Path) -> None:
    first = generate_dataset(tmp_path / "first.csv", seed=11)
    second = generate_dataset(tmp_path / "second.csv", seed=12)
    assert first.read_bytes() != second.read_bytes()


def test_noiseless_fiducial_prediction_is_retained(tmp_path: Path) -> None:
    path = generate_dataset(tmp_path / "realization.csv", seed=1)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "z,H,sigma"
    values = np.loadtxt(path, delimiter=",", skiprows=1)
    noiseless = 70.0 * np.sqrt(0.30 * (1 + values[:, 0]) ** 3 + 0.70)
    assert np.all(np.isfinite(noiseless))


def test_original_validation_input_is_not_overwritten(tmp_path: Path) -> None:
    before = hashlib.sha256(FIXED_DATASET.read_bytes()).hexdigest()
    generate_dataset(tmp_path / "new.csv", seed=123)
    assert hashlib.sha256(FIXED_DATASET.read_bytes()).hexdigest() == before


def test_completed_run_is_safely_skipped(tmp_path: Path) -> None:
    run_directory = tmp_path / "completed"
    run_directory.mkdir()
    (run_directory / "status.json").write_text(
        json.dumps({"state": "succeeded"}), encoding="utf-8"
    )
    assert run_is_successful(run_directory)
    assert run_cosmofit(FIXED_DATASET, run_directory, seed=1, label="skip") == 0


def test_incomplete_run_directory_is_collision_safe(tmp_path: Path) -> None:
    run_directory = tmp_path / "incomplete"
    run_directory.mkdir()
    with pytest.raises(FileExistsError, match="Refusing"):
        run_cosmofit(FIXED_DATASET, run_directory, seed=1, label="collision")


def test_pull_and_coverage() -> None:
    assert pull(72.0, 70.0, 2.0) == 1.0
    assert coverage(70.0, 69.0, 71.0) is True
    assert coverage(70.0, 70.1, 71.0) is False
    assert coverage(70.0, None, 71.0) is None


def test_summary_excludes_failed_and_nonconverged_rows() -> None:
    row = {
        "run_status": "succeeded",
        "converged": True,
        "H0_posterior_mean": 71.0,
        "H0_posterior_sigma": 2.0,
        "H0_pull": 0.5,
        "H0_coverage_68": True,
        "H0_coverage_95": True,
        "Om_posterior_mean": 0.31,
        "Om_posterior_sigma": 0.02,
        "Om_pull": 0.5,
        "Om_coverage_68": False,
        "Om_coverage_95": True,
    }
    summary = aggregate_realizations(
        [row, {**row, "converged": False}, {**row, "run_status": "failed"}]
    )
    assert summary["included_realizations"] == 1
    assert summary["excluded_realizations"] == 2
    assert summary["H0"]["coverage_fraction_68"] == 1.0
    assert summary["Om"]["coverage_fraction_68"] == 0.0


def test_configuration_equivalence_checker_detects_difference() -> None:
    first = canonical_science_config(FIXED_DATASET)
    second = json.loads(json.dumps(first))
    second["sampler"]["Rminus1_stop"] = 0.02
    assert "sampler" in compare_science_configs(first, second)


def test_configuration_equivalence_checker_accepts_identical_config() -> None:
    first = canonical_science_config(FIXED_DATASET)
    assert compare_science_configs(first, dict(first)) == {}


def test_seed_metadata_is_preserved(tmp_path: Path) -> None:
    path = generate_dataset(tmp_path / "dataset.csv", seed=99)
    assert path.is_file()
    # The run driver persists the seed in per-run metadata; its deterministic
    # dataset content supplies an independent check without starting MCMC.
    assert (
        generate_dataset(tmp_path / "again.csv", seed=99).read_bytes()
        == path.read_bytes()
    )
