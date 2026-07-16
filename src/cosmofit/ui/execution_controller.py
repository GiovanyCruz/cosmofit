"""Qt-facing controller for background Cobaya execution."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from cosmofit.application import (
    RunConfig,
    cleanup_worker_request,
    prepare_worker_request,
)

EVENT_PREFIX = "COSMOFIT_EVENT "

STATE_IDLE = "Idle"
STATE_VALIDATING = "Validating"
STATE_STARTING = "Starting"
STATE_RUNNING = "Running"
STATE_CANCELLING = "Cancelling"
STATE_COMPLETED = "Completed"
STATE_FAILED = "Failed"
STATE_CANCELLED = "Cancelled"


@dataclass(frozen=True)
class ExecutionState:
    """Observable execution snapshot for the main window."""

    state: str = STATE_IDLE
    active: bool = False
    run_directory: Path | None = None
    output_root: Path | None = None


class ExecutionController(QObject):
    """Own a single worker process and stream its output into Qt signals."""

    state_changed = Signal(str, str)
    started = Signal(str)
    running = Signal()
    log_message = Signal(str, str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    final_run_directory = Signal(str)
    request_rejected = Signal(str)

    def __init__(
        self,
        *,
        cancellation_timeout_ms: int = 3000,
        worker_program: str | None = None,
        worker_arguments_builder: callable | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cancellation_timeout_ms = cancellation_timeout_ms
        self._worker_program = worker_program or sys.executable
        self._worker_arguments_builder = (
            worker_arguments_builder or self._default_worker_arguments
        )
        self._process = QProcess(self)
        self._process.setProgram(self._worker_program)
        self._process.readyReadStandardOutput.connect(self._drain_stdout)
        self._process.readyReadStandardError.connect(self._drain_stderr)
        self._process.started.connect(self._handle_process_started)
        self._process.finished.connect(self._handle_process_finished)
        self._process.errorOccurred.connect(self._handle_process_error)

        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._force_kill)

        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._prepared = None
        self._state = ExecutionState()
        self._cancellation_requested = False
        self._pending_terminal_event: tuple[str, str] | None = None

    def execution_state(self) -> ExecutionState:
        return self._state

    def has_active_run(self) -> bool:
        return self._state.active

    def start_run(self, run_config: RunConfig) -> bool:
        if self._state.active:
            self.request_rejected.emit("Ya existe una ejecucion activa.")
            return False

        try:
            prepared = prepare_worker_request(run_config)
        except Exception as error:
            self.request_rejected.emit(
                str(error) or "No se pudo preparar la ejecucion."
            )
            return False
        self._prepared = prepared
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._cancellation_requested = False
        self._pending_terminal_event = None
        self._set_state(
            STATE_STARTING,
            "Preparando el proceso de Cobaya.",
            active=True,
            run_directory=prepared.artifacts.run_directory,
            output_root=prepared.output_root,
        )
        self._process.setArguments(self._worker_arguments_builder(prepared.request_path))
        self._process.setWorkingDirectory(str(Path.cwd()))
        environment = QProcessEnvironment.systemEnvironment()
        existing_pythonpath = environment.value("PYTHONPATH", "")
        source_root = str(Path(__file__).resolve().parents[2])
        environment.insert(
            "PYTHONPATH",
            source_root
            if not existing_pythonpath
            else source_root + (":" + existing_pythonpath),
        )
        self._process.setProcessEnvironment(environment)
        self._process.start()
        return True

    def cancel_run(self) -> bool:
        if not self._state.active:
            return False
        if self._cancellation_requested:
            return False
        self._cancellation_requested = True
        self._set_state(STATE_CANCELLING, "Solicitando cancelacion del ajuste.")
        self._process.terminate()
        self._kill_timer.start(self._cancellation_timeout_ms)
        return True

    def cleanup(self) -> None:
        if self._prepared is not None:
            cleanup_worker_request(self._prepared.request_path)
            self._prepared = None

    def _default_worker_arguments(self, request_path: Path) -> list[str]:
        return ["-m", "cosmofit.application.run_worker", str(request_path)]

    def _handle_process_started(self) -> None:
        if self._state.run_directory is not None:
            self.started.emit(str(self._state.run_directory))

    def _handle_process_finished(
        self,
        exit_code: int,
        _exit_status: QProcess.ExitStatus,
    ) -> None:
        if self._prepared is None:
            return
        self._kill_timer.stop()
        self._drain_stdout()
        self._drain_stderr()
        terminal_state, message = self._finalize_process_result(exit_code)
        if terminal_state == STATE_COMPLETED:
            self.completed.emit(str(self._state.run_directory))
        elif terminal_state == STATE_CANCELLED:
            self.cancelled.emit()
        else:
            self.failed.emit(message)
        self.cleanup()

    def _handle_process_error(self, _error: QProcess.ProcessError) -> None:
        if not self._state.active:
            return
        if (
            _error == QProcess.ProcessError.Crashed
            and self._cancellation_requested
        ):
            self._set_state(
                STATE_CANCELLED,
                "La ejecucion fue cancelada.",
                active=False,
            )
            self.cancelled.emit()
            self.cleanup()
            return
        message = self._process.errorString() or "No se pudo iniciar el worker."
        self._set_state(STATE_FAILED, message, active=False)
        self.failed.emit(message)
        self.cleanup()

    def _drain_stdout(self) -> None:
        self._stdout_buffer += bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._stdout_buffer = self._consume_lines(self._stdout_buffer, "stdout")

    def _drain_stderr(self) -> None:
        self._stderr_buffer += bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        self._stderr_buffer = self._consume_lines(self._stderr_buffer, "stderr")

    def _consume_lines(self, buffer: str, stream: str) -> str:
        lines = buffer.splitlines(keepends=True)
        remaining = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            remaining = lines.pop()
        for raw_line in lines:
            self._handle_output_line(stream, raw_line.rstrip("\r\n"))
        return remaining

    def _handle_output_line(self, stream: str, line: str) -> None:
        if not line:
            return
        if stream == "stdout" and line.startswith(EVENT_PREFIX):
            try:
                payload = json.loads(line[len(EVENT_PREFIX) :])
            except json.JSONDecodeError:
                self.log_message.emit(stream, line)
                return
            self._apply_worker_event(payload)
            return
        self.log_message.emit(stream, line)

    def _apply_worker_event(self, payload: dict[str, object]) -> None:
        event = str(payload.get("event", ""))
        message = str(payload.get("message", ""))
        run_directory = payload.get("run_directory")
        if isinstance(run_directory, str):
            self.final_run_directory.emit(run_directory)
            self._state = ExecutionState(
                state=self._state.state,
                active=self._state.active,
                run_directory=Path(run_directory),
                output_root=self._state.output_root,
            )
        if event == "running":
            self._set_state(STATE_RUNNING, message, active=True)
            self.running.emit()
            return
        if event == "completed":
            self._pending_terminal_event = (event, message)
            return
        if event == "failed":
            self._pending_terminal_event = (event, message)
            return
        if event == "cancelled":
            self._pending_terminal_event = (event, message)
            return
        self.log_message.emit("stdout", message)

    def _force_kill(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _finalize_process_result(self, exit_code: int) -> tuple[str, str]:
        status = self._load_status_payload()
        run_directory = self._state.run_directory
        if status and isinstance(status.get("run_directory"), str):
            run_directory = Path(status["run_directory"])
            self.final_run_directory.emit(str(run_directory))

        if (
            exit_code == 0
            and status
            and status.get("state") == "succeeded"
            and run_directory
        ):
            message = "El ajuste termino correctamente."
            self._set_state(
                STATE_COMPLETED,
                message,
                active=False,
                run_directory=run_directory,
            )
            return STATE_COMPLETED, message

        if status and status.get("state") == "cancelled":
            message = "La ejecucion fue cancelada."
            self._set_state(
                STATE_CANCELLED,
                message,
                active=False,
                run_directory=run_directory,
            )
            return STATE_CANCELLED, message

        message = "La ejecucion fallo."
        if (
            status
            and isinstance(status.get("message"), str)
            and status["message"].strip()
        ):
            message = status["message"].strip()
        elif (
            self._pending_terminal_event is not None
            and self._pending_terminal_event[0] == "failed"
        ):
            message = self._pending_terminal_event[1]
        elif self._cancellation_requested and exit_code != 0:
            message = "La ejecucion fue cancelada."
            self._set_state(
                STATE_CANCELLED,
                message,
                active=False,
                run_directory=run_directory,
            )
            return STATE_CANCELLED, message
        elif exit_code == 0:
            message = "El worker termino sin artefactos finales validos."
        self._set_state(
            STATE_FAILED,
            message,
            active=False,
            run_directory=run_directory,
        )
        return STATE_FAILED, message

    def _load_status_payload(self) -> dict[str, object] | None:
        if self._prepared is None:
            return None
        path = self._prepared.artifacts.status_path
        if not path.is_file():
            return None
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {
                "state": "malformed",
                "message": "La salida del worker es invalida.",
            }
        return payload if isinstance(payload, dict) else None

    def _set_state(
        self,
        state: str,
        message: str,
        *,
        active: bool | None = None,
        run_directory: Path | None = None,
        output_root: Path | None = None,
    ) -> None:
        self._state = ExecutionState(
            state=state,
            active=self._state.active if active is None else active,
            run_directory=(
                self._state.run_directory
                if run_directory is None
                else run_directory
            ),
            output_root=self._state.output_root if output_root is None else output_root,
        )
        self.state_changed.emit(state, message)
