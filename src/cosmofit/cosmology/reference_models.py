"""Reference background models for cosmology tests and examples."""

from __future__ import annotations

from cosmofit.cosmology.models import (
    BackgroundModel,
    PriorBounds,
    ProposalWidth,
    ReferenceValue,
    SampledParameter,
)

FLAT_LCDM_EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"


def flat_lcdm_example() -> BackgroundModel:
    """Return the milestone-1 flat LCDM H(z) example model."""
    return BackgroundModel(
        expression=FLAT_LCDM_EXPRESSION,
        parameters=(
            SampledParameter(
                name="H0",
                prior=PriorBounds(minimum=50.0, maximum=90.0),
                reference=ReferenceValue(67.4),
                proposal_width=ProposalWidth(1.0),
                unit="km/s/Mpc",
            ),
            SampledParameter(
                name="Om",
                prior=PriorBounds(minimum=0.0, maximum=1.0),
                reference=ReferenceValue(0.315),
                proposal_width=ProposalWidth(0.02),
                unit=None,
            ),
        ),
    )
