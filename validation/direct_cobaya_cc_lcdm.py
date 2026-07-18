"""Independent Cobaya validation for flat LCDM with cosmic chronometers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from cobaya.run import run

DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "cosmic_chronometers"
    / "cosmic_chronometers_18.csv"
)

OUTPUT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "direct_cobaya_cc_lcdm"
    / "chain"
)


def load_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load redshift, H(z), and uncertainties from CSV."""

    dataframe = pd.read_csv(DATA_PATH)

    required_columns = {"z", "H", "sigma"}
    missing = required_columns.difference(dataframe.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    z = dataframe["z"].to_numpy(dtype=float)
    hubble = dataframe["H"].to_numpy(dtype=float)
    sigma = dataframe["sigma"].to_numpy(dtype=float)

    if np.any(sigma <= 0):
        raise ValueError("All uncertainties must be positive.")

    return z, hubble, sigma


Z_DATA, H_DATA, SIGMA_DATA = load_data()


def loglike(H0: float, Om: float) -> float:
    """Gaussian log-likelihood for independent H(z) measurements."""

    model = H0 * np.sqrt(
        Om * (1.0 + Z_DATA) ** 3
        + 1.0
        - Om
    )

    residuals = (H_DATA - model) / SIGMA_DATA
    chi2 = np.sum(residuals**2)

    return -0.5 * float(chi2)


def main() -> None:
    """Execute the independent Cobaya MCMC run."""

    OUTPUT_ROOT.parent.mkdir(parents=True, exist_ok=True)

    info = {
        "likelihood": {
            "cc_direct": {
                "external": loglike,
                "input_params": ["H0", "Om"],
            }
        },
        "params": {
            "H0": {
                "prior": {
                    "min": 50.0,
                    "max": 90.0,
                },
                "ref": 70.0,
                "proposal": 1.0,
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
                "seed": 314159,
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

    products = sampler.products()
    sample = products["sample"]

    print("Independent Cobaya run completed.")
    print(f"Number of rows: {len(sample)}")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"Updated keys: {sorted(updated_info.keys())}")


if __name__ == "__main__":
    main()
