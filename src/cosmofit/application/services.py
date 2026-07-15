"""Builders that connect validated run configuration to pure scientific objects."""

from __future__ import annotations

from dataclasses import replace

from cosmofit.application.config_models import (
    CosmicChronometerDatasetConfig,
    ParameterConfig,
    RunConfig,
)
from cosmofit.cosmology import (
    BackgroundModel,
    FixedParameter,
    PriorBounds,
    ProposalWidth,
    ReferenceValue,
    SampledParameter,
)
from cosmofit.likelihoods import (
    CosmicChronometersLikelihood,
    load_cosmic_chronometers_csv,
)


def resolve_run_config(run_config: RunConfig) -> RunConfig:
    """Return a copy with filesystem paths resolved to absolute paths."""

    return replace(
        run_config,
        dataset=replace(
            run_config.dataset,
            data_path=run_config.dataset.data_path.resolve(),
        ),
        runtime=replace(
            run_config.runtime,
            output_directory=run_config.runtime.output_directory.resolve(),
        ),
    )


def build_background_model(run_config: RunConfig) -> BackgroundModel:
    """Build the validated scientific background model for a run."""

    return BackgroundModel(
        expression=run_config.model.expression,
        parameters=tuple(
            _build_domain_parameter(parameter) for parameter in run_config.parameters
        ),
        redshift_symbol=run_config.model.redshift_symbol,
        allowed_functions=run_config.model.allowed_functions,
    )


def build_cosmic_chronometers_likelihood(
    dataset_config: CosmicChronometerDatasetConfig,
) -> CosmicChronometersLikelihood:
    """Load the selected cosmic chronometer dataset as a pure likelihood."""

    dataset = load_cosmic_chronometers_csv(
        dataset_config.data_path,
        name=dataset_config.name,
    )
    return CosmicChronometersLikelihood(dataset)


def _build_domain_parameter(
    parameter: ParameterConfig,
) -> FixedParameter | SampledParameter:
    if parameter.role == "fixed":
        assert parameter.value is not None
        return FixedParameter(
            name=parameter.symbol,
            value=parameter.value,
            unit=parameter.unit,
        )

    assert parameter.prior is not None
    assert parameter.reference is not None
    assert parameter.proposal is not None
    return SampledParameter(
        name=parameter.symbol,
        prior=PriorBounds(
            minimum=parameter.prior.minimum,
            maximum=parameter.prior.maximum,
        ),
        reference=ReferenceValue(parameter.reference),
        proposal_width=ProposalWidth(parameter.proposal),
        unit=parameter.unit,
    )
