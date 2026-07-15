"""Shared interfaces for pure likelihood implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
ParameterValues = Mapping[str, float]


class HubbleRateProvider(Protocol):
    """Protocol for models that provide H(z) in km/s/Mpc."""

    def hz(
        self,
        z: float | FloatArray,
        parameter_values: dict[str, float],
    ) -> float | FloatArray:
        """Return H(z) predictions in km/s/Mpc at the requested redshifts."""
