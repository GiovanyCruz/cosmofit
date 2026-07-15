"""Validated application-level configuration models for Cobaya runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from cosmofit.cosmology import ALLOWED_FUNCTIONS
from cosmofit.cosmology.validators import ParameterDefinitionError


@dataclass(frozen=True)
class UniformPriorConfig:
    """Uniform prior bounds for a sampled parameter."""

    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if self.minimum >= self.maximum:
            raise ParameterDefinitionError(
                "Uniform prior minimum must be smaller than maximum."
            )


@dataclass(frozen=True)
class ParameterConfig:
    """Application-facing cosmological parameter configuration."""

    name: str
    symbol: str
    role: Literal["fixed", "sampled"]
    unit: str | None = None
    value: float | None = None
    prior: UniformPriorConfig | None = None
    reference: float | None = None
    proposal: float | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ParameterDefinitionError("Parameter name must not be empty.")
        if not self.symbol.isidentifier():
            raise ParameterDefinitionError(
                f"Parameter symbol '{self.symbol}' must be a valid identifier."
            )
        if self.symbol == "z":
            raise ParameterDefinitionError("Parameter symbol 'z' is reserved.")
        if self.symbol in ALLOWED_FUNCTIONS:
            raise ParameterDefinitionError(
                f"Parameter symbol '{self.symbol}' conflicts with an allowed function."
            )

        if self.role == "fixed":
            if self.value is None:
                raise ParameterDefinitionError(
                    f"Fixed parameter '{self.name}' requires a value."
                )
            if self.prior is not None or self.proposal is not None:
                raise ParameterDefinitionError(
                    f"Fixed parameter '{self.name}' must not define prior or proposal."
                )
            return

        if self.prior is None:
            raise ParameterDefinitionError(
                f"Sampled parameter '{self.name}' requires a prior."
            )
        if self.reference is None:
            raise ParameterDefinitionError(
                f"Sampled parameter '{self.name}' requires a reference value."
            )
        if self.proposal is None or self.proposal <= 0.0:
            raise ParameterDefinitionError(
                f"Sampled parameter '{self.name}' requires "
                "a strictly positive proposal."
            )
        if not (self.prior.minimum <= self.reference <= self.prior.maximum):
            raise ParameterDefinitionError(
                f"Reference value for '{self.name}' must lie within the prior bounds."
            )


@dataclass(frozen=True)
class ModelConfig:
    """Validated H(z) model configuration for milestone 1."""

    kind: Literal["hz_expression_flat"]
    expression: str
    expression_unit: Literal["km/s/Mpc"] = "km/s/Mpc"
    redshift_symbol: Literal["z"] = "z"
    allowed_functions: tuple[str, ...] = ALLOWED_FUNCTIONS

    def __post_init__(self) -> None:
        if self.kind != "hz_expression_flat":
            raise ParameterDefinitionError(
                "Milestone 1 supports only kind='hz_expression_flat'."
            )
        if self.expression_unit != "km/s/Mpc":
            raise ParameterDefinitionError(
                "Milestone 1 requires expression_unit='km/s/Mpc'."
            )
        if self.redshift_symbol != "z":
            raise ParameterDefinitionError("Milestone 1 reserves redshift symbol 'z'.")
        if not self.expression.strip():
            raise ParameterDefinitionError("Model expression must not be empty.")


@dataclass(frozen=True)
class CosmicChronometerDatasetConfig:
    """Dataset selection for the milestone-1 cosmic chronometer likelihood."""

    kind: Literal["cosmic_chronometers"]
    data_path: Path
    name: str = "cosmic_chronometers"

    def __post_init__(self) -> None:
        if self.kind != "cosmic_chronometers":
            raise ParameterDefinitionError(
                "Milestone 1 supports only kind='cosmic_chronometers'."
            )


@dataclass(frozen=True)
class SamplerConfig:
    """Sampler settings for Cobaya MCMC runs."""

    kind: Literal["cobaya_mcmc"]
    seed: int
    max_samples: int | None = None
    burn_in: int | None = 0
    learn_proposal: bool = False
    Rminus1_stop: float | None = None
    Rminus1_cl_stop: float | None = None

    def __post_init__(self) -> None:
        if self.kind != "cobaya_mcmc":
            raise ParameterDefinitionError(
                "Milestone 1 supports only kind='cobaya_mcmc'."
            )
        if self.seed < 0:
            raise ParameterDefinitionError("Sampler seed must be non-negative.")
        if self.max_samples is not None and self.max_samples <= 0:
            raise ParameterDefinitionError("max_samples must be strictly positive.")
        if self.burn_in is not None and self.burn_in < 0:
            raise ParameterDefinitionError("burn_in must be non-negative.")
        if self.Rminus1_stop is not None and self.Rminus1_stop <= 0.0:
            raise ParameterDefinitionError("Rminus1_stop must be strictly positive.")
        if self.Rminus1_cl_stop is not None and self.Rminus1_cl_stop <= 0.0:
            raise ParameterDefinitionError(
                "Rminus1_cl_stop must be strictly positive."
            )


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime settings for artifact management."""

    run_label: str
    output_directory: Path
    overwrite: bool = False

    def __post_init__(self) -> None:
        if not self.run_label.strip():
            raise ParameterDefinitionError("Run label must not be empty.")


