# UI GetDist Results

## Architecture

The results flow keeps the package boundary from `AGENTS.md`:

```text
ui -> application services -> analysis
```

- `cosmofit.ui.results_widget` owns only Qt widgets, user interaction, and
  PNG preview rendering.
- `cosmofit.ui.results_controller` runs loading, plotting, and export work in
  background `QThread` tasks.
- `cosmofit.application.posterior_results_service` is the UI-facing facade for
  posterior loading, summary refresh, plot generation, and exports.
- `cosmofit.analysis.PosteriorAnalysisService` remains the only GetDist-aware
  layer.

The UI does not import GetDist or Cobaya directly.

## Load A Run

The Results tab supports two entrypoints:

- `Load latest completed run`
- `Open run directory` + `Load`

Runs are validated through the existing analysis locator and status artifacts.
CosmoFit rejects failed, cancelled, malformed, or incomplete runs before
loading summaries or plots.

## Automatic Handoff From Execution

After a successful UI execution:

- the final managed run directory is stored;
- the Results tab remains enabled;
- `Load latest completed run` points to that completed directory;
- heavy posterior analysis is not started automatically.

Failed or cancelled executions are not promoted as completed posterior results.

## Parameter Selection

The Results tab uses a multi-selection list of posterior parameters.

- `Select all`
- `Clear selection`
- `Invert selection`

Validation rules:

- Select exactly one parameter for a `Plot 1D`.
- Select exactly two parameters for a `Plot 2D`.
- Select at least two parameters for a `Triangle plot`.

Displayed order follows the analysis metadata order. Derived parameters stay in
the summary table and are marked as derived, but fixed parameters are not
treated as sampled posterior columns.

## Credible Levels

The summary table supports:

- `68%`
- `95%`

The analysis service loads both supported levels and the table switches between
their lower and upper limits safely in the UI.

## Ignore Initial Fraction

`Ignore initial fraction` is configured from the Results tab as a fraction in
`[0, 1)`.

- `0.0` means no extra row skipping beyond the Cobaya run configuration.
- The selected value is preserved in exported summary metadata.

## Plot Generation

Plot options:

- credible levels
- `Ignore initial fraction`
- plot title with Matplotlib MathText support
- optional filled contours
- optional legend label with Matplotlib MathText support

MathText behavior:

- CosmoFit uses Matplotlib MathText by default.
- `text.usetex` remains disabled by default.
- No system LaTeX installation is required.
- Raw user-entered strings are preserved in project files.
- Internal parameter symbols stay unchanged even when display labels use
  MathText, for example `Om` with display label `$\Omega_m$`.
- The analysis layer validates plot titles, legend labels, and selected
  parameter display labels before exporting PNG/PDF artifacts.
- Invalid MathText does not crash the UI or worker thread. The Results tab
  shows a clear English message and the Results log keeps the full traceback
  with Matplotlib parser details.

Supported editable fields:

- plot title
- legend label
- parameter display label

Preview behavior:

- the Results tab renders small title and legend previews under each field;
- the Parameters tab renders a small preview under each display-label edit;
- previews use the same Matplotlib MathText engine as final plot exports.

Example labels:

- `$H_0$`
- `$\Omega_m$`
- `$\Lambda$CDM`
- `$w_0$`
- `$w_a$`

Plot rendering flow:

1. the widget builds a `PosteriorPlotRequest`;
2. the controller runs the request in a background thread;
3. the application facade calls `PosteriorAnalysisService`;
4. GetDist exports managed PNG/PDF artifacts;
5. the UI loads the PNG preview into the Results tab.

Figures are closed in the analysis layer and the UI only handles the exported
files.

The same validated text is used for PNG preview rendering and PDF export, so
both formats keep matching titles and labels.

## Exports

Supported exports:

- summary JSON
- summary CSV
- current plot PNG
- current plot PDF

The UI uses `QFileDialog` and asks before overwriting an existing target.
Exports are written only to the user-selected destination.

## Headless Test Commands

Focused posterior/UI tests:

```bash
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 QT_QPA_PLATFORM=offscreen \
MPLCONFIGDIR=/private/tmp/mpl \
pytest tests/analysis/test_posterior_analysis_service.py \
  tests/application/test_posterior_results_service.py \
  tests/ui/test_results_widget.py \
  tests/ui/test_execution_window.py -q
```

All UI tests:

```bash
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 QT_QPA_PLATFORM=offscreen \
MPLCONFIGDIR=/private/tmp/mpl \
pytest tests/ui -q
```

Optional threaded controller tests:

```bash
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 QT_QPA_PLATFORM=offscreen \
MPLCONFIGDIR=/private/tmp/mpl COSMOFIT_RUN_RESULTS_CONTROLLER_TESTS=1 \
pytest tests/ui/test_results_controller.py -q
```

## Optional Real Smoke Test

Run the real UI execution smoke path:

```bash
LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 QT_QPA_PLATFORM=offscreen \
COSMOFIT_RUN_UI_SMOKE=1 pytest tests/ui/test_execution_integration_smoke.py -q
```

## Current Limitations

- The threaded controller tests are skipped by default because this Python 3.13
  Qt environment can segfault inside threaded `pytest` runs.
- The Results tab currently supports one loaded run at a time.
- Multiple-run comparison, live-chain plotting, remote runs, and convergence
  dashboards remain out of scope.
