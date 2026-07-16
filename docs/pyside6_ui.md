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

## Window sizing

The main desktop window now uses these practical size targets:

- initial size: `1200x800`
- minimum practical size: `800x600`

Responsive behavior is implemented in the tab content instead of relying on a
large main-window minimum:

- the `Model`, `Datasets`, and `Sampler` pages live inside `QScrollArea`
  containers with `widgetResizable=True`;
- the `Parameters` and posterior summary tables use interactive headers and
  horizontal scrollbars instead of stretching every column to the window width;
- the `Results` page uses responsive action grids, scrollable metadata content,
  a scrollable content area, a resizable splitter layout, and a scaled PNG
  preview that preserves the original export files;
- Results action buttons keep their natural height after a plot preview loads;
- the plot metadata pane wraps long paths and scrolls instead of forcing the
  preview or action rows to collapse;
- the preview shrinks with `KeepAspectRatio` before the action area loses
  usable height.

The `Results` tab is an inactive placeholder for the next milestone.

Validation is performed by building the existing application
configuration models and reusing backend validation. The UI does not
evaluate cosmological expressions itself, does not call Cobaya
execution, and does not import GetDist directly.

## LCDM example

Use `Load LCDM example` to populate the form with the predefined
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
- Results loading, GetDist plots, and summary tables are not implemented in
  this milestone snapshot.
- `use_abs_mag` remains fixed to `false`.
- The current chronometer example points to the repository fixture CSV.

## Next milestone

Execution, run monitoring, and post-run analysis are added in the next
UI milestone.
