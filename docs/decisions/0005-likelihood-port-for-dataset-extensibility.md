# ADR 0005: Likelihood Port for Dataset Extensibility

## Status

Accepted

## Context

Milestone 1 starts with cosmic chronometers, but the project scope will
expand to additional datasets. If the first likelihood implementation is
coupled directly to Cobaya or to one concrete cosmology class, future
dataset work will be harder and riskier.

## Decision

Likelihood classes will depend on a narrow scientific interface:

```python
class HubbleRateProvider(Protocol):
    def hz(self, z: FloatArray, parameters: ParameterValues) -> FloatArray: ...
```

Each likelihood:

- loads and validates its own dataset configuration;
- requests only the predictions it needs through explicit interfaces;
- returns a scalar log-likelihood;
- remains free of Cobaya imports and callback assumptions.

`cobaya_engine` is responsible only for adapting Cobaya parameter input
into calls to the pure likelihood bundle.

## Consequences

- Cosmic chronometers can be implemented and tested without Cobaya.
- New datasets can add new protocols only when scientifically necessary.
- Future Pantheon+ support can be added alongside cosmic chronometers
  instead of rewriting the first likelihood.
