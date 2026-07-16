"""Headless tests for the Qt execution controller."""

from __future__ import annotations

import json
import sys
import textwrap
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from cosmofit.application import PreparedRunExecution, WorkerRequest
from cosmofit.application.examples import build_lcdm_example_run_config
from cosmofit.cobaya_engine.artifacts import RunArtifacts
from cosmofit.ui import execution_controller as execution_controller_module
from cosmofit.ui.execution_controller import (
    STATE_CANCELLED,
    STATE_CANCELLING,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_IDLE,
    ExecutionController,
)


def test_execution_controller_initial_state() -> None:
    controller = ExecutionController()

    state = controller.execution_state()

    assert state.state == STATE_IDLE
    assert state.active is False
    assert state.run_directory is None


def test_execution_controller_handles_success(monkeypatch, tmp_path: Path) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import sys
        import time
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        run_directory = request["run_directory"]
        status_path = Path(request["status_path"])
        print(
            "COSMOFIT_EVENT "
            '{"event":"running","message":"running","run_directory":"%s"}'
            % run_directory,
            flush=True,
        )
        print("stdout line", flush=True)
        print("stderr line", file=sys.stderr, flush=True)
        time.sleep(0.1)
        status_path.write_text(
            json.dumps({"state": "succeeded", "run_directory": run_directory}),
            encoding="utf-8",
        )
        print(
            'COSMOFIT_EVENT {"event":"completed","message":"done","run_directory":"%s"}'
            % run_directory,
            flush=True,
        )
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )
    logs: list[tuple[str, str]] = []
    completions: list[str] = []
    controller.log_message.connect(lambda stream, line: logs.append((stream, line)))
    controller.completed.connect(completions.append)

    started = controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    assert started is True
    _spin_until(lambda: bool(completions), app)

    assert controller.execution_state().state == STATE_COMPLETED
    assert any(line == ("stdout", "stdout line") for line in logs)
    assert any(line == ("stderr", "stderr line") for line in logs)
    assert completions == [str(prepared.artifacts.run_directory)]
    assert not prepared.request_path.exists()


def test_execution_controller_rejects_concurrent_starts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import signal
        import sys
        import time
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        status_path = Path(request["status_path"])
        status_path.write_text(
            json.dumps(
                {
                    "state": "running",
                    "run_directory": request["run_directory"],
                }
            ),
            encoding="utf-8",
        )
        signal.signal(signal.SIGTERM, lambda *_args: sys.exit(130))
        while True:
            time.sleep(0.1)
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(
        cancellation_timeout_ms=100,
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )

    assert controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    assert (
        controller.start_run(
            build_lcdm_example_run_config(output_directory=tmp_path / "output")
        )
        is False
    )
    _spin_until(lambda: prepared.artifacts.status_path.exists(), app)
    controller.cancel_run()
    _spin_until(lambda: controller.execution_state().state == STATE_CANCELLED, app)


def test_execution_controller_handles_malformed_status(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import sys
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        Path(request["status_path"]).write_text("{not-json", encoding="utf-8")
        print(
            'COSMOFIT_EVENT {"event":"completed","message":"done","run_directory":"%s"}'
            % request["run_directory"],
            flush=True,
        )
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )
    failures: list[str] = []
    controller.failed.connect(failures.append)

    assert controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    _spin_until(lambda: bool(failures), app)

    assert controller.execution_state().state == STATE_FAILED
    assert "invalid" in failures[0].lower()


def test_terminal_event_does_not_unlock_before_process_exit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import sys
        import time
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        run_directory = request["run_directory"]
        status_path = Path(request["status_path"])
        print(
            'COSMOFIT_EVENT {"event":"completed","message":"done","run_directory":"%s"}'
            % run_directory,
            flush=True,
        )
        time.sleep(0.5)
        status_path.write_text(
            json.dumps({"state": "succeeded", "run_directory": run_directory}),
            encoding="utf-8",
        )
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )

    assert controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    time.sleep(0.1)
    app.processEvents()

    assert controller.has_active_run() is True
    assert controller.execution_state().state == "Starting"

    _spin_until(lambda: controller.execution_state().state == STATE_COMPLETED, app)


