"""Cobaya external likelihood class for milestone-1 cosmic chronometers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from cobaya.likelihood import Likelihood

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
    build_background_model,
    build_cosmic_chronometers_likelihood,
)
from cosmofit.cosmology.validators import NumericalValidationError
from cosmofit.likelihoods.datasets import DatasetValidationError

INVALID_POINT_FRAGMENTS = (
    "real values",
    "finite values",
    "strictly positive",
)


@dataclass(frozen=True)
class _LikelihoodBundle:
    background_model: Any
    likelihood: Any
    sampled_symbols: tuple[str, ...]


class CosmicChronometersCobayaLikelihood(Likelihood):
    """Cobaya-facing adapter that reuses the existing pure likelihood implementation."""

    model_expression: str
    model_expression_unit: str
    model_redshift_symbol: str
    model_allowed_functions: list[str]
    parameter_definitions: list[dict[str, Any]]
    dataset_path: str
    dataset_name: str

    def initialize_with_params(self) -> None:
        run_config = _build_run_config_from_options(
            model_expression=self.model_expression,
            model_expression_unit=self.model_expression_unit,
            model_redshift_symbol=self.model_redshift_symbol,
            model_allowed_functions=tuple(self.model_allowed_functions),
            parameter_definitions=self.parameter_definitions,
            dataset_path=Path(self.dataset_path),
            dataset_name=self.dataset_name,
        )
        bundle = _LikelihoodBundle(
            background_model=build_background_model(run_config),
            likelihood=build_cosmic_chronometers_likelihood(run_config.dataset),
            sampled_symbols=tuple(
                parameter.symbol
                for parameter in run_config.parameters
                if parameter.role == "sampled"
            ),
        )
        self._bundle = bundle

    def logp(self, **params_values: float) -> float:
        parameter_values: dict[str, float] = {}
        for symbol in self._bundle.sampled_symbols:
            parameter_values[symbol] = float(params_values[symbol])

        try:
            return float(
                self._bundle.likelihood.loglike(
                    self._bundle.background_model,
                    parameter_values,
                )
            )
        except NumericalValidationError:
            return -np.inf
        except DatasetValidationError as exc:
            if any(fragment in str(exc) for fragment in INVALID_POINT_FRAGMENTS):
                return -np.inf
            raise


def _build_run_config_from_options(
    *,
    model_expression: str,
    model_expression_unit: str,
    model_redshift_symbol: str,
    model_allowed_functions: tuple[str, ...],
    parameter_definitions: list[dict[str, Any]],
    dataset_path: Path,
    dataset_name: str,
) -> RunConfig:
    parameters = tuple(_deserialize_parameter(item) for item in parameter_definitions)
    return RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=model_expression,
            expression_unit=model_expression_unit,
            redshift_symbol=model_redshift_symbol,
            allowed_functions=model_allowed_functions,
        ),
        parameters=parameters,
        dataset=CosmicChronometerDatasetConfig(
            kind="cosmic_chronometers",
            data_path=dataset_path,
            name=dataset_name,
        ),
        sampler=SamplerConfig(kind="cobaya_mcmc", seed=0),
        runtime=RuntimeConfig(
            run_label="external-likelihood",
            output_directory=Path("."),
            overwrite=False,
        ),
    )


def _deserialize_parameter(item: dict[str, Any]) -> ParameterConfig:
    prior = item.get("prior")
    return ParameterConfig(
        name=item["name"],
        symbol=item["symbol"],
        role=item["role"],
        unit=item.get("unit"),
        value=item.get("value"),
        prior=(
            UniformPriorConfig(
                minimum=prior["minimum"],
                maximum=prior["maximum"],
            )
            if prior is not None
            else None
        ),
        reference=item.get("reference"),
        proposal=item.get("proposal"),
    )
