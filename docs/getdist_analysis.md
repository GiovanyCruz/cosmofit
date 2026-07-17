# GetDist Analysis Workflow

CosmoFit analyzes completed Cobaya runs from the run directory produced by
`cosmofit.cobaya_engine.runner`.

## Supported Run-Directory Structure

The analysis layer expects a completed run directory with the current
CosmoFit artifact layout:

```text
<run-directory>/
  input.yaml
  normalized_config.json
  cobaya_input.yaml
  updated_cobaya_input.yaml
  summary.json
  status.json
  metadata.json
  logs/
    worker.log
    cobaya.stdout.log
    cobaya.stderr.log
  chains/
    chain.1.txt
    chain.input.yaml
    chain.updated.yaml
    chain.checkpoint
    chain.progress
    chain.covmat
```

`status.json` is the authoritative completion signal. Analysis rejects
run directories unless `status.json` contains `state: succeeded`.

## Chain-Root Discovery

The current Cobaya runner writes its managed root at `chains/chain`.
Analysis validates that root and requires:

- `chains/chain.updated.yaml`
- one or more chain files matching `chains/chain.<n>.txt`
- a successful `status.json`

Unrelated files under `chains/` are ignored unless they form a second
valid chain root. When multiple valid chain roots exist, analysis fails
with a clear error instead of guessing.

## Burn-In Handling

`PosteriorAnalysisService` accepts `ignore_rows` as a fraction in
`[0, 1)`. The default is `0.0`, which is appropriate for completed
CosmoFit runs because Cobaya burn-in is already controlled at run time.

The selected `ignore_rows` value is preserved in:

- exported `summary.json`
- exported `summary.csv`
- in-memory diagnostics returned by the analysis service

## Parameter Selection

Selectable parameters are the sampled posterior dimensions reported by
GetDist, excluding fixed parameters and derived parameters.

- `plot_1d(parameter)` requires exactly one valid sampled parameter.
- `plot_2d(parameter_x, parameter_y)` requires two distinct valid
  sampled parameters.
- `triangle_plot(parameters)` accepts any non-empty sampled subset.
- User-selected ordering is preserved.
- Unknown or duplicate parameter selections are rejected explicitly.

Derived parameters such as `chi2` remain visible through
`parameter_metadata()` and are marked as `derived`, but they are not
accepted by the sampled-parameter plotting methods.

## Output Files

Analysis writes its own managed outputs under:

```text
<run-directory>/analysis/getdist/
  summary.json
  summary.csv
  plots/
    1d_<parameter>.png
    1d_<parameter>.pdf
    2d_<x>_<y>.png
    2d_<x>_<y>.pdf
    triangle_<ordered-parameters>.png
    triangle_<ordered-parameters>.pdf
```

Nothing is written back into `chains/`.

## Plot Types

- 1D plots show marginalized density for one sampled parameter.
- 2D plots show marginalized confidence contours for two sampled
  parameters.
- Triangle plots combine 1D and 2D marginals for any selected subset.
- User-provided plot titles are applied as figure-level suptitles for
  1D, 2D, and triangle plots, with reserved top margin for preview,
  PNG, and PDF exports.
- Triangle legends are rendered as figure-level legends in reserved
  whitespace outside the scientific axes so they do not cover diagonal
  densities or contour panels.

For many parameters, triangle plots preserve the requested order and
scale naturally beyond two or three dimensions. This milestone does not
assume a fixed parameter count.

## Command-Line Smoke Utility

Analyze an existing completed run:

```bash
python -m cosmofit.analysis.smoke_run /path/to/run
```

Select a triangle subset explicitly:

```bash
python -m cosmofit.analysis.smoke_run /path/to/run --parameters H0,Om,w0
```

Apply additional row skipping on load:

```bash
python -m cosmofit.analysis.smoke_run /path/to/run --ignore-rows 0.1
```

The utility:

- creates `<run-directory>/analysis/getdist/`
- exports `summary.json`
- exports `summary.csv`
- exports a 1D plot for each available sampled parameter
- exports a triangle plot when at least two selected parameters exist
- prints every generated output path
