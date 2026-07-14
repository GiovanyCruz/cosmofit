# ADR 0001: Package Boundaries and Dependency Direction

## Status

Accepted

## Context

CosmoFit must keep scientific code independent from PySide6 and keep
Cobaya-specific objects inside `cobaya_engine`. The current repository
already contains the package skeleton:

- `cosmology`
- `likelihoods`
- `cobaya_engine`
- `analysis`
- `ui`

Milestone 1 also needs a command-line entrypoint and an application
layer that owns configuration and orchestration.

## Decision

Milestone 1 introduces two new packages:

- `src/cosmofit/application`
- `src/cosmofit/cli`

Dependency direction is:

```text
cli -> application -> cosmology
                  -> likelihoods
                  -> cobaya_engine

ui -> application   (future only)
analysis -> run artifacts   (future only)
```

Boundary rules:

- `cosmology` and `likelihoods` never import `PySide6` or `cobaya`.
- `cobaya_engine` is the only package allowed to import `cobaya`.
- `ui` is not part of milestone 1 runtime.
- `application` owns public configuration models, validation, and
  orchestration use cases.
- `likelihoods` depend on explicit scientific interfaces, not on
  Cobaya callback shapes.

## Consequences

- Milestone 1 stays testable without a GUI.
- Scientific logic can be tested without Cobaya.
- Future UI work can reuse the same `application` services as the CLI.
- Import-boundary tests should be added to prevent architectural drift.
