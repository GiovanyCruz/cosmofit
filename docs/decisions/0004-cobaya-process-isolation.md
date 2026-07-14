# ADR 0004: Cobaya Process Isolation

## Status

Accepted

## Context

Cobaya execution can fail due to model errors, sampler configuration,
filesystem issues, or third-party library behavior. The architecture
must isolate Cobaya from the parent application process and preserve
debug artifacts.

## Decision

Milestone 1 runs Cobaya in a dedicated worker subprocess launched from
`cobaya_engine.runner`.

Process design:

- the parent CLI validates configuration and creates the run directory;
- the parent writes the normalized manifest and generated Cobaya input;
- the parent launches `python -m cosmofit.cobaya_engine.worker`;
- the worker imports Cobaya and executes the run;
- the worker updates `status.json` and writes logs on success or failure.

Only `cobaya_engine` may import Cobaya or define Cobaya-specific
callables.

## Consequences

- Parent-process state stays clean after worker failure.
- Run directories become the source of truth for diagnostics.
- The architecture gains a stable seam for future cancellation and job
  monitoring work.
- More serialization and status-handling code is required up front.
