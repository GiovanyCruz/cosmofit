# CosmoFit Architecture

## Purpose

This document defines the first implementation milestone for CosmoFit
in this repository. It is scoped to:

- flat background cosmology;
- cosmic chronometer likelihoods only;
- uniform priors;
- Cobaya MCMC execution;
- command-line execution only;
- no graphical interface yet.

The design must satisfy the dependency rule from `AGENTS.md`:

```text
ui -> application services -> domain/cosmology
                           -> likelihoods
                           -> cobaya adapter
```

For milestone 1, the CLI replaces the UI as the only entrypoint, but
the same dependency direction still applies.

## Environment Baseline

Milestone 1 implementation should align the repository with the project
rules before runtime work begins:

- Python 3.12 is the supported interpreter target.
- public functions use type hints;
- `pathlib.Path` is used for filesystem paths;
- NumPy arrays are the internal numeric representation;
- pytest and Ruff remain the default test and lint tools.

Current repository metadata does not fully match this baseline:

- `pyproject.toml` currently declares `requires-python = ">=3.11"`;
- Ruff currently targets `py311`.

Those settings should be aligned to Python 3.12 at the start of
implementation so the packaging contract matches the project rules.

## Milestone 1 Boundaries

Milestone 1 is intentionally narrow:

- The user provides an `H(z)` expression in `km/s/Mpc`.
- The CLI validates the expression, parameters, dataset selection,
  and sampler settings.
- The application layer produces a normalized run manifest.
- `cobaya_engine` translates that manifest into a Cobaya input file and
  runs Cobaya in a separate process.
- The only supported dataset is cosmic chronometers.
- The only supported prior type is uniform.
- `ui` remains unused and must not be imported by milestone 1 code.

`E(z)` input is deferred in milestone 1. It introduces an avoidable
ambiguity around `H0` ownership and units in the first milestone. The
parser and config contracts should therefore accept `H(z)` only until a
later ADR expands the model family. The broader product direction can
still reserve room for `E(z)` as a future model kind.

## Package Architecture

The current skeleton already contains:

```text
src/cosmofit/
  analysis/
  cobaya_engine/
  cosmology/
  likelihoods/
  ui/
```

Milestone 1 should add:

```text
src/cosmofit/
  application/
    __init__.py
    config_models.py
    loaders.py
    services.py
    validation.py
    ports.py
    results.py
  cli/
    __init__.py
    main.py
  cosmology/
    __init__.py
    expression_ast.py
    expression_parser.py
    expression_evaluator.py
    validators.py
    reference_models.py
  likelihoods/
    __init__.py
    base.py
    cosmic_chronometers.py
    datasets.py
  cobaya_engine/
    __init__.py
    config_builder.py
    runner.py
    worker.py
    status.py
    artifacts.py
  analysis/
    __init__.py
  ui/
    __init__.py
```

### Responsibilities by Package

`src/cosmofit/cli`

- Parse command-line arguments.
- Load a YAML run file from disk.
- Invoke application services.
- Return exit codes and human-readable errors.
- Never import Cobaya directly.

`src/cosmofit/application`

- Own public configuration models and validation errors.
- Normalize the user run file into immutable internal models.
- Coordinate cosmology, likelihood, and Cobaya adapter objects.
- Expose use cases such as `validate-run` and `run-inference`.
- Depend on `cosmology`, `likelihoods`, and `cobaya_engine`, but not on
  `ui`.

`src/cosmofit/cosmology`

- Own safe parsing for user-provided `H(z)`.
- Define model-facing protocols for predicting `H(z)` on NumPy arrays.
- Enforce units and physical validity checks.
- Contain flat-LCDM reference calculations used for scientific tests.
- Never import PySide6 or Cobaya.

`src/cosmofit/likelihoods`

- Load and validate cosmic chronometer datasets.
- Define pure likelihood classes that receive predictions through an
  explicit predictor interface.
- Never import PySide6 or Cobaya.

`src/cosmofit/cobaya_engine`

- Translate validated application configuration into Cobaya input.
- Build the Cobaya likelihood wrapper that bridges Cobaya parameter
  dictionaries into domain/likelihood calls.
- Execute each run in an isolated run directory.
- Capture logs, generated config, status, and failure details.
- Contain all Cobaya imports and types.

`src/cosmofit/analysis`

- Reserved for future GetDist integration.
- Out of scope for milestone 1 runtime.

`src/cosmofit/ui`

- Reserved for PySide6 desktop work after command-line validation.
- Must remain isolated from scientific and Cobaya code.

## Main Configuration Data Models

Milestone 1 should use dataclasses for core configuration models.
Dataclasses are sufficient here, avoid new dependencies, and keep the
application boundary explicit.

