"""Application-layer configuration models and builders for CosmoFit."""

from __future__ import annotations

from importlib import import_module

from cosmofit.application.config_models import (
    SUPPORTED_SUPERNOVA_DATASETS,
    CosmicChronometerDatasetConfig,
    DatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    SupernovaDatasetConfig,
    UniformPriorConfig,
    deserialize_run_config,
    serialize_run_config,
)
from cosmofit.application.examples import (
    LCDM_EXPRESSION,
    build_lcdm_example_run_config,
    default_cosmic_chronometer_path,
)
from cosmofit.application.execution import (
    PreparedRunExecution,
    WorkerRequest,
    cleanup_worker_request,
    load_worker_request,
    prepare_worker_request,
    validate_run_config_for_execution,
)
from cosmofit.application.runtime_info import get_cobaya_packages_path
from cosmofit.application.services import (
    build_background_model,
    build_cosmic_chronometers_likelihood,
    resolve_run_config,
)
from cosmofit.cosmology import ALLOWED_FUNCTIONS

__all__ = [
    "ALLOWED_FUNCTIONS",
    "CosmicChronometerDatasetConfig",
    "DatasetConfig",
    "LCDM_EXPRESSION",
    "ModelConfig",
    "ParameterConfig",
    "PreparedRunExecution",
    "PlotKind",
    "PosteriorPlotArtifact",
    "PosteriorPlotRequest",
    "PosteriorResultsLoadOptions",
    "PosteriorResultsService",
    "RunConfig",
    "RuntimeConfig",
    "SamplerConfig",
    "SummaryExportArtifact",
    "SupernovaDatasetConfig",
    "SUPPORTED_SUPERNOVA_DATASETS",
    "UniformPriorConfig",
    "WorkerRequest",
    "build_lcdm_example_run_config",
    "build_background_model",
    "build_cosmic_chronometers_likelihood",
    "cleanup_worker_request",
    "default_cosmic_chronometer_path",
    "deserialize_run_config",
    "get_cobaya_packages_path",
    "load_worker_request",
    "LoadedPosteriorResults",
    "MathTextPreview",
    "MathTextService",
    "prepare_worker_request",
    "resolve_run_config",
    "serialize_run_config",
    "validate_run_config_for_execution",
]


def __getattr__(name: str) -> object:
    if name in {
        "LoadedPosteriorResults",
        "MathTextPreview",
        "MathTextService",
        "PlotKind",
        "PosteriorPlotArtifact",
        "PosteriorPlotRequest",
        "PosteriorResultsLoadOptions",
        "SummaryExportArtifact",
    }:
        if name in {"MathTextPreview", "MathTextService"}:
            module = import_module("cosmofit.application.mathtext_service")
        else:
            module = import_module("cosmofit.application.posterior_results_models")
        return getattr(module, name)
    if name == "PosteriorResultsService":
        module = import_module("cosmofit.application.posterior_results_service")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
