# ADR 0002: Reproducible Run Configuration

## Status

Accepted

## Context

CosmoFit must produce reproducible Cobaya runs and preserve enough
artifacts to debug failures. The user provides model definitions,
parameter settings, datasets, and sampler configuration.

## Decision

Milestone 1 uses a single YAML run file as the user-facing input
contract. The CLI validates that file into immutable dataclass models in
`application.config_models`.

Required configuration decisions:

- `schema_version` is mandatory.
- `seed` is mandatory for Cobaya MCMC runs.
- model input is limited to `H(z)` expressions in `km/s/Mpc`.
- parameter roles are limited to `fixed` and `sampled`.
- prior type is limited to `uniform`.
- dataset type is limited to `cosmic_chronometers`.

Each run writes an isolated artifact directory containing:

- the original YAML input;
- a normalized manifest with resolved paths;
- the generated Cobaya YAML;
- machine-readable status and metadata;
- stdout/stderr and worker logs;
- chain outputs.

## Consequences

- Reruns are reproducible from preserved artifacts.
- Validation errors occur before Cobaya starts.
- Future schema changes must be versioned deliberately.
- Users see the exact Cobaya input that was executed.
