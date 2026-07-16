"""Worker entry point used by the desktop UI and blocking runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cosmofit.application import deserialize_run_config
from cosmofit.application.execution import (
    load_worker_request,
    validate_run_config_for_execution,
)
from cosmofit.cobaya_engine.worker import run_worker_request


def main(argv: list[str] | None = None) -> int:
    """Validate a prepared request and execute it without importing PySide6."""

    parser = argparse.ArgumentParser()
    parser.add_argument("request_path")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    request = load_worker_request(Path(args.request_path))
    with request.normalized_config_path.open(encoding="utf-8") as handle:
        run_config = deserialize_run_config(json.load(handle))
    validated_config = validate_run_config_for_execution(run_config)
    return run_worker_request(request, validated_config)


if __name__ == "__main__":
    raise SystemExit(main())
