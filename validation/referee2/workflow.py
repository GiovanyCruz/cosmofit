"""Reusable, isolated machinery for the Referee Comment 2 experiments.

This module deliberately reuses CosmoFit's public RunConfig and subprocess
runner.  The direct path is intentionally small and independent: it evaluates
the same flat-LCDM H(z) likelihood directly in Cobaya.
"""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cobaya
import getdist
import numpy as np
import pandas as pd
import scipy
import yaml
from cobaya.run import run as cobaya_run
from getdist import loadMCSamples

from cosmofit.application import (
    CosmicChronometerDatasetConfig,
    ModelConfig,
    ParameterConfig,
    RunConfig,
    RuntimeConfig,
    SamplerConfig,
    UniformPriorConfig,
)
from cosmofit.cobaya_engine.runner import run_in_subprocess

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
SUMMARIES = ROOT / "summaries"
PLOTS = ROOT / "plots"
FIXED_DATASET = (
    ROOT.parent / "data" / "cosmic_chronometers_synthetic_recovery_input.csv"
)
EXPRESSION = "H0*sqrt(Om*(1+z)**3 + 1-Om)"
H0_FIDUCIAL = 70.0
OM_FIDUCIAL = 0.30
DEFAULT_MCMC_SEED = 20260717
SMOKE_REALIZATION_SEEDS = (20260718, 20260719, 20260720)
SMOKE_MCMC_SEEDS = (314159, 314160)


@dataclass(frozen=True)
class ParameterResult:
    """Posterior result and interval coverage for one parameter."""

    fiducial: float
    mean: float
    sigma: float
    interval_68_lower: float | None
    interval_68_upper: float | None
    interval_95_lower: float | None
    interval_95_upper: float | None

    @property
    def pull(self) -> float:
        return pull(self.mean, self.fiducial, self.sigma)

    @property
    def covered_68(self) -> bool | None:
        return coverage(self.fiducial, self.interval_68_lower, self.interval_68_upper)

    @property
    def covered_95(self) -> bool | None:
        return coverage(self.fiducial, self.interval_95_lower, self.interval_95_upper)