@dataclass(frozen=True)
class RunConfig:
    """Validated top-level configuration for a Cobaya run."""

    schema_version: int
    model: ModelConfig
    parameters: tuple[ParameterConfig, ...]
    dataset: CosmicChronometerDatasetConfig
    sampler: SamplerConfig
    runtime: RuntimeConfig

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ParameterDefinitionError("Milestone 1 requires schema_version=1.")
        if not self.parameters:
            raise ParameterDefinitionError(
                "At least one cosmological parameter is required."
            )

        names = [parameter.name for parameter in self.parameters]
        symbols = [parameter.symbol for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ParameterDefinitionError("Parameter names must be unique.")
        if len(symbols) != len(set(symbols)):
            raise ParameterDefinitionError("Parameter symbols must be unique.")


def serialize_run_config(run_config: RunConfig) -> dict[str, Any]:
    """Convert a run configuration into JSON/YAML-safe primitives."""

    return _serialize_value(asdict(run_config))


def deserialize_run_config(data: dict[str, Any]) -> RunConfig:
    """Reconstruct a run configuration from serialized primitives."""

    parameters = tuple(
        ParameterConfig(
            name=item["name"],
            symbol=item["symbol"],
            role=item["role"],
            unit=item.get("unit"),
            value=item.get("value"),
            prior=(
                UniformPriorConfig(
                    minimum=item["prior"]["minimum"],
                    maximum=item["prior"]["maximum"],
                )
                if item.get("prior") is not None
                else None
            ),
            reference=item.get("reference"),
            proposal=item.get("proposal"),
        )
        for item in data["parameters"]
    )
    return RunConfig(
        schema_version=data["schema_version"],
        model=ModelConfig(
            kind=data["model"]["kind"],
            expression=data["model"]["expression"],
            expression_unit=data["model"]["expression_unit"],
            redshift_symbol=data["model"]["redshift_symbol"],
            allowed_functions=tuple(data["model"]["allowed_functions"]),
        ),
        parameters=parameters,
        dataset=CosmicChronometerDatasetConfig(
            kind=data["dataset"]["kind"],
            data_path=Path(data["dataset"]["data_path"]),
            name=data["dataset"]["name"],
        ),
        sampler=SamplerConfig(
            kind=data["sampler"]["kind"],
            seed=data["sampler"]["seed"],
            max_samples=data["sampler"].get("max_samples"),
            burn_in=data["sampler"].get("burn_in"),
            learn_proposal=data["sampler"]["learn_proposal"],
            Rminus1_stop=data["sampler"].get("Rminus1_stop"),
            Rminus1_cl_stop=data["sampler"].get("Rminus1_cl_stop"),
        ),
        runtime=RuntimeConfig(
            run_label=data["runtime"]["run_label"],
            output_directory=Path(data["runtime"]["output_directory"]),
            overwrite=data["runtime"]["overwrite"],
        ),
    )


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value
