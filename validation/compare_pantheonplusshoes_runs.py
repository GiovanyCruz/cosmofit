"""Compare CosmoFit and direct-Cobaya Pantheon+SH0ES chains."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from getdist import loadMCSamples


def newest_cosmofit_root() -> Path:
    """Return the newest CosmoFit Pantheon+SH0ES chain root."""

    parent = Path(
        "outputs/validation_pantheonplusshoes_lcdm"
    )

    run_directories = sorted(
        path
        for path in parent.iterdir()
        if path.is_dir()
    )

    if not run_directories:
        raise FileNotFoundError(
            "No CosmoFit Pantheon+SH0ES validation runs found."
        )

    return run_directories[-1] / "chains" / "chain"


def summarize(root: Path, label: str) -> dict[str, float]:
    """Return marginalized Om statistics for one chain."""

    samples = loadMCSamples(
        str(root),
        settings={"ignore_rows": 0.3},
    )

    stats = samples.getMargeStats()
    parameter = stats.parWithName("Om")

    result = {
        "mean": float(parameter.mean),
        "sigma": float(parameter.err),
        "lower68": float(parameter.limits[0].lower),
        "upper68": float(parameter.limits[0].upper),
        "lower95": float(parameter.limits[1].lower),
        "upper95": float(parameter.limits[1].upper),
    }

    print(f"\n{label}")
    print("-" * len(label))
    print(
        f"Om = {result['mean']:.6f} "
        f"+/- {result['sigma']:.6f}"
    )
    print(
        f"68% = [{result['lower68']:.6f}, "
        f"{result['upper68']:.6f}]"
    )
    print(
        f"95% = [{result['lower95']:.6f}, "
        f"{result['upper95']:.6f}]"
    )

    return result


def relative_difference(
    first: float,
    second: float,
) -> float:
    """Return symmetric relative percentage difference."""

    denominator = 0.5 * (
        abs(first) + abs(second)
    )

    if denominator == 0.0:
        return 0.0

    return (
        100.0
        * abs(first - second)
        / denominator
    )


def normalized_mean_difference(
    first_mean: float,
    first_sigma: float,
    second_mean: float,
    second_sigma: float,
) -> float:
    """Return the mean separation in combined-sigma units."""

    combined_sigma = np.sqrt(
        first_sigma**2 + second_sigma**2
    )

    return (
        abs(first_mean - second_mean)
        / combined_sigma
    )


def main() -> None:
    """Compare the two Pantheon+SH0ES posterior chains."""

    cosmofit = summarize(
        newest_cosmofit_root(),
        "CosmoFit",
    )

    direct = summarize(
        Path(
            "outputs/"
            "direct_cobaya_pantheonplusshoes_lcdm/"
            "chain"
        ),
        "Direct Cobaya",
    )

    print("\nComparison")
    print("----------")
    print(
        "Om mean relative difference: "
        f"{relative_difference(cosmofit['mean'], direct['mean']):.4f}%"
    )
    print(
        "Om sigma relative difference: "
        f"{relative_difference(cosmofit['sigma'], direct['sigma']):.4f}%"
    )
    print(
        "Normalized mean separation: "
        f"{normalized_mean_difference(
            cosmofit['mean'],
            cosmofit['sigma'],
            direct['mean'],
            direct['sigma'],
        ):.6f} sigma"
    )


if __name__ == "__main__":
    main()
