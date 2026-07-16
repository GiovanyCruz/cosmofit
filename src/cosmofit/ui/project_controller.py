"""Controller helpers for building and validating UI project state."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    DatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    SupernovaDatasetConfig,
    UniformPriorConfig,
    build_background_model,
    build_cosmic_chronometers_likelihood,
    build_lcdm_example_run_config,
    default_cosmic_chronometer_path,
    deserialize_run_config,
    get_cobaya_packages_path,
    serialize_run_config,
)


class ProjectError(ValueError):
    """Base project controller error."""


class ProjectFileError(ProjectError):
    """Raised when a project file cannot be loaded safely."""


@dataclass(frozen=True)
class ValidationResult:
    """Validated run configuration and a human-readable success message."""

    run_config: RunConfig
    summary: str


class ProjectController:
    """Convert UI state into validated backend configuration models."""

    def default_state(self) -> dict[str, Any]:
        return {
            "model": {
                "model_name": "hz_expression_flat",
                "expression": "",
                "preview_min": "0.0",
                "preview_max": "2.0",
            },
            "parameters": [
                {
                    "name": "",
                    "label": "",
                    "role": "sampled",
                    "prior_min": "",
                    "prior_max": "",
                    "reference": "",
                    "proposal": "",
                    "fixed_value": "",
                    "unit": "",
                    "nuisance": False,
                }
            ],
            "datasets": {
                "cosmic_chronometers_selected": False,
                "cosmic_chronometers_path": "",
                "sn.pantheonplus": False,
                "sn.pantheonplusshoes": False,
                "sn.union3": False,
            },
            "sampler": {
                "sampler_kind": "cobaya_mcmc",
                "run_label": "ui-run",
                "output_directory": "outputs/ui-run",
                "seed": "1234",
                "max_samples": "",
                "burn_in": "0",
                "Rminus1_stop": "",
                "Rminus1_cl_stop": "",
                "learn_proposal": False,
                "overwrite": False,
            },
        }

    def lcdm_example_state(self) -> dict[str, Any]:
        return self._run_config_to_state(
            build_lcdm_example_run_config(output_directory=Path("outputs/lcdm-example"))
        )

    def cobaya_packages_path(self) -> Path | None:
        return get_cobaya_packages_path()

    def validate_model(self, state: dict[str, Any]) -> ValidationResult:
        model = self._build_model_config(state["model"])
        parameters = self._build_parameter_configs(state["parameters"])
        run_config = RunConfig(
            schema_version=1,
            model=model,
            parameters=parameters,
            datasets=(
                CosmicChronometerDatasetConfig(
                    kind="cosmic_chronometers",
                    data_path=default_cosmic_chronometer_path(),
                    name="synthetic-cc",
                ),
            ),
            sampler=SamplerConfig(kind="cobaya_mcmc", seed=1),
            runtime=RuntimeConfig(
                run_label="model-validation",
                output_directory=Path("outputs/model-validation"),
                overwrite=False,
            ),
        )
        build_background_model(run_config)
        return ValidationResult(
            run_config=run_config,
            summary="El modelo H(z) es valido para los parametros actuales.",
        )

    def validate_configuration(self, state: dict[str, Any]) -> ValidationResult:
        run_config = self.build_run_config(state)
        build_background_model(run_config)
        for dataset in run_config.datasets:
            if isinstance(dataset, CosmicChronometerDatasetConfig):
                build_cosmic_chronometers_likelihood(dataset)
        return ValidationResult(
            run_config=run_config,
            summary="La configuracion es valida y esta lista para el siguiente hito.",
        )

    def build_run_config(self, state: dict[str, Any]) -> RunConfig:
        return RunConfig(
            schema_version=1,
            model=self._build_model_config(state["model"]),
            parameters=self._build_parameter_configs(state["parameters"]),
            datasets=self._build_dataset_configs(state["datasets"]),
            sampler=self._build_sampler_config(state["sampler"]),
            runtime=self._build_runtime_config(state["sampler"]),
        )

    def save_project(self, path: Path, state: dict[str, Any]) -> RunConfig:
        run_config = self.build_run_config(state)
        payload = serialize_run_config(run_config)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        return run_config

    def load_project(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError as error:
            raise ProjectFileError(
                "El archivo del proyecto no contiene JSON valido."
            ) from error
        except OSError as error:
            raise ProjectFileError(
                "No se pudo leer el archivo del proyecto."
            ) from error

        if not isinstance(data, dict):
            raise ProjectFileError(
                "El archivo del proyecto debe contener un objeto JSON."
            )

        try:
            run_config = deserialize_run_config(data)
        except (KeyError, TypeError, ValueError) as error:
            raise ProjectFileError(
                "El archivo del proyecto no coincide con el formato "
                "normalizado de CosmoFit."
            ) from error
        return self._run_config_to_state(run_config)

    def _build_model_config(self, model_state: dict[str, Any]) -> ModelConfig:
        return ModelConfig(
            kind="hz_expression_flat",
            expression=self._require_text(
                model_state.get("expression", ""),
                message="Debes escribir una expresion H(z).",
            ),
        )

    def _build_parameter_configs(
        self, parameter_rows: list[dict[str, Any]]
    ) -> tuple[ParameterConfig, ...]:
        if not parameter_rows:
            raise ProjectError("Debes definir al menos un parametro cosmologico.")

        symbols = [
            self._require_text(
                row.get("name", ""),
                message="Cada parametro necesita un nombre interno.",
            )
            for row in parameter_rows
        ]
        if len(symbols) != len(set(symbols)):
            raise ProjectError("Los nombres de los parametros deben ser unicos.")

        parameters: list[ParameterConfig] = []
        for row in parameter_rows:
            symbol = self._require_text(
                row.get("name", ""),
                message="Cada parametro necesita un nombre interno.",
            )
            display_name = self._optional_text(row.get("label")) or symbol
            role = row.get("role", "sampled")
            unit = self._optional_text(row.get("unit"))
            if role == "fixed":
                parameters.append(
                    ParameterConfig(
                        name=display_name,
                        symbol=symbol,
                        role="fixed",
                        unit=unit,
                        value=self._parse_float(
                            row.get("fixed_value", ""),
                            message=(
                                f"El parametro fijo '{symbol}' necesita "
                                "un valor numerico."
                            ),
                        ),
                    )
                )
                continue

            parameters.append(
                ParameterConfig(
                    name=display_name,
                    symbol=symbol,
                    role="sampled",
                    unit=unit,
                    prior=UniformPriorConfig(
                        minimum=self._parse_float(
                            row.get("prior_min", ""),
                            message=(
                                f"El parametro muestreado '{symbol}' necesita "
                                "un prior minimo."
                            ),
                        ),
                        maximum=self._parse_float(
                            row.get("prior_max", ""),
                            message=(
                                f"El parametro muestreado '{symbol}' necesita "
                                "un prior maximo."
                            ),
                        ),
                    ),
                    reference=self._parse_float(
                        row.get("reference", ""),
                        message=(
                            f"El parametro muestreado '{symbol}' necesita "
                            "un valor de referencia."
                        ),
                    ),
                    proposal=self._parse_float(
                        row.get("proposal", ""),
                        message=(
                            f"El parametro muestreado '{symbol}' necesita "
                            "una propuesta numerica."
                        ),
                    ),
                )
            )

        return tuple(parameters)

    def _build_dataset_configs(
        self, dataset_state: dict[str, Any]
    ) -> tuple[DatasetConfig, ...]:
        datasets: list[DatasetConfig] = []
        if dataset_state.get("cosmic_chronometers_selected", False):
            data_path = Path(
                self._require_text(
                    dataset_state.get("cosmic_chronometers_path", ""),
                    message=(
                        "Debes seleccionar un archivo CSV para cronometros cosmicos."
                    ),
                )
            )
            datasets.append(
                CosmicChronometerDatasetConfig(
                    kind="cosmic_chronometers",
                    data_path=data_path,
                    name="cosmic_chronometers",
                )
            )

        selected_supernovae = [
            name
            for name in (
                "sn.pantheonplus",
                "sn.pantheonplusshoes",
                "sn.union3",
            )
            if dataset_state.get(name, False)
        ]
        if len(selected_supernovae) > 1:
            raise ProjectError(
                "Solo puedes seleccionar un conjunto de supernovas "
                "por defecto para evitar solapamientos."
            )
        if selected_supernovae:
            datasets.append(
                SupernovaDatasetConfig(
                    kind=selected_supernovae[0],
                    use_absolute_magnitude=False,
                )
            )

        return tuple(datasets)

    def _build_sampler_config(self, sampler_state: dict[str, Any]) -> SamplerConfig:
        return SamplerConfig(
            kind="cobaya_mcmc",
            seed=self._parse_int(
                sampler_state.get("seed", ""),
                message="La semilla aleatoria debe ser un entero no negativo.",
            ),
            max_samples=self._parse_optional_int(
                sampler_state.get("max_samples", ""),
                message="El maximo de muestras debe ser un entero positivo.",
            ),
            burn_in=self._parse_optional_int(
                sampler_state.get("burn_in", ""),
                message="El burn in debe ser un entero no negativo.",
                allow_zero=True,
            ),
            learn_proposal=bool(sampler_state.get("learn_proposal", False)),
            Rminus1_stop=self._parse_optional_float(
                sampler_state.get("Rminus1_stop", ""),
                message="Rminus1_stop debe ser un numero positivo.",
            ),
            Rminus1_cl_stop=self._parse_optional_float(
                sampler_state.get("Rminus1_cl_stop", ""),
                message="Rminus1_cl_stop debe ser un numero positivo.",
            ),
        )

    def _build_runtime_config(self, sampler_state: dict[str, Any]) -> RuntimeConfig:
        return RuntimeConfig(
            run_label=self._require_text(
                sampler_state.get("run_label", ""),
                message="El identificador de la corrida no puede estar vacio.",
            ),
            output_directory=Path(
                self._require_text(
                    sampler_state.get("output_directory", ""),
                    message="Debes seleccionar un directorio de salida.",
                )
            ),
            overwrite=bool(sampler_state.get("overwrite", False)),
        )

    def _run_config_to_state(self, run_config: RunConfig) -> dict[str, Any]:
        dataset_lookup = {dataset.kind: dataset for dataset in run_config.datasets}
        chronometers = dataset_lookup.get("cosmic_chronometers")
        return {
            "model": {
                "model_name": "hz_expression_flat",
                "expression": run_config.model.expression,
                "preview_min": "0.0",
                "preview_max": "2.0",
            },
            "parameters": [
                {
                    "name": parameter.symbol,
                    "label": parameter.name,
                    "role": parameter.role,
                    "prior_min": (
                        "" if parameter.prior is None else str(parameter.prior.minimum)
                    ),
                    "prior_max": (
                        "" if parameter.prior is None else str(parameter.prior.maximum)
                    ),
                    "reference": (
                        "" if parameter.reference is None else str(parameter.reference)
                    ),
                    "proposal": (
                        "" if parameter.proposal is None else str(parameter.proposal)
                    ),
                    "fixed_value": (
                        "" if parameter.value is None else str(parameter.value)
                    ),
                    "unit": parameter.unit or "",
                    "nuisance": False,
                }
                for parameter in run_config.parameters
            ],
            "datasets": {
                "cosmic_chronometers_selected": chronometers is not None,
                "cosmic_chronometers_path": (
                    ""
                    if chronometers is None
                    else str(chronometers.data_path)
                ),
                "sn.pantheonplus": "sn.pantheonplus" in dataset_lookup,
                "sn.pantheonplusshoes": "sn.pantheonplusshoes" in dataset_lookup,
                "sn.union3": "sn.union3" in dataset_lookup,
            },
            "sampler": {
                "sampler_kind": "cobaya_mcmc",
                "run_label": run_config.runtime.run_label,
                "output_directory": str(run_config.runtime.output_directory),
                "seed": str(run_config.sampler.seed),
                "max_samples": (
                    ""
                    if run_config.sampler.max_samples is None
                    else str(run_config.sampler.max_samples)
                ),
                "burn_in": (
                    ""
                    if run_config.sampler.burn_in is None
                    else str(run_config.sampler.burn_in)
                ),
                "Rminus1_stop": (
                    ""
                    if run_config.sampler.Rminus1_stop is None
                    else str(run_config.sampler.Rminus1_stop)
                ),
                "Rminus1_cl_stop": (
                    ""
                    if run_config.sampler.Rminus1_cl_stop is None
                    else str(run_config.sampler.Rminus1_cl_stop)
                ),
                "learn_proposal": run_config.sampler.learn_proposal,
                "overwrite": run_config.runtime.overwrite,
            },
        }

    def _require_text(self, value: Any, *, message: str) -> str:
        text = str(value).strip()
        if not text:
            raise ProjectError(message)
        return text

    def _optional_text(self, value: Any) -> str | None:
        text = str(value).strip()
        return text or None

    def _parse_float(self, value: Any, *, message: str) -> float:
        text = self._require_text(value, message=message)
        try:
            return float(text)
        except ValueError as error:
            raise ProjectError(message) from error

    def _parse_optional_float(self, value: Any, *, message: str) -> float | None:
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as error:
            raise ProjectError(message) from error

    def _parse_int(self, value: Any, *, message: str) -> int:
        text = self._require_text(value, message=message)
        try:
            return int(text)
        except ValueError as error:
            raise ProjectError(message) from error

    def _parse_optional_int(
        self,
        value: Any,
        *,
        message: str,
        allow_zero: bool = False,
    ) -> int | None:
        text = str(value).strip()
        if not text:
            return None
        try:
            integer = int(text)
        except ValueError as error:
            raise ProjectError(message) from error
        if integer == 0 and allow_zero:
            return 0
        if integer <= 0:
            raise ProjectError(message)
        return integer
