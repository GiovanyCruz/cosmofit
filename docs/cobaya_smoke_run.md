# Cobaya Smoke Run

Milestone 1 exposes a predefined command-line smoke run:

```bash
python -m cosmofit.cobaya_engine.smoke_run
```

Behavior:

- runs a short flat-LCDM MCMC with `H0` and `Om`;
- uses the synthetic cosmic chronometer fixture in
  `tests/fixtures/cosmic_chronometers_synth.csv`;
- creates an isolated run directory under `outputs/smoke_cc_lcdm/`;
- saves `input.yaml`, `normalized_config.json`, `cobaya_input.yaml`,
  `status.json`, `summary.json`, logs, and Cobaya chain outputs.

This smoke run is only for integration validation. It is not a
scientific result.
