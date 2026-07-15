"""Translate validated application configuration into Cobaya input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    RunConfig,
    SupernovaDatasetConfig,
)

LIKELIHOOD_CLASS_PATH = (
    "cosmofit.cobaya_engine.external_likelihood."
    "CosmicChronometersCobayaLikelihood"
)
THEORY_CLASS_PATH = (
    "cosmofit.cobaya_engine.background_theory."
    "GenericBackgroundTheory"
)


@dataclass(frozen=True)
class CobayaInput:
    """Executable Cobaya input plus a few convenience views."""

    info: dict[str, Any]
    sampled_symbols: tuple[str, ...]
    fixed_values: dict[str, float]


def build_cobaya_input(run_config: RunConfig) -> CobayaInput:
    """Build the Cobaya input dictionary for a validated run."""

    params_block: dict[str, dict[str, Any]] = {}
    sampled_symbols: list[str] = []
    fixed_values: dict[str, float] = {}
    all_symbols: list[str] = []
    for parameter in run_config.parameters:
        all_symbols.append(parameter.symbol)
        if parameter.role == "fixed":
            assert parameter.value is not None
            params_block[parameter.symbol] = {"value": parameter.value}
            fixed_values[parameter.symbol] = parameter.value
            continue

        assert parameter.prior is not None
        assert parameter.reference is not None
        assert parameter.proposal is not None
        params_block[parameter.symbol] = {
            "prior": {
                "min": parameter.prior.minimum,
                "max": parameter.prior.maximum,
            },
            "ref": parameter.reference,
            "proposal": parameter.proposal,
        }
        sampled_symbols.append(parameter.symbol)

    theory_options = {
        "model_expression": run_config.model.expression,
        "model_expression_unit": run_config.model.expression_unit,
        "model_redshift_symbol": run_config.model.redshift_symbol,
        "model_allowed_functions": list(run_config.model.allowed_functions),
        "parameter_definitions": [
            {
                "name": parameter.name,
                "symbol": parameter.symbol,
                "role": parameter.role,
                "unit": parameter.unit,
                "value": parameter.value,
                "prior": (
                    {
                        "minimum": parameter.prior.minimum,
                        "maximum": parameter.prior.maximum,
                    }
                    if parameter.prior is not None
                    else None
                ),
                "reference": parameter.reference,
                "proposal": parameter.proposal,
            }
            for parameter in run_config.parameters
        ],
        "input_params": all_symbols,
    }
    likelihood_block: dict[str, Any] = {}
    for dataset in run_config.datasets:
        if isinstance(dataset, CosmicChronometerDatasetConfig):
            likelihood_block[LIKELIHOOD_CLASS_PATH] = {
                "dataset_path": str(dataset.data_path),
                "dataset_name": dataset.name,
            }
        elif isinstance(dataset, SupernovaDatasetConfig):
            likelihood_block[dataset.kind] = {
                "use_abs_mag": dataset.use_absolute_magnitude,
            }
        else:
            raise AssertionError(f"Unsupported dataset type {type(dataset).__name__}.")

    sampler_options: dict[str, Any] = {
        "learn_proposal": run_config.sampler.learn_proposal,
    }
    if run_config.sampler.max_samples is not None:
        sampler_options["max_samples"] = run_config.sampler.max_samples
    if run_config.sampler.burn_in is not None:
        sampler_options["burn_in"] = run_config.sampler.burn_in
    if run_config.sampler.Rminus1_stop is not None:
        sampler_options["Rminus1_stop"] = run_config.sampler.Rminus1_stop
    if run_config.sampler.Rminus1_cl_stop is not None:
        sampler_options["Rminus1_cl_stop"] = run_config.sampler.Rminus1_cl_stop

    info = {
        "theory": {
            THEORY_CLASS_PATH: theory_options,
        },
        "likelihood": likelihood_block,
        "params": params_block,
        "sampler": {"mcmc": sampler_options},
    }
    return CobayaInput(
        info=info,
        sampled_symbols=tuple(sampled_symbols),
        fixed_values=fixed_values,
    )
