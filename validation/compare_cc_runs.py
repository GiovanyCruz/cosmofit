"""Compare CosmoFit and direct Cobaya posterior chains."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from getdist import loadMCSamples


def newest_cosmofit_root() -> Path:
    """Return the most recent CosmoFit validation chain root."""

    parent = Path("outputs/validation_cc_lcdm")
    run_directories = sorted(
        path for path in parent.iterdir() if path.is_dir()
    )

    if not run_directories:
        raise FileNotFoundError(
            "No CosmoFit validation runs were found."
        )

    return run_directories[-1] / "chains" / "chain"


def summarize(root: Path, label: str) -> dict[str, float]:
    """Load and summarize one GetDist chain."""

    samples = loadMCSamples(
        str(root),
        settings={"ignore_rows": 0.3},
    )

    means = samples.getMeans()
    covariance = samples.getCov()
    names = samples.getParamNames()

    h0_index = names.numberOfName("H0")
    om_index = names.numberOfName("Om")

    result = {
        "H0_mean": float(means[h0_index]),
        "H0_sigma": float(
            np.sqrt(covariance[h0_index, h0_index])
        ),
        "Om_mean": float(means[om_index]),
        "Om_sigma": float(
            np.sqrt(covariance[om_index, om_index])
        ),
    }

    print(f"\n{label}")
    print("-" * len(label))
    print(
        f"H0 = {result['H0_mean']:.6f} "
        f"+/- {result['H0_sigma']:.6f}"
    )
    print(
        f"Om = {result['Om_mean']:.6f} "
        f"+/- {result['Om_sigma']:.6f}"
    )

    return result


def relative_difference(first: float, second: float) -> float:
    """Calculate symmetric relative percentage difference."""

    denominator = 0.5 * (abs(first) + abs(second))

    if denominator == 0:
        return 0.0

    return 100.0 * abs(first - second) / denominator


def main() -> None:
    cosmofit = summarize(
        newest_cosmofit_root(),
        "CosmoFit",
    )

    direct = summarize(
        Path("outputs/direct_cobaya_cc_lcdm/chain"),
        "Direct Cobaya",
    )

    print("\nRelative differences")
    print("--------------------")
    print(
        "H0 mean: "
        f"{relative_difference(cosmofit['H0_mean'], direct['H0_mean']):.4f}%"
    )
    print(
        "Om mean: "
        f"{relative_difference(cosmofit['Om_mean'], direct['Om_mean']):.4f}%"
    )
    print(
        "H0 sigma: "
        f"{relative_difference(cosmofit['H0_sigma'], direct['H0_sigma']):.4f}%"
    )
    print(
        "Om sigma: "
        f"{relative_difference(cosmofit['Om_sigma'], direct['Om_sigma']):.4f}%"
    )


if __name__ == "__main__":
    main()