def project_commit() -> str:
    """Return the checked-out project commit without embedding an absolute path."""

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT.parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def checksum(path: Path) -> str:
    """SHA-256 checksum of an immutable input artifact."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def environment_metadata(
    *, seed: int, dataset_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Return reproducibility metadata shared by both experiment paths."""

    return {
        "created_at_utc": utc_now(),
        "cosmofit_git_commit": project_commit(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cobaya_version": getattr(cobaya, "__version__", "unknown"),
        "getdist_version": getattr(getdist, "__version__", "unknown"),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "random_seed": seed,
        "dataset_path": str(dataset_path),
        "dataset_sha256": checksum(dataset_path),
        "covariance_sha256": None,
        "output_directory": str(output_directory),
    }


def fixed_redshifts_and_errors() -> tuple[np.ndarray, np.ndarray]:
    """Read the manuscript synthetic setup, retaining its exact grid and errors."""

    frame = pd.read_csv(FIXED_DATASET)
    return frame["z"].to_numpy(float), frame["sigma"].to_numpy(float)


def fiducial_hubble(redshifts: np.ndarray) -> np.ndarray:
    return H0_FIDUCIAL * np.sqrt(
        OM_FIDUCIAL * (1.0 + redshifts) ** 3 + 1.0 - OM_FIDUCIAL
    )


def generate_dataset(destination: Path, *, seed: int) -> Path:
    """Generate a deterministic CC realization without touching baseline files."""

    redshifts, errors = fixed_redshifts_and_errors()
    truth = fiducial_hubble(redshifts)
    observed = np.random.default_rng(seed).normal(truth, errors)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The existing CosmoFit CC loader deliberately accepts exactly z,H,sigma.
    # The fiducial prediction is specified by the recorded model configuration.
    pd.DataFrame({"z": redshifts, "H": observed, "sigma": errors}).to_csv(
        destination, index=False
    )
    return destination


def build_run_config(
    dataset_path: Path, run_directory: Path, *, seed: int, label: str
) -> RunConfig:
    """Build exactly the existing synthetic-recovery scientific configuration."""

    return RunConfig(
        schema_version=1,
        model=ModelConfig(
            kind="hz_expression_flat",
            expression=EXPRESSION,
            allowed_functions=("sqrt",),
        ),
        parameters=(
            ParameterConfig(
                "H0",
                "H0",
                "sampled",
                unit="km/s/Mpc",
                prior=UniformPriorConfig(50.0, 90.0),
                reference=70.0,
                proposal=1.0,
            ),
            ParameterConfig(
                "Om",
                "Om",
                "sampled",
                prior=UniformPriorConfig(0.05, 0.60),
                reference=0.30,
                proposal=0.02,
            ),
        ),
        datasets=(
            CosmicChronometerDatasetConfig(
                "cosmic_chronometers", dataset_path, "synthetic-recovery-cc"
            ),
        ),
        sampler=SamplerConfig(
            "cobaya_mcmc",
            seed=seed,
            max_samples=10000,
            burn_in=200,
            learn_proposal=True,
            Rminus1_stop=0.01,
            Rminus1_cl_stop=0.05,
        ),
        runtime=RuntimeConfig(
            run_label=label, output_directory=run_directory, overwrite=False
        ),
    )


def canonical_science_config(dataset_path: Path) -> dict[str, Any]:
    """Science-only payload excluding paths, seeds, and implementation wrappers."""

    config = build_run_config(dataset_path, Path("not-used"), seed=0, label="not-used")
    return {
        "model": {
            "expression": config.model.expression,
            "unit": config.model.expression_unit,
            "redshift_symbol": "z",
        },
        "likelihood": {
            "kind": "independent_gaussian_cc",
            "dataset_sha256": checksum(dataset_path),
            "covariance": "diagonal_sigma_squared",
        },
        "parameters": {
            p.symbol: {
                "prior": [p.prior.minimum, p.prior.maximum],
                "reference": p.reference,
                "proposal": p.proposal,
            }
            for p in config.parameters
            if p.prior
        },
        "sampler": {
            "max_samples": config.sampler.max_samples,
            "burn_in": config.sampler.burn_in,
            "learn_proposal": config.sampler.learn_proposal,
            "Rminus1_stop": config.sampler.Rminus1_stop,
            "Rminus1_cl_stop": config.sampler.Rminus1_cl_stop,
        },
        "packages_path": None,
    }


def compare_science_configs(
    first: dict[str, Any], second: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Return every meaningful canonical-field difference, or an empty mapping."""

    differences: dict[str, dict[str, Any]] = {}
    for key in sorted(set(first) | set(second)):
        if first.get(key) != second.get(key):
            differences[key] = {
                "cosmofit": first.get(key),
                "direct_cobaya": second.get(key),
            }
    return differences


def direct_cobaya_info(
    dataset_path: Path, chain_prefix: Path, *, seed: int
) -> dict[str, Any]:
    """Independent direct-Cobaya formulation matched to the canonical configuration."""

    frame = pd.read_csv(dataset_path)
    z, observed, errors = (
        frame[column].to_numpy(float) for column in ("z", "H", "sigma")
    )

    def loglike(H0: float, Om: float) -> float:
        predicted = H0 * np.sqrt(Om * (1.0 + z) ** 3 + 1.0 - Om)
        return -0.5 * float(np.sum(((observed - predicted) / errors) ** 2))

    return {
        "likelihood": {
            "cc_direct": {"external": loglike, "input_params": ["H0", "Om"]}
        },
        "params": {
            "H0": {
                "prior": {"min": 50.0, "max": 90.0},
                "ref": 70.0,
                "proposal": 1.0,
                "latex": "H_0",
            },
            "Om": {
                "prior": {"min": 0.05, "max": 0.60},
                "ref": 0.30,
                "proposal": 0.02,
                "latex": r"\\Omega_m",
            },
        },
        "sampler": {
            "mcmc": {
                "seed": seed,
                "max_samples": 10000,
                "burn_in": 200,
                "learn_proposal": True,
                "Rminus1_stop": 0.01,
                "Rminus1_cl_stop": 0.05,
            }
        },
        "output": str(chain_prefix),
        "force": False,
    }


def run_direct_cobaya(dataset_path: Path, run_directory: Path, *, seed: int) -> int:
    """Run direct Cobaya once, recording status and exact independent input."""

    if run_is_successful(run_directory):
        return 0
    if run_directory.exists():
        raise FileExistsError(
            f"Refusing to reuse incomplete direct run: {run_directory}"
        )
    chains = run_directory / "chains"
    chains.mkdir(parents=True)
    info = direct_cobaya_info(dataset_path, chains / "chain", seed=seed)
    (run_directory / "direct_cobaya_input.yaml").write_text(
        yaml.safe_dump(_yaml_safe(info, drop_external=True), sort_keys=False),
        encoding="utf-8",
    )
    _write_json(
        run_directory / "metadata.json",
        environment_metadata(
            seed=seed, dataset_path=dataset_path, output_directory=run_directory
        ),
    )
    _write_json(
        run_directory / "science_config.json", canonical_science_config(dataset_path)
    )
    _write_json(
        run_directory / "status.json",
        {
            "state": "running",
            "started_at": utc_now(),
            "run_directory": str(run_directory),
        },
    )
    random.seed(seed)
    np.random.seed(seed)
    started = time.monotonic()
    try:
        cobaya_run(info, no_mpi=True)
    except Exception as exc:
        _write_json(
            run_directory / "status.json",
            {
                "state": "failed",
                "message": str(exc),
                "finished_at": utc_now(),
                "wall_seconds": time.monotonic() - started,
            },
        )
        return 1
    _write_json(
        run_directory / "status.json",
        {
            "state": "succeeded",
            "finished_at": utc_now(),
            "wall_seconds": time.monotonic() - started,
            "run_directory": str(run_directory),
        },
    )
    return 0


def run_cosmofit(
    dataset_path: Path, run_directory: Path, *, seed: int, label: str
) -> int:
    """Run the unchanged CosmoFit execution backend exactly once."""

    if run_is_successful(run_directory):
        return 0
    if run_directory.exists():
        raise FileExistsError(
            f"Refusing to reuse incomplete CosmoFit run: {run_directory}"
        )
    config = build_run_config(dataset_path, run_directory, seed=seed, label=label)
    started = time.monotonic()
    result = run_in_subprocess(config)
    metadata = environment_metadata(
        seed=seed, dataset_path=dataset_path, output_directory=run_directory
    )
    metadata["wall_seconds_referee2"] = time.monotonic() - started
    _write_json(run_directory / "referee2_metadata.json", metadata)
    _write_json(
        run_directory / "science_config.json", canonical_science_config(dataset_path)
    )
    return result.return_code


def run_is_successful(run_directory: Path) -> bool:
    status = run_directory / "status.json"
    if not status.is_file():
        return False
    try:
        return (
            json.loads(status.read_text(encoding="utf-8")).get("state") == "succeeded"
        )
    except json.JSONDecodeError:
        return False


def analyze_run(run_directory: Path) -> dict[str, Any]:
    """Use GetDist posterior summaries and Cobaya checkpoint/progress diagnostics."""

    root = run_directory / "chains" / "chain"
    _configure_getdist_cache()
    samples = loadMCSamples(
        str(root),
        no_cache=True,
        settings={"ignore_rows": 0.0, "contours": [0.68, 0.95]},
    )
    stats = samples.getMargeStats()
    results: dict[str, ParameterResult] = {}
    for symbol, fiducial in (("H0", H0_FIDUCIAL), ("Om", OM_FIDUCIAL)):
        item = stats.parWithName(symbol)
        limits = dict(zip((0.68, 0.95), item.limits, strict=True))
        lower68, upper68 = _limit_values(limits[0.68])
        lower95, upper95 = _limit_values(limits[0.95])
        results[symbol] = ParameterResult(
            fiducial,
            float(item.mean),
            float(item.err),
            lower68,
            upper68,
            lower95,
            upper95,
        )
    checkpoint = _load_yaml(root.with_suffix(".checkpoint"))
    progress = _read_progress(root.with_suffix(".progress"))
    sampler = (checkpoint.get("sampler") or {}).get("mcmc") or {}
    status = _load_json(run_directory / "status.json")
    return {
        "run_directory": str(run_directory),
        "run_status": status.get("state", "unknown"),
        "converged": sampler.get("converged"),
        "rminus1_last": sampler.get("Rminus1_last"),
        "effective_sample_size_H0": float(
            samples.getEffectiveSamples(_parameter_index(samples, "H0"))
        ),
        "effective_sample_size_Om": float(
            samples.getEffectiveSamples(_parameter_index(samples, "Om"))
        ),
        # Cobaya's progress N is explicitly the accepted-chain count. The
        # total proposal count is not exposed in this artifact format.
        "accepted_sample_count": _last_progress(progress, "N"),
        "total_sample_count": None,
        "acceptance_rate": _last_progress(progress, "acceptance_rate"),
        "wall_seconds": _wall_seconds(run_directory),
        "H0": asdict(results["H0"]),
        "Om": asdict(results["Om"]),
    }


def flatten_result(
    result: dict[str, Any],
    *,
    realization: int | None = None,
    seed: int | None = None,
    workflow: str | None = None,
) -> dict[str, Any]:
    """Make a stable, CSV-ready row retaining all requested diagnostics."""

    row: dict[str, Any] = {
        "realization": realization,
        "random_seed": seed,
        "workflow": workflow,
    }
    for parameter in ("H0", "Om"):
        value = result[parameter]
        row.update(
            {
                f"{parameter}_fiducial": value["fiducial"],
                f"{parameter}_posterior_mean": value["mean"],
                f"{parameter}_posterior_sigma": value["sigma"],
                f"{parameter}_pull": pull(
                    value["mean"], value["fiducial"], value["sigma"]
                ),
                f"{parameter}_68_lower": value["interval_68_lower"],
                f"{parameter}_68_upper": value["interval_68_upper"],
                f"{parameter}_95_lower": value["interval_95_lower"],
                f"{parameter}_95_upper": value["interval_95_upper"],
                f"{parameter}_coverage_68": coverage(
                    value["fiducial"],
                    value["interval_68_lower"],
                    value["interval_68_upper"],
                ),
                f"{parameter}_coverage_95": coverage(
                    value["fiducial"],
                    value["interval_95_lower"],
                    value["interval_95_upper"],
                ),
            }
        )
    row.update(
        {
            key: result.get(key)
            for key in (
                "converged",
                "rminus1_last",
                "effective_sample_size_H0",
                "effective_sample_size_Om",
                "accepted_sample_count",
                "total_sample_count",
                "acceptance_rate",
                "wall_seconds",
                "run_directory",
                "run_status",
            )
        }
    )
    return row


def pull(mean: float, fiducial: float, sigma: float) -> float:
    if sigma <= 0:
        raise ValueError("Posterior sigma must be positive to calculate a pull.")
    return (mean - fiducial) / sigma


def coverage(fiducial: float, lower: float | None, upper: float | None) -> bool | None:
    return None if lower is None or upper is None else lower <= fiducial <= upper


def aggregate_realizations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive aggregate only over successful converged realizations."""

    valid = [
        row
        for row in rows
        if row.get("run_status") == "succeeded" and row.get("converged") is True
    ]
    result: dict[str, Any] = {
        "included_realizations": len(valid),
        "excluded_realizations": len(rows) - len(valid),
        "interpretation": (
            "Measured fractions are descriptive; they are not asserted to equal "
            "nominal coverage for this finite experiment."
        ),
    }
    for parameter in ("H0", "Om"):
        means = np.array([row[f"{parameter}_posterior_mean"] for row in valid], float)
        sigmas = np.array([row[f"{parameter}_posterior_sigma"] for row in valid], float)
        pulls = np.array([row[f"{parameter}_pull"] for row in valid], float)
        result[parameter] = {
            "mean_recovered": _mean_or_none(means),
            "standard_deviation_of_means": _std_or_none(means),
            "mean_posterior_sigma": _mean_or_none(sigmas),
            "mean_pull": _mean_or_none(pulls),
            "standard_deviation_of_pulls": _std_or_none(pulls),
            "coverage_fraction_68": _fraction(valid, f"{parameter}_coverage_68"),
            "coverage_fraction_95": _fraction(valid, f"{parameter}_coverage_95"),
        }
    return result


def aggregate_seed_workflows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-path width variability and paired symmetric differences."""

    output: dict[str, Any] = {
        "workflows": {},
        "paired_relative_sigma_differences_percent": {},
    }
    for workflow in ("cosmofit", "direct_cobaya"):
        selected = [
            row
            for row in rows
            if row.get("workflow") == workflow
            and row.get("run_status") == "succeeded"
            and row.get("converged") is True
        ]
        output["workflows"][workflow] = {
            parameter: _seed_parameter_stats(selected, parameter)
            for parameter in ("H0", "Om")
        }
    by_seed: dict[int, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_seed.setdefault(int(row["random_seed"]), {})[str(row["workflow"])] = row
    for parameter in ("H0", "Om"):
        differences = [
            symmetric_percent(
                pair["cosmofit"][f"{parameter}_posterior_sigma"],
                pair["direct_cobaya"][f"{parameter}_posterior_sigma"],
            )
            for pair in by_seed.values()
            if {"cosmofit", "direct_cobaya"} <= set(pair)
        ]
        output["paired_relative_sigma_differences_percent"][parameter] = {
            "values": differences,
            "mean": _mean_or_none(np.array(differences)),
            "standard_deviation": _std_or_none(np.array(differences)),
            "minimum": float(np.min(differences)) if differences else None,
            "maximum": float(np.max(differences)) if differences else None,
        }
    return output


def symmetric_percent(first: float, second: float) -> float:
    denominator = 0.5 * (abs(first) + abs(second))
    return 0.0 if denominator == 0 else 100.0 * abs(first - second) / denominator


def write_rows(rows: list[dict[str, Any]], stem: str) -> tuple[Path, Path]:
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = SUMMARIES / f"{stem}.json", SUMMARIES / f"{stem}.csv"
    _write_json(json_path, rows)
    keys = sorted({key for row in rows for key in row})
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def _configure_getdist_cache() -> None:
    import getdist as getdist_module

    cache = OUTPUTS / ".getdist_cache"
    cache.mkdir(parents=True, exist_ok=True)
    getdist_module.cache_dir = str(cache)


def _parameter_index(samples: Any, symbol: str) -> int:
    return samples.getParamNames().numberOfName(symbol)


def _limit_values(limit: Any) -> tuple[float | None, float | None]:
    return (None, None) if limit is None else (float(limit.lower), float(limit.upper))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_progress(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    # Cobaya's leading '#' is a visual marker, not a column; explicit names
    # prevent pandas from shifting every diagnostic field left by one.
    return pd.read_csv(
        path,
        sep=r"\s+",
        skiprows=1,
        names=["N", "timestamp", "acceptance_rate", "Rminus1", "Rminus1_cl"],
    )


def _last_progress(frame: pd.DataFrame, field: str) -> float | int | None:
    if frame.empty or field not in frame:
        return None
    value = frame[field].iloc[-1]
    return None if pd.isna(value) else float(value)


def _wall_seconds(run_directory: Path) -> float | None:
    status = _load_json(run_directory / "status.json")
    if "wall_seconds" in status:
        return float(status["wall_seconds"])
    metadata = _load_json(run_directory / "referee2_metadata.json")
    return (
        float(metadata["wall_seconds_referee2"])
        if "wall_seconds_referee2" in metadata
        else None
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _yaml_safe(info: dict[str, Any], *, drop_external: bool) -> dict[str, Any]:
    copied = json.loads(json.dumps(info, default=str))
    if drop_external:
        copied["likelihood"]["cc_direct"].pop("external", None)
    return copied


def _mean_or_none(values: np.ndarray) -> float | None:
    return float(np.mean(values)) if len(values) else None


def _std_or_none(values: np.ndarray) -> float | None:
    return float(np.std(values, ddof=1)) if len(values) > 1 else None


def _fraction(rows: list[dict[str, Any]], key: str) -> float | None:
    flags = [row[key] for row in rows if row.get(key) is not None]
    return float(np.mean(flags)) if flags else None


def _seed_parameter_stats(
    rows: list[dict[str, Any]], parameter: str
) -> dict[str, float | None]:
    widths = np.array([row[f"{parameter}_posterior_sigma"] for row in rows], float)
    means = np.array([row[f"{parameter}_posterior_mean"] for row in rows], float)
    mean_width, std_width = _mean_or_none(widths), _std_or_none(widths)
    return {
        "mean_posterior_sigma": mean_width,
        "standard_deviation_posterior_sigma": std_width,
        "coefficient_of_variation_posterior_sigma": None
        if mean_width in (None, 0.0) or std_width is None
        else std_width / mean_width,
        "standard_deviation_posterior_means": _std_or_none(means),
    }