def test_execution_controller_cancels_and_force_kills(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import signal
        import sys
        import time
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        Path(request["status_path"]).write_text(
            json.dumps(
                {
                    "state": "running",
                    "run_directory": request["run_directory"],
                }
            ),
            encoding="utf-8",
        )
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(0.1)
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    controller = ExecutionController(
        cancellation_timeout_ms=50,
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )

    assert controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    _spin_until(lambda: prepared.artifacts.status_path.exists(), app)
    assert controller.cancel_run() is True
    _spin_until(lambda: controller.execution_state().state == STATE_CANCELLED, app)

    assert controller.execution_state().state == STATE_CANCELLED
    assert not prepared.request_path.exists()


def test_execution_controller_cancel_stays_responsive_and_force_kills(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script_path = _write_worker_script(
        tmp_path,
        """
        import json
        import signal
        import sys
        import time
        from pathlib import Path

        request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        Path(request["status_path"]).write_text(
            json.dumps(
                {
                    "state": "running",
                    "run_directory": request["run_directory"],
                }
            ),
            encoding="utf-8",
        )
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        line = "x" * 512
        while True:
            print(line, flush=True)
            print(line, file=sys.stderr, flush=True)
            time.sleep(0.005)
        """,
    )
    prepared = _prepared_run(tmp_path)
    monkeypatch.setattr(
        execution_controller_module,
        "prepare_worker_request",
        lambda _run_config: prepared,
    )

    app = QApplication.instance() or QApplication([])
    force_kill_calls: list[float] = []

    class TrackingExecutionController(ExecutionController):
        def _force_kill(self) -> None:  # noqa: PLW3201
            force_kill_calls.append(time.monotonic())
            super()._force_kill()

    controller = TrackingExecutionController(
        cancellation_timeout_ms=75,
        worker_program=sys.executable,
        worker_arguments_builder=lambda path: [str(script_path), str(path)],
    )

    assert controller.start_run(
        build_lcdm_example_run_config(output_directory=tmp_path / "output")
    )
    _spin_until(lambda: prepared.artifacts.status_path.exists(), app)

    start_timer_fired = {"value": False}
    QTimer.singleShot(0, lambda: _set_flag(start_timer_fired))
    _spin_until(lambda: start_timer_fired["value"], app)

    assert controller.cancel_run() is True
    assert controller.execution_state().state == STATE_CANCELLING
    assert controller.cancel_run() is False

    cancel_timer_fired = {"value": False}
    QTimer.singleShot(0, lambda: _set_flag(cancel_timer_fired))
    _spin_until(lambda: cancel_timer_fired["value"], app)

    _spin_until(lambda: controller.execution_state().state == STATE_CANCELLED, app)

    assert force_kill_calls
    assert controller.execution_state().state == STATE_CANCELLED
    assert not prepared.request_path.exists()


def test_cancel_request_does_not_mask_backend_failure(tmp_path: Path) -> None:
    controller = ExecutionController()
    run_directory = tmp_path / "failed-run"
    controller._state = execution_controller_module.ExecutionState(  # noqa: SLF001
        state="Cancelling",
        active=True,
        run_directory=run_directory,
        output_root=tmp_path,
    )
    controller._cancellation_requested = True  # noqa: SLF001
    controller._pending_terminal_event = ("failed", "backend failed")  # noqa: SLF001
    controller._load_status_payload = lambda: {  # type: ignore[method-assign]  # noqa: SLF001
        "state": "failed",
        "message": "backend failed",
        "run_directory": str(run_directory),
    }

    terminal_state, message = controller._finalize_process_result(1)  # noqa: SLF001

    assert terminal_state == STATE_FAILED
    assert message == "backend failed"


def _prepared_run(tmp_path: Path) -> PreparedRunExecution:
    run_directory = tmp_path / "run"
    logs_directory = run_directory / "logs"
    chains_directory = run_directory / "chains"
    logs_directory.mkdir(parents=True)
    chains_directory.mkdir(parents=True)
    request_path = tmp_path / "request.json"
    status_path = run_directory / "status.json"
    request_path.write_text(
        json.dumps(
            {
                "run_directory": str(run_directory),
                "status_path": str(status_path),
            }
        ),
        encoding="utf-8",
    )

    run_config = build_lcdm_example_run_config(output_directory=tmp_path / "output")
    artifacts = RunArtifacts(
        run_directory=run_directory,
        logs_directory=logs_directory,
        chains_directory=chains_directory,
        input_yaml_path=run_directory / "input.yaml",
        normalized_config_path=run_directory / "normalized_config.json",
        cobaya_input_path=run_directory / "cobaya_input.yaml",
        updated_cobaya_input_path=run_directory / "updated_cobaya_input.yaml",
        summary_path=run_directory / "summary.json",
        status_path=status_path,
        metadata_path=run_directory / "metadata.json",
        worker_log_path=logs_directory / "worker.log",
        cobaya_stdout_path=logs_directory / "cobaya.stdout.log",
        cobaya_stderr_path=logs_directory / "cobaya.stderr.log",
        events_path=logs_directory / "events.jsonl",
        chain_prefix=chains_directory / "chain",
    )
    request = WorkerRequest(
        schema_version=1,
        run_directory=run_directory,
        normalized_config_path=artifacts.normalized_config_path,
        cobaya_input_path=artifacts.cobaya_input_path,
        chain_prefix=artifacts.chain_prefix,
        status_path=artifacts.status_path,
        summary_path=artifacts.summary_path,
        updated_cobaya_input_path=artifacts.updated_cobaya_input_path,
        worker_log_path=artifacts.worker_log_path,
        cobaya_stdout_path=artifacts.cobaya_stdout_path,
        cobaya_stderr_path=artifacts.cobaya_stderr_path,
        events_path=artifacts.events_path,
        overwrite=False,
        seed=1,
    )
    return PreparedRunExecution(
        run_config=run_config,
        output_root=tmp_path / "output",
        artifacts=artifacts,
        request=request,
        request_path=request_path,
    )


def _write_worker_script(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake_worker.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _set_flag(flag: dict[str, bool]) -> None:
    flag["value"] = True


def _spin_until(condition, app: QApplication, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for condition.")
