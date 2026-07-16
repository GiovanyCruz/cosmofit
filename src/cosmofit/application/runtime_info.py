"""Application-facing runtime metadata helpers for the desktop UI."""

from __future__ import annotations

from pathlib import Path

from cosmofit.cobaya_engine.environment import get_cobaya_packages_path as _get_path


def get_cobaya_packages_path() -> Path | None:
    """Return the configured Cobaya packages path when available."""

    return _get_path()
