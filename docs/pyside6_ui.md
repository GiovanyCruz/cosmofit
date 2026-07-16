# PySide6 UI Milestone 1

## Launch

Use:

```bash
python -m cosmofit.ui
```

For headless testing:

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ui/test_ui_milestone.py
```

## Current functionality

This first desktop milestone provides a usable PySide6 window for
defining and validating a CosmoFit run configuration without starting
Cobaya yet.

The window contains five tabs:

- `Model`
- `Parameters`
- `Datasets`
- `Sampler`
- `Results`

The `Results` tab is an inactive placeholder for the next milestone.

Validation is performed by building the existing application
configuration models and reusing backend validation. The UI does not
evaluate cosmological expressions itself, does not call Cobaya
execution, and does not import GetDist directly.

## LCDM example

Use `Cargar ejemplo LCDM` to populate the form with the predefined
flat LCDM example:

- `H(z) = H0*sqrt(Om*(1+z)**3 + 1-Om)`
- `H0` sampled
- `Om` sampled
- flat geometry
- `cosmic chronometers` selected

In the repository development environment, the example uses the
synthetic chronometer CSV fixture already present under `tests/fixtures`.

## Save and open

Projects are saved as JSON using the existing normalized application
configuration format produced by `serialize_run_config`.

The project file preserves:

- parameter order;
- dataset selections;
- sampler settings;
- runtime settings.

It does not store generated chains or other run artifacts.

## Current limitations

- The UI validates configuration only; it does not start or stop Cobaya.
- There is no progress monitoring or background execution yet.
- Results loading, GetDist plots, and summary tables are not implemented.
- `use_abs_mag` remains fixed to `false`.
- The current chronometer example points to the repository fixture CSV.

## Next milestone

Execution, run monitoring, and post-run analysis are added in the next
UI milestone.
