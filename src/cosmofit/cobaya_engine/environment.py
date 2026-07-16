"""Environment helpers that keep Cobaya imports inside cobaya_engine."""

from __future__ import annotations

from pathlib import Path

from cobaya.tools import resolve_packages_path


def get_cobaya_packages_path() -> Path | None:
    """Return the installed Cobaya packages path when configured."""

    packages_path = resolve_packages_path()
    if not packages_path:
        return None
    return Path(packages_path)
