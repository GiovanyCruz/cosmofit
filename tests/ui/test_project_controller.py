"""Project controller tests for MathText-compatible project persistence."""

from __future__ import annotations

from pathlib import Path

from cosmofit.ui.project_controller import ProjectController


def test_save_and_load_project_preserves_raw_mathtext_strings(tmp_path: Path) -> None:
    controller = ProjectController()
    state = controller.default_state()
    state["model"]["expression"] = "H0*sqrt(Om*(1+z)**3 + 1-Om)"
    state["parameters"] = [
        {
            "name": "H0",
            "label": r"$H_0$",
            "role": "sampled",
            "prior_min": "50",
            "prior_max": "90",
            "reference": "70",
            "proposal": "1",
            "fixed_value": "",
            "unit": "km/s/Mpc",
            "nuisance": False,
        },
        {
            "name": "Om",
            "label": r"$\Omega_m$",
            "role": "fixed",
            "prior_min": "",
            "prior_max": "",
            "reference": "",
            "proposal": "",
            "fixed_value": "0.3",
            "unit": "",
            "nuisance": False,
        },
    ]
    state["datasets"]["cosmic_chronometers_selected"] = True
    state["datasets"]["cosmic_chronometers_path"] = (
        "tests/fixtures/cosmic_chronometers_synth.csv"
    )

    path = tmp_path / "project.json"
    controller.save_project(path, state)
    restored = controller.load_project(path)

    assert restored["parameters"][0]["label"] == r"$H_0$"
    assert restored["parameters"][1]["label"] == r"$\Omega_m$"