All public configuration models belong in
`src/cosmofit/application/config_models.py`.

### Top-Level Models

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class UniformPriorConfig:
    lower: float
    upper: float


@dataclass(frozen=True)
class ParameterConfig:
    name: str
    symbol: str
    role: Literal["sampled", "fixed"]
    unit: str | None
    value: float | None
    prior: UniformPriorConfig | None
    reference: float | None
    proposal: float | None


@dataclass(frozen=True)
class ModelConfig:
    kind: Literal["hz_expression_flat"]
    expression: str
    expression_unit: Literal["km/s/Mpc"]
    redshift_symbol: Literal["z"]
    allowed_functions: tuple[str, ...]


@dataclass(frozen=True)
class CosmicChronometerDatasetConfig:
    kind: Literal["cosmic_chronometers"]
    data_path: Path
    name: str = "cosmic_chronometers"


@dataclass(frozen=True)
class SamplerConfig:
    kind: Literal["cobaya_mcmc"]
    seed: int
    max_samples: int | None
    burn_in: int | None
    learn_proposal: bool
    Rminus1_stop: float | None
    Rminus1_cl_stop: float | None


@dataclass(frozen=True)
class RuntimeConfig:
    run_label: str
    output_root: Path
    overwrite: bool


@dataclass(frozen=True)
class RunConfig:
    schema_version: int
    model: ModelConfig
    parameters: tuple[ParameterConfig, ...]
    datasets: tuple[CosmicChronometerDatasetConfig, ...]
    sampler: SamplerConfig
    runtime: RuntimeConfig
```

### Configuration Rules

`RunConfig`

- `schema_version` is required and starts at `1`.
- The same file is the source of truth for validation and reproducible
  reruns.
- The schema should be designed so a future `ez_expression_flat` model
  kind can be added without breaking existing `hz_expression_flat`
  manifests.

`ModelConfig`

- Milestone 1 supports `kind = "hz_expression_flat"` only.
- `expression_unit` must be exactly `km/s/Mpc`.
- `redshift_symbol` is fixed to `z`.
- The expression may reference only declared parameter symbols and
  approved math functions.
- Future `E(z)` support should use a separate model kind rather than
  overloading the `H(z)` contract with optional scaling behavior.

`ParameterConfig`

- `role = "fixed"` requires `value` and forbids `prior` and `proposal`.
- `role = "sampled"` requires `prior`, `reference`, and `proposal`.
- `role = "fixed"` may omit `reference`; the application may normalize
  it to `value` when preparing engine inputs.
- `reference` must lie inside the uniform prior bounds.
- Parameter names are application identifiers. Symbols are the names
  exposed to the user expression.

`CosmicChronometerDatasetConfig`

- `data_path` is resolved to an absolute `Path` during normalization.
- The normalized manifest records the resolved path.
- Milestone 1 assumes uncorrelated errors for cosmic chronometers unless
  a later ADR adds covariance support.

`SamplerConfig`

- `seed` is mandatory for reproducibility.
- Only Cobaya MCMC is supported in milestone 1.

`RuntimeConfig`

- `output_root` defaults to `outputs/runs`.
- Each run creates its own isolated subdirectory under `output_root`.

### Recommended CLI YAML Contract

```yaml
schema_version: 1

model:
  kind: hz_expression_flat
  expression: H0 * sqrt(Om0 * (1 + z)**3 + (1 - Om0))
  expression_unit: km/s/Mpc
  redshift_symbol: z
  allowed_functions: [sqrt]

parameters:
  - name: H0
    symbol: H0
    role: sampled
    unit: km/s/Mpc
    prior: {lower: 50.0, upper: 90.0}
    reference: 70.0
    proposal: 1.0
  - name: Om0
    symbol: Om0
    role: sampled
    unit: null
    prior: {lower: 0.1, upper: 0.5}
    reference: 0.3
    proposal: 0.02

datasets:
  - kind: cosmic_chronometers
    data_path: data/cosmic_chronometers/example.csv

sampler:
  kind: cobaya_mcmc
  seed: 12345
  max_samples: 20000
  burn_in: 0
  learn_proposal: true
  Rminus1_stop: 0.01
  Rminus1_cl_stop: 0.2

runtime:
  run_label: flat-lcdm-cc
  output_root: outputs/runs
  overwrite: false
```

## Interfaces Between Cosmology, Likelihoods, and Cobaya

The core rule is that likelihoods must consume predictions through a
small scientific interface, not through Cobaya callbacks or UI objects.

### Domain Interfaces

```python
from collections.abc import Mapping
from typing import Protocol, TypeAlias
import numpy as np
from numpy.typing import NDArray

