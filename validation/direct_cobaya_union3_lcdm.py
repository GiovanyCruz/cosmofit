"""Independent Cobaya validation for flat LCDM with Union3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from cobaya.run import run
from cobaya.theory import Theory
from scipy.integrate import quad

SPEED_OF_LIGHT_KM_S = 299792.458

OUTPUT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "direct_cobaya_union3_lcdm"
    / "chain"
)


class IndependentFlatLCDMTheory(Theory):
    """Independent flat-LCDM angular-diameter-distance provider."""

    def initialize(self) -> None:
        self._requested_redshifts: dict[str, np.ndarray] = {}

    def get_can_provide(self) -> list[str]:
        return ["angular_diameter_distance"]

    def must_provide(
        self,
        **requirements: Any,
    ) -> dict[str, Any]:
        if "angular_diameter_distance" in requirements:
            payload = requirements["angular_diameter_distance"]
            redshifts = np.asarray(payload["z"], dtype=float)

            if redshifts.ndim != 1:
                raise ValueError(
                    "Union3 redshifts must be one-dimensional."
                )

            self._requested_redshifts[
                "angular_diameter_distance"
            ] = redshifts

        return {}

    def calculate(
        self,
        state: dict[str, Any],
        want_derived: bool = True,
        **params_values_dict: float,
    ) -> bool:
        h0 = float(params_values_dict["H0"])
        om = float(params_values_dict["Om"])

        redshifts = self._requested_redshifts.get(
            "angular_diameter_distance"
        )

        if redshifts is None:
            raise RuntimeError(
                "No angular-diameter-distance redshifts were requested."
            )

        state["angular_diameter_distance"] = np.array(
            [
                angular_diameter_distance(
                    z=float(redshift),
                    h0=h0,
                    om=om,
                )
                for redshift in redshifts
            ],
            dtype=float,
        )

        return True

    def get_angular_diameter_distance(
        self,
        z: float | np.ndarray,
    ) -> float | np.ndarray:
        requested = np.asarray(z, dtype=float)
        scalar = requested.ndim == 0
        requested_values = np.atleast_1d(requested)

        available_z = self._requested_redshifts[
            "angular_diameter_distance"
        ]
        distances = np.asarray(
            self.current_state["angular_diameter_distance"],
            dtype=float,
        )

        indices: list[int] = []

        for redshift in requested_values:
            matches = np.where(
                np.isclose(
                    available_z,
                    redshift,
                    rtol=0.0,
                    atol=1.0e-12,
                )
            )[0]

            if matches.size == 0:
                raise ValueError(
                    f"Distance was not computed for z={redshift!r}."
                )

            indices.append(int(matches[0]))

        result = distances[indices]

        if scalar:
            return float(result[0])

        return result


def angular_diameter_distance(
    *,
    z: float,
    h0: float,
    om: float,
) -> float:
    """Return the angular-diameter distance in Mpc."""

    if z < 0.0:
        raise ValueError("Redshift must be non-negative.")

    integral, _ = quad(
        lambda zp: 1.0 / expansion_rate_ratio(zp, om),
        0.0,
        z,
        epsabs=1.0e-10,
        epsrel=1.0e-10,
        limit=200,
    )

    comoving_distance = SPEED_OF_LIGHT_KM_S * integral / h0
    return comoving_distance / (1.0 + z)


def expansion_rate_ratio(
    z: float,
    om: float,
) -> float:
    """Return E(z)=H(z)/H0 for flat LCDM."""

    return float(
        np.sqrt(
            om * (1.0 + z) ** 3
            + 1.0
            - om
        )
    )


def main() -> None:
    """Execute the independent Union3 MCMC run."""

    OUTPUT_ROOT.parent.mkdir(parents=True, exist_ok=True)

    info = {
        "theory": {
            "independent_flat_lcdm": {
                "external": IndependentFlatLCDMTheory,
                "input_params": ["H0", "Om"],
            }
        },
        "likelihood": {
            "sn.union3": {
                "use_abs_mag": False,
            }
        },
        "params": {
            "H0": {
                "value": 70.0,
                "latex": "H_0",
            },
            "Om": {
                "prior": {
                    "min": 0.05,
                    "max": 0.60,
                },
                "ref": 0.30,
                "proposal": 0.02,
                "latex": r"\Omega_m",
            },
        },
        "sampler": {
            "mcmc": {
                "seed": 20260718,
                "burn_in": 200,
                "learn_proposal": True,
                "Rminus1_stop": 0.01,
                "Rminus1_cl_stop": 0.05,
                "max_samples": 10000,
            }
        },
        "output": str(OUTPUT_ROOT),
        "force": True,
    }

    updated_info, sampler = run(info)

    sample = sampler.products()["sample"]

    print("Independent Union3 Cobaya run completed.")
    print(f"Number of rows: {len(sample)}")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Updated keys: {sorted(updated_info.keys())}")


if __name__ == "__main__":
    main()
