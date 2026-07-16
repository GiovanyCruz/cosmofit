# UI Cobaya Execution

## Architecture

This milestone keeps the package boundary from `AGENTS.md`:

```text
ui -> application services -> domain/cosmology
                           -> likelihoods
                           -> cobaya adapter
```

The desktop UI builds and validates a `RunConfig`, then hands it to a
Qt execution controller. The controller does not import Cobaya. It
prepares a worker request through `cosmofit.application.execution`,
launches a separate Python process, streams stdout/stderr, and reacts to
structured lifecycle events.

The worker entry point is `cosmofit.application.run_worker`. That module
re-loads the normalized configuration, validates it again through the
application layer, and then delegates to `cosmofit.cobaya_engine.worker`
for real Cobaya execution.

## Launch Commands

Launch the desktop UI with:

```bash
python -m cosmofit.ui
```

The worker command used by the UI is:

```bash
python -m cosmofit.application.run_worker <temporary-worker-request.json>
```

The worker request is a temporary JSON file created by the execution
controller. It points to the prepared run directory, normalized config,
Cobaya input, status file, summary file, log files, and chain prefix.

## Lifecycle States

The UI presents these states:

- `Idle`
- `Validating`
- `Starting`
- `Running`
- `Cancelling`
- `Completed`
- `Failed`
- `Cancelled`

The worker persists machine-readable status transitions in
`status.json`. Success is not based on process launch alone. A run is
treated as successful only when:

- the worker exits with code `0`;
- `status.json` reports `state="succeeded"`;
- `summary.json` exists;
- `chains/chain.updated.yaml` exists;
- at least one `chains/chain.N.txt` file exists.

## Logs

The Results tab contains the execution log panel.

- stdout and stderr are buffered in memory and flushed into the widget in
  short timer-driven batches.
- stderr lines are prefixed in the UI.
- the log view auto-scrolls to the newest line.
- the widget document retains at most the most recent 5000 lines.
- `Clear log` clears only the in-memory UI view.
- full technical logs remain on disk under `logs/`.

The worker also emits structured JSON-line events on stdout with the
`COSMOFIT_EVENT ` prefix. The UI uses those events for lifecycle updates
and final run-directory tracking.

## Cancellation

The UI first requests graceful termination through `QProcess.terminate()`
and then escalates to `QProcess.kill()` after a bounded timeout if the
worker does not stop.

- the controller updates the UI to `Cancelling` before signalling the
  process;
- `Cancel run` is disabled immediately after the first request;
- no blocking `waitForFinished`, `waitForStarted`, or
  `waitForReadyRead` call is used from the GUI thread.

On macOS, `terminate()` maps to `SIGTERM` and `kill()` maps to a forced
kill. Cancellation never marks a run as successful, and partial output
is intentionally left on disk for diagnosis.

Closing the main window during an active run prompts for confirmation.
If the user confirms, the UI cancels the worker and closes only after
the child process reaches a terminal state.

## Output Directories

The sampler form still stores an output root in the project state. For
desktop execution, CosmoFit creates a managed timestamped run directory
inside that root using the run label plus a UTC timestamp.

The Results tab shows the final run directory reported by the worker.
`Open output folder` is enabled only when that directory exists and is
still inside the configured output root.

Folder opening uses `QDesktopServices.openUrl(QUrl.fromLocalFile(...))`.
No shell command is constructed from paths.

## Results Placeholder

This milestone does not load GetDist plots yet.

After a successful run, the Results tab stores and shows:

- run label;
- completion state;
- final run directory;
- selected datasets;
- sampled parameter names.

The tab also states that posterior loading is the next milestone.

## Test Commands

Focused execution tests:

```bash
QT_QPA_PLATFORM=offscreen pytest \
  tests/ui/test_execution_controller.py \
  tests/ui/test_execution_window.py -q
```

All UI tests:

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ui -q
```

Real Cobaya smoke path through the blocking runner:

```bash
pytest tests/cobaya_engine/test_smoke_run.py -q
```

Optional real UI execution smoke test:

```bash
QT_QPA_PLATFORM=offscreen COSMOFIT_RUN_UI_SMOKE=1 \
pytest tests/ui/test_execution_integration_smoke.py -q
```

## Current Limitations

- GetDist plot rendering is still pending.
- Posterior tables are still pending.
- Only one active run is supported.
- There is no remote execution or resumable MCMC.
- The desktop UI still saves the configured output root in project JSON;
  the final managed run directory is created at execution time.
- The test bootstrap now sets `LC_ALL` and `LANG` to `en_US.UTF-8`
  automatically because this macOS Qt environment crashes under the
  default `C` locale during headless UI runs.
