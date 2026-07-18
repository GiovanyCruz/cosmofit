"""Build reproducible validation-summary tables for the CosmoFit paper."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

RESULTS_DIRECTORY = Path("validation/results")
OUTPUT_CSV = RESULTS_DIRECTORY / "validation_summary.csv"
OUTPUT_MARKDOWN = RESULTS_DIRECTORY / "validation_summary.md"


@dataclass(frozen=True)
class ValidationResult:
    """One comparison between CosmoFit and a reference calculation."""

    dataset: str
    parameter: str
    cosmofit_mean: float
    cosmofit_sigma: float
    reference_mean: float
    reference_sigma: float
    mean_relative_difference_percent: float
    sigma_relative_difference_percent: float
    normalized_mean_separation_sigma: float


def read_text(filename: str) -> str:
    """Read one stored validation-result file."""

    path = RESULTS_DIRECTORY / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Required validation result was not found: {path}"
        )

    return path.read_text(encoding="utf-8")


def extract_float(
    text: str,
    pattern: str,
    *,
    description: str,
) -> float:
    """Extract one floating-point value using a regular expression."""

    match = re.search(pattern, text, flags=re.MULTILINE)

    if match is None:
        raise ValueError(
            f"Could not extract {description} using pattern: {pattern}"
        )

    return float(match.group(1))


def parse_two_parameter_comparison(
    filename: str,
    *,
    dataset: str,
) -> list[ValidationResult]:
    """Parse the direct-Cobaya cosmic-chronometer comparison."""

    text = read_text(filename)

    sections = re.split(
        r"\n(?=Direct Cobaya\n)",
        text,
        maxsplit=1,
    )

    if len(sections) != 2:
        raise ValueError(
            f"Could not separate CosmoFit and Direct Cobaya sections in {filename}."
        )

    cosmofit_text = sections[0]
    direct_text = sections[1]

    relative_section = text.split(
        "Relative differences",
        maxsplit=1,
    )[-1]

    results: list[ValidationResult] = []

    for parameter in ("H0", "Om"):
        cosmofit_mean = extract_float(
            cosmofit_text,
            rf"{parameter}\s*=\s*([-+0-9.eE]+)\s*\+/-",
            description=f"{parameter} CosmoFit mean",
        )
        cosmofit_sigma = extract_float(
            cosmofit_text,
            rf"{parameter}\s*=\s*[-+0-9.eE]+\s*\+/-\s*([-+0-9.eE]+)",
            description=f"{parameter} CosmoFit sigma",
        )
        reference_mean = extract_float(
            direct_text,
            rf"{parameter}\s*=\s*([-+0-9.eE]+)\s*\+/-",
            description=f"{parameter} reference mean",
        )
        reference_sigma = extract_float(
            direct_text,
            rf"{parameter}\s*=\s*[-+0-9.eE]+\s*\+/-\s*([-+0-9.eE]+)",
            description=f"{parameter} reference sigma",
        )

        mean_relative_difference = extract_float(
            relative_section,
            rf"{parameter} mean:\s*([-+0-9.eE]+)%",
            description=f"{parameter} mean relative difference",
        )
        sigma_relative_difference = extract_float(
            relative_section,
            rf"{parameter} sigma:\s*([-+0-9.eE]+)%",
            description=f"{parameter} sigma relative difference",
        )

        combined_sigma = (
            cosmofit_sigma**2 + reference_sigma**2
        ) ** 0.5

        normalized_separation = (
            abs(cosmofit_mean - reference_mean)
            / combined_sigma
        )

        results.append(
            ValidationResult(
                dataset=dataset,
                parameter=parameter,
                cosmofit_mean=cosmofit_mean,
                cosmofit_sigma=cosmofit_sigma,
                reference_mean=reference_mean,
                reference_sigma=reference_sigma,
                mean_relative_difference_percent=mean_relative_difference,
                sigma_relative_difference_percent=sigma_relative_difference,
                normalized_mean_separation_sigma=normalized_separation,
            )
        )

    return results


def parse_single_parameter_comparison(
    filename: str,
    *,
    dataset: str,
) -> ValidationResult:
    """Parse one supernova comparison file."""

    text = read_text(filename)

    cosmofit_section, remainder = text.split(
        "Direct Cobaya",
        maxsplit=1,
    )

    direct_section, comparison_section = remainder.split(
        "Comparison",
        maxsplit=1,
    )

    return ValidationResult(
        dataset=dataset,
        parameter="Om",
        cosmofit_mean=extract_float(
            cosmofit_section,
            r"Om\s*=\s*([-+0-9.eE]+)\s*\+/-",
            description=f"{dataset} CosmoFit mean",
        ),
        cosmofit_sigma=extract_float(
            cosmofit_section,
            r"Om\s*=\s*[-+0-9.eE]+\s*\+/-\s*([-+0-9.eE]+)",
            description=f"{dataset} CosmoFit sigma",
        ),
        reference_mean=extract_float(
            direct_section,
            r"Om\s*=\s*([-+0-9.eE]+)\s*\+/-",
            description=f"{dataset} reference mean",
        ),
        reference_sigma=extract_float(
            direct_section,
            r"Om\s*=\s*[-+0-9.eE]+\s*\+/-\s*([-+0-9.eE]+)",
            description=f"{dataset} reference sigma",
        ),
        mean_relative_difference_percent=extract_float(
            comparison_section,
            r"Om mean relative difference:\s*([-+0-9.eE]+)%",
            description=f"{dataset} mean relative difference",
        ),
        sigma_relative_difference_percent=extract_float(
            comparison_section,
            r"Om sigma relative difference:\s*([-+0-9.eE]+)%",
            description=f"{dataset} sigma relative difference",
        ),
        normalized_mean_separation_sigma=extract_float(
            comparison_section,
            r"Normalized mean separation:\s*([-+0-9.eE]+)\s*sigma",
            description=f"{dataset} normalized mean separation",
        ),
    )


def write_csv(results: list[ValidationResult]) -> None:
    """Write a machine-readable validation table."""

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(handle)

        writer.writerow(
            [
                "dataset",
                "parameter",
                "cosmofit_mean",
                "cosmofit_sigma",
                "reference_mean",
                "reference_sigma",
                "mean_relative_difference_percent",
                "sigma_relative_difference_percent",
                "normalized_mean_separation_sigma",
            ]
        )

        for result in results:
            writer.writerow(
                [
                    result.dataset,
                    result.parameter,
                    f"{result.cosmofit_mean:.6f}",
                    f"{result.cosmofit_sigma:.6f}",
                    f"{result.reference_mean:.6f}",
                    f"{result.reference_sigma:.6f}",
                    f"{result.mean_relative_difference_percent:.4f}",
                    f"{result.sigma_relative_difference_percent:.4f}",
                    f"{result.normalized_mean_separation_sigma:.6f}",
                ]
            )


def write_markdown(results: list[ValidationResult]) -> None:
    """Write a paper-friendly Markdown validation table."""

    lines = [
        "# CosmoFit validation summary",
        "",
        "| Dataset | Parameter | CosmoFit | Direct reference | Mean difference | Separation |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        lines.append(
            "| "
            f"{result.dataset} | "
            f"{result.parameter} | "
            f"{result.cosmofit_mean:.6f} ± {result.cosmofit_sigma:.6f} | "
            f"{result.reference_mean:.6f} ± {result.reference_sigma:.6f} | "
            f"{result.mean_relative_difference_percent:.4f}% | "
            f"{result.normalized_mean_separation_sigma:.6f} σ |"
        )

    lines.extend(
        [
            "",
            "The direct references were evaluated independently of "
            "CosmoFit's configuration builder and generic background theory.",
            "",
        ]
    )

    OUTPUT_MARKDOWN.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    """Build all validation-summary artifacts."""

    results: list[ValidationResult] = []

    results.extend(
        parse_two_parameter_comparison(
            "cc_lcdm_comparison.txt",
            dataset="Cosmic Chronometers",
        )
    )

    results.append(
        parse_single_parameter_comparison(
            "pantheonplus_comparison.txt",
            dataset="Pantheon+",
        )
    )

    results.append(
        parse_single_parameter_comparison(
            "pantheonplusshoes_comparison.txt",
            dataset="Pantheon+SH0ES",
        )
    )

    results.append(
        parse_single_parameter_comparison(
            "union3_comparison.txt",
            dataset="Union3",
        )
    )

    write_csv(results)
    write_markdown(results)

    print(f"Written: {OUTPUT_CSV}")
    print(f"Written: {OUTPUT_MARKDOWN}")
    print(f"Validation rows: {len(results)}")


if __name__ == "__main__":
    main()