FloatArray: TypeAlias = NDArray[np.float64]
ParameterValues: TypeAlias = Mapping[str, float]


class HubbleRateProvider(Protocol):
    def hz(self, z: FloatArray, parameters: ParameterValues) -> FloatArray:
        """Return H(z) in km/s/Mpc for the requested redshifts."""


class Likelihood(Protocol):
    dataset_name: str

    def log_likelihood(
        self,
        provider: HubbleRateProvider,
        parameters: ParameterValues,
    ) -> float:
        """Return log-likelihood for one dataset."""
```

### Cosmology Package Public API

`cosmology.expression_parser`

- Parse a user expression into a validated internal expression tree.
- Accept only approved syntax.

`cosmology.expression_evaluator`

- Evaluate the internal expression tree on NumPy arrays.
- Reject `NaN`, infinite, complex, and non-positive `H(z)` outputs.

`cosmology.reference_models`

- Provide flat-LCDM reference formulas used in scientific tests.

Suggested public constructor:

```python
def build_hubble_rate_provider(
    model_config: ModelConfig,
    parameter_symbols: tuple[str, ...],
) -> HubbleRateProvider: ...
```

### Likelihood Package Public API

`likelihoods.datasets`

- Load the cosmic chronometer table from disk into validated NumPy
  arrays with explicit units.

`likelihoods.cosmic_chronometers`

- Implement the Gaussian log-likelihood over measured `H(z)` points.
- Require a `HubbleRateProvider`.

Suggested public constructor:

```python
def build_cosmic_chronometer_likelihood(
    dataset_config: CosmicChronometerDatasetConfig,
) -> Likelihood: ...
```

### Cobaya Adapter Boundary

The application layer passes only validated `RunConfig` and pure domain
objects into `cobaya_engine`.

Suggested application port:

```python
from pathlib import Path
from typing import Protocol


class InferenceEngine(Protocol):
    def run(self, run_config: RunConfig) -> Path:
        """Execute inference and return the run directory."""
```

`cobaya_engine` should implement:

- `config_builder.build_cobaya_input(run_config, likelihood_bundle)`
- `runner.run_in_subprocess(run_config, cobaya_payload)`
- `worker.main()` for the Cobaya child process

Cobaya-specific parameter dictionaries and likelihood callables exist
only inside `cobaya_engine`.

### Translation Strategy

1. `application.loaders` reads YAML into raw Python data.
2. `application.validation` converts raw data into `RunConfig`.
3. `application.services` builds:
   - one `HubbleRateProvider`;
   - one or more `Likelihood` instances.
4. `application.services` passes `RunConfig` and those scientific
   objects into `cobaya_engine`.
5. `cobaya_engine.config_builder` translates sampled and fixed
   parameters into Cobaya parameter definitions.
6. `cobaya_engine` wraps the pure likelihood bundle in a Cobaya
   likelihood callable.
7. `cobaya_engine.runner` launches `worker.py` in a separate process.

## Dependency Direction

The allowed dependency graph for milestone 1 is:

```text
cli -> application -> cosmology
                  -> likelihoods
                  -> cobaya_engine

ui -> application   (future milestone only)
analysis -> outputs produced by cobaya_engine   (future milestone only)
```

Import rules:

- `cosmology` imports only standard library, NumPy, and internal domain
  helpers.
- `likelihoods` may import NumPy, SciPy, and `cosmology` protocols if
  needed, but never Cobaya or PySide6.
- `application` may import `cosmology`, `likelihoods`, and
  `cobaya_engine`.
- `cobaya_engine` may import `application` models and scientific
  interfaces, but no other package may import Cobaya.
- `ui` must not be imported anywhere in milestone 1 runtime.

Static checks recommended for milestone 1:

- one test that scans imports to verify `PySide6` is confined to `ui`;
- one test that scans imports to verify `cobaya` is confined to
  `cobaya_engine`.

## Reproducible Run and Artifact Layout

Each command-line run should produce:

```text
outputs/runs/<run-label>-<timestamp-or-uuid>/
  input.yaml
  normalized_config.json
  cobaya_input.yaml
  status.json
  metadata.json
  logs/
    cli.log
    worker.log
    cobaya.stdout.log
    cobaya.stderr.log
  chains/
```

Required artifact behavior:

- Copy the original user YAML as `input.yaml`.
- Write a normalized, fully resolved manifest as `normalized_config.json`.
- Preserve the generated Cobaya input file exactly as executed.
- Persist a machine-readable `status.json` with states such as
  `pending`, `running`, `succeeded`, and `failed`.
- Persist Python, NumPy, Cobaya, and CosmoFit version metadata.
- Never reuse another run's directory.

This layout is the primary mechanism for reproducibility, debugging, and
later GetDist analysis.

## Testability Strategy

Recommended test layout:

```text
tests/
  unit/
    application/
    cosmology/
    likelihoods/
    cobaya_engine/
  integration/
    cli/
    cobaya_engine/
  fixtures/
    datasets/
    run_configs/
