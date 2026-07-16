"""Deterministic completed-run fixtures for analysis and UI tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

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


def build_chain_rows(
    *,
    sampled_symbols: tuple[str, ...],
    nuisance_symbols: tuple[str, ...],
    chain_count: int,
) -> list[list[list[float]]]:
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
        return [list(rows)]
    midpoint = len(rows) // 2
    return [list(rows[:midpoint]), list(rows[midpoint:])]


def write_chain_file(
    path: Path,
    *,
    sampled_symbols: tuple[str, ...],
    nuisance_symbols: tuple[str, ...],
    rows: list[list[float]],
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


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def corrupt_chain_file(path: Path) -> None:
    path.write_text("# broken chain\nnot-a-number\n", encoding="utf-8")
