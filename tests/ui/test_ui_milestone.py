"""Headless tests for the first PySide6 UI milestone."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from cosmofit.application import LCDM_EXPRESSION
from cosmofit.ui.project_controller import ProjectController

ROOT = Path(__file__).resolve().parents[2]


def _run_ui_script(script: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    python_path = str(ROOT / "src")
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = python_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = python_path
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_ui_json(script: str) -> dict[str, object]:
    result = _run_ui_script(script)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_application_entry_point_starts_in_offscreen_mode() -> None:
    payload = _run_ui_json(
        """
        import json
        import os
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui import app as ui_app

        original_exec = QApplication.exec
        QApplication.exec = lambda self: 0
        try:
            result = ui_app.main([])
        finally:
            QApplication.exec = original_exec

        print(json.dumps({"platform": os.environ["QT_QPA_PLATFORM"], "result": result}))
        """
    )

    assert payload == {"platform": "offscreen", "result": 0}


def test_main_window_can_be_constructed() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        print(json.dumps(
            {
                "class_name": type(window).__name__,
                "tab_count": window.tabs.count(),
                "first_tab": window.tabs.tabText(0),
                "last_tab": window.tabs.tabText(4),
            }
        ))
        """
    )

    assert payload == {
        "class_name": "MainWindow",
        "tab_count": 5,
        "first_tab": "Model",
        "last_tab": "Results",
    }


def test_lcdm_example_populates_correctly() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        window.load_lcdm_example()
        print(json.dumps(
            {
                "expression": window.model_widget.expression_edit.text(),
                "row_count": window.parameter_table.table.rowCount(),
                "chronometers": (
                    window.datasets_widget
                    .cosmic_chronometers_checkbox
                    .isChecked()
                ),
                "pantheonplus": (
                    window.datasets_widget.pantheonplus_checkbox.isChecked()
                ),
            }
        ))
        """
    )

    assert payload["expression"] == LCDM_EXPRESSION
    assert payload["row_count"] == 2
    assert payload["chronometers"] is True
    assert payload["pantheonplus"] is False


def test_parameter_table_supports_arbitrary_rows() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        window.parameter_table.set_parameters_state([])
        for index in range(6):
            window.parameter_table.add_parameter_row(
                {
                    "name": f"p{index}",
                    "label": f"P{index}",
                    "role": "sampled",
                    "prior_min": "0.0",
                    "prior_max": "1.0",
                    "reference": "0.5",
                    "proposal": "0.1",
                    "fixed_value": "",
                    "unit": "",
                    "nuisance": False,
                }
            )
        rows = window.parameter_table.parameters_state()
        print(json.dumps({"count": len(rows), "names": [row["name"] for row in rows]}))
        """
    )

    assert payload["count"] == 6
    assert payload["names"] == ["p0", "p1", "p2", "p3", "p4", "p5"]


def test_duplicate_parameter_validation_is_reported() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        window.load_lcdm_example()
        rows = window.parameter_table.parameters_state()
        rows[1]["name"] = rows[0]["name"]
        window.parameter_table.set_parameters_state(rows)
        window.validate_configuration()
        print(json.dumps({"summary": window.validation_summary_label.text()}))
        """
    )

    assert "unicos" in str(payload["summary"])


def test_sampled_and_fixed_field_behavior() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        table = window.parameter_table
        table.set_parameters_state(
            [
                {
                    "name": "alpha",
                    "label": "Alpha",
                    "role": "fixed",
                    "prior_min": "",
                    "prior_max": "",
                    "reference": "",
                    "proposal": "",
                    "fixed_value": "1.0",
                    "unit": "",
                    "nuisance": False,
                }
            ]
        )
        before = {
            "sampled_enabled": table.is_sampled_fields_enabled(0),
            "fixed_enabled": table.is_fixed_field_enabled(0),
        }
        role_box = table.table.cellWidget(0, table.COLUMN_ROLE)
        role_box.setCurrentText("sampled")
        after = {
            "sampled_enabled": table.is_sampled_fields_enabled(0),
            "fixed_enabled": table.is_fixed_field_enabled(0),
        }
        print(json.dumps({"before": before, "after": after}))
        """
    )

    assert payload["before"] == {"sampled_enabled": False, "fixed_enabled": True}
    assert payload["after"] == {"sampled_enabled": True, "fixed_enabled": False}


def test_dataset_conflict_prevention() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        window.datasets_widget.pantheonplus_checkbox.click()
        window.datasets_widget.union3_checkbox.click()
        print(json.dumps(
            {
                "pantheonplus": (
                    window.datasets_widget.pantheonplus_checkbox.isChecked()
                ),
                "union3": window.datasets_widget.union3_checkbox.isChecked(),
                "message": window.datasets_widget.conflict_message.toPlainText(),
            }
        ))
        """
    )

    assert payload["pantheonplus"] is True
    assert payload["union3"] is False
    assert "supernovas" in str(payload["message"])


def test_building_valid_run_config() -> None:
    controller = ProjectController()
    run_config = controller.build_run_config(controller.lcdm_example_state())

    assert run_config.model.expression == LCDM_EXPRESSION
    assert [parameter.symbol for parameter in run_config.parameters] == ["H0", "Om"]
    assert run_config.datasets[0].kind == "cosmic_chronometers"


def test_malformed_configuration_displays_error() -> None:
    payload = _run_ui_json(
        """
        import json
        from PySide6.QtWidgets import QApplication
        from cosmofit.ui.main_window import build_main_window

        app = QApplication([])
        window = build_main_window()
        window.load_lcdm_example()
        window.model_widget.expression_edit.setText("")
        window.validate_configuration()
        print(json.dumps({"summary": window.validation_summary_label.text()}))
        """
    )

    assert "expresion" in str(payload["summary"]).lower()


def test_save_and_reopen_project_round_trip(tmp_path: Path) -> None:
    controller = ProjectController()
    path = tmp_path / "project.json"
    state = controller.lcdm_example_state()

    saved = controller.save_project(path, state)
    restored_state = controller.load_project(path)
    restored = controller.build_run_config(restored_state)

    assert restored == saved


def test_ui_modules_do_not_import_cobaya_or_getdist() -> None:
    for path in Path("src/cosmofit/ui").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
                assert not any(name.startswith("cobaya") for name in imported), path
                assert not any(name.startswith("getdist") for name in imported), path
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith("cobaya"), path
                assert not node.module.startswith("getdist"), path


def test_ui_modules_do_not_duplicate_scientific_equations() -> None:
    forbidden_snippets = (
        "H0*sqrt(Om*(1+z)**3 + 1-Om)",
        "scipy.integrate",
        "quad(",
        "299792.458",
    )
    for path in Path("src/cosmofit/ui").rglob("*.py"):
        contents = path.read_text(encoding="utf-8")
        assert all(snippet not in contents for snippet in forbidden_snippets), path
