"""Architecture boundary tests for Cobaya and PySide6 imports."""

from __future__ import annotations

import ast
from pathlib import Path


def test_only_cobaya_engine_imports_cobaya() -> None:
    offending_files = _find_offending_imports(
        "cobaya",
        allowed_root=Path("src/cosmofit/cobaya_engine"),
    )

    assert offending_files == []


def test_only_ui_imports_pyside6() -> None:
    offending_files = _find_offending_imports(
        "PySide6",
        allowed_root=Path("src/cosmofit/ui"),
    )

    assert offending_files == []


def test_only_analysis_imports_getdist() -> None:
    offending_files = _find_offending_imports(
        "getdist",
        allowed_root=Path("src/cosmofit/analysis"),
    )

    assert offending_files == []


def test_only_analysis_imports_matplotlib() -> None:
    offending_files = _find_offending_imports(
        "matplotlib",
        allowed_root=Path("src/cosmofit/analysis"),
    )

    assert offending_files == []


def test_worker_entry_points_do_not_import_pyside6() -> None:
    offending_files = _find_offending_imports(
        "PySide6",
        allowed_root=Path("src/cosmofit/ui"),
    )

    assert "src/cosmofit/application/run_worker.py" not in offending_files
    assert "src/cosmofit/cobaya_engine/worker.py" not in offending_files


def _find_offending_imports(module_name: str, *, allowed_root: Path) -> list[str]:
    offenders: list[str] = []
    for path in Path("src/cosmofit").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports_module = any(
            (
                isinstance(node, ast.Import)
                and any(
                    alias.name == module_name
                    or alias.name.startswith(f"{module_name}.")
                    for alias in node.names
                )
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == module_name
                    or node.module.startswith(f"{module_name}.")
                )
            )
            for node in ast.walk(tree)
        )
        if imports_module and not path.is_relative_to(allowed_root):
            offenders.append(str(path))
    return offenders