```

Required milestone 1 test categories:

- parser unit tests for accepted and rejected `H(z)` syntax;
- evaluator unit tests for invalid numeric outputs;
- flat-LCDM scientific checks against independent reference values;
- cosmic chronometer likelihood tests for nominal and malformed data;
- application validation tests for prior bounds, fixed vs sampled
  parameters, and required units;
- Cobaya adapter tests that verify generated parameter blocks and run
  artifact creation;
- one CLI integration test for a validated run config;
- one failure-path integration test that confirms logs and `status.json`
  are preserved when the worker fails.

## Milestone 1 Acceptance Criteria

Milestone 1 is complete when all of the following are true:

1. The repository contains a command-line entrypoint under
   `src/cosmofit/cli`.
2. A YAML run file can be loaded into validated dataclass models in
   `application`.
3. The only accepted model form is a flat `H(z)` expression with
   explicit `km/s/Mpc` units.
4. The cosmology layer rejects undeclared symbols, forbidden syntax,
   `NaN`, infinite, complex, and non-positive `H(z)` predictions.
5. The cosmic chronometer likelihood is implemented as a pure class that
   depends only on the `HubbleRateProvider` interface.
6. `cobaya_engine` is the only package importing Cobaya.
7. Cobaya runs in a separate process with a unique run directory, saved
   generated config, and persistent logs/status on success and failure.
8. Uniform priors, fixed parameters, and sampled parameters are all
   translated correctly into Cobaya input.
9. Every scientific formula introduced for milestone 1 has a unit test.
10. Flat-LCDM milestone reference calculations are tested against an
    independent calculation source or independently derived reference
    values.
11. No milestone 1 runtime code imports PySide6 outside `ui`.
12. `pytest` passes for the milestone 1 test set.
13. Packaging and lint configuration are aligned to Python 3.12 before
    the first production implementation is merged.

## Scientific Risks

`H(z)` unit ambiguity

- Risk: accepting both `H(z)` and `E(z)` in the first milestone can
  silently shift responsibility for `H0`.
- Mitigation: milestone 1 accepts `H(z)` only and requires
  `expression_unit = "km/s/Mpc"`.

Invalid but numerically finite models

- Risk: a user expression can be finite at some redshifts and still be
  physically invalid elsewhere.
- Mitigation: validate positivity and finiteness over every redshift
  requested by the active dataset and fail fast on violation.

Reference-model drift

- Risk: the user-expression path may pass tests while the scientific
  interpretation of a flat-LCDM baseline drifts.
- Mitigation: keep explicit flat-LCDM reference formulas in
  `cosmology.reference_models` and compare against independent values.

Dataset contract mismatch

- Risk: malformed cosmic chronometer tables can be interpreted with
  wrong columns or wrong units.
- Mitigation: require explicit column schema, validate monotonic
  redshift ordering if assumed, and reject negative uncertainties.

## Security Risks

Parser breakout through Python evaluation

- Risk: string-based evaluation or symbolic parsing helpers may execute
  Python code.
- Mitigation: do not use `eval`, `exec`, `sympy.parse_expr`, or
  `sympy.lambdify` for user expressions. Parse with Python `ast` in
  expression mode, validate nodes, and evaluate through a closed NumPy
  function map.

Access to undeclared identifiers or attributes

- Risk: expressions such as `os.system(...)`, `a.__class__`, or
  `x[0]` can become a code-execution or data-leak vector.
- Mitigation: forbid attribute access, subscripting, comprehensions,
  lambdas, assignments, imports, and all calls except approved bare
  math-function names.

Silent path injection through datasets

- Risk: run configs can point outside intended data locations or produce
  inconsistent normalized manifests.
- Mitigation: resolve dataset paths with `pathlib.Path`, store resolved
  paths in the manifest, and surface the resolved locations in logs.

Cobaya process contamination

- Risk: in-process Cobaya execution can pollute interpreter state and
  make failures hard to recover from.
- Mitigation: launch a worker subprocess and treat the run directory as
  the boundary of record for status and artifacts.

Environment contract drift

- Risk: repository metadata that still targets Python 3.11 can hide
  version-specific behavior until packaging, CI, or user installs fail.
- Mitigation: update packaging and lint targets to Python 3.12 before
  implementation work begins, and keep the declared interpreter target
  synchronized with project rules.
