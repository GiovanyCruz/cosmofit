# ADR 0006: Defer E(z) Support Until a Separate Model Contract

## Status

Accepted

## Context

The product direction allows users to define either `H(z)` or `E(z)`,
but the first implementation milestone is intentionally narrow:

- flat cosmology only;
- cosmic chronometers only;
- uniform priors only;
- Cobaya MCMC only;
- command-line execution only.

Supporting both `H(z)` and `E(z)` immediately would force an early
decision about where `H0` enters the model contract. That ambiguity
affects units, parameter ownership, validation, and how the expression
maps into likelihood predictions.

## Decision

Milestone 1 accepts only `H(z)` expressions with explicit units of
`km/s/Mpc`.

`E(z)` is deferred until a later milestone and must be introduced as a
separate model kind, not as a flag or overloaded variant of the
`H(z)` contract.

That future `E(z)` design must define explicitly:

- how `H0` is provided and validated;
- whether `H0` is mandatory, fixed, or sampled;
- how `E(z)` is converted into `H(z)` for dataset likelihoods;
- which units remain user-visible at the configuration boundary.

## Consequences

- Milestone 1 keeps one unambiguous scientific contract for the model
  expression layer.
- The parser, validator, and likelihood interfaces stay simpler for the
  first end-to-end implementation.
- Future `E(z)` support remains possible, but requires a deliberate
  schema and architecture update instead of incremental ad hoc growth.
