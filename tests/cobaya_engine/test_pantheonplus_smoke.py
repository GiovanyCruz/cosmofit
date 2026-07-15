"""Optional real-data smoke test for the generic background Theory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cobaya.likelihoods.sn.pantheonplus import PantheonPlus
from cobaya.tools import resolve_packages_path

from cosmofit.application import (
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    SupernovaDatasetConfig,
    UniformPriorConfig,
)
from cosmofit.cobaya_engine.runner import run_in_subprocess


def test_pantheonplus_smoke_run_with_generic_theory(tmp_path: Path) -> None:
    packages_path = resolve_packages_path()
    if not packages_path or not PantheonPlus.is_installed(
        path=packages_path,
        data=True,
        show_error=False,
    ):
        pytest.skip(
            "Pantheon+ data package is not installed. Install it with: "
            "cobaya-install sn.pantheonplus"
        )

    run_directory = tmp_path / _timestamped_label()
    run_config = RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression="H0*sqrt(Om*(1+z)**3 + 1-Om)",
            allowed_functions=("sqrt",),
        ),
        parameters=(
            ParameterConfig(
                name="H0",
                symbol="H0",
                role="fixed",
                unit="km/s/Mpc",
                value=70.0,
            ),
            ParameterConfig(
                name="Om",
                symbol="Om",
                role="sampled",
                prior=UniformPriorConfig(minimum=0.05, maximum=0.6),
                reference=0.3,
                proposal=0.02,
            ),
        ),
        datasets=(SupernovaDatasetConfig(kind="sn.pantheonplus"),),
        sampler=SamplerConfig(
            kind="cobaya_mcmc",
            seed=20260715,
            max_samples=4,
            burn_in=0,
            learn_proposal=False,
            Rminus1_stop=5.0,
            Rminus1_cl_stop=5.0,
        ),
        runtime=RuntimeConfig(
            run_label=run_directory.name,
            output_directory=run_directory,
        ),
    )

    result = run_in_subprocess(run_config)

    assert result.return_code == 0
    assert result.artifacts.cobaya_input_path.is_file()
    assert result.artifacts.updated_cobaya_input_path.is_file()
    assert result.artifacts.summary_path.is_file()
    with result.artifacts.status_path.open(encoding="utf-8") as handle:
        status = json.load(handle)
    assert status["state"] == "succeeded"


def _timestamped_label() -> str:
    return "smoke-pantheonplus-" + datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
