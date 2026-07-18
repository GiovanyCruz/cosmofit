"""Generate a reproducible synthetic cosmic-chronometer dataset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

H0_TRUE = 70.0
OM_TRUE = 0.30
RANDOM_SEED = 20260717

OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "data"
    / "cosmic_chronometers_synthetic_recovery.csv"
)


def main() -> None:
    """Generate synthetic H(z) measurements for flat LCDM."""

    redshifts = np.array(
        [
            0.05,
            0.10,
            0.17,
            0.25,
            0.35,
            0.48,
            0.60,
            0.75,
            0.90,
            1.10,
            1.30,
            1.50,
            1.80,
            2.10,
            2.35,
        ],
        dtype=float,
    )

    uncertainties = np.array(
        [
            2.5,
            3.0,
            3.5,
            4.0,
            4.0,
            4.5,
            5.0,
            5.5,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
            11.0,
            12.0,
        ],
        dtype=float,
    )

    rng = np.random.default_rng(RANDOM_SEED)

    hubble_true = H0_TRUE * np.sqrt(
        OM_TRUE * (1.0 + redshifts) ** 3
        + 1.0
        - OM_TRUE
    )

    hubble_observed = rng.normal(
        loc=hubble_true,
        scale=uncertainties,
    )

    dataframe = pd.DataFrame(
        {
            "z": redshifts,
            "H": hubble_observed,
            "sigma": uncertainties,
            "H_true": hubble_true,
        }
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(OUTPUT_PATH, index=False)

    print(f"Dataset written to: {OUTPUT_PATH}")
    print(f"H0_true = {H0_TRUE}")
    print(f"Om_true = {OM_TRUE}")
    print(f"seed = {RANDOM_SEED}")
    print(f"number of points = {len(dataframe)}")


if __name__ == "__main__":
    main()
