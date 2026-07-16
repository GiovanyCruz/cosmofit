"""Cobaya integration layer for CosmoFit milestone 1."""

__all__ = ["build_cobaya_input", "run_in_subprocess"]


def __getattr__(name: str):
    if name == "build_cobaya_input":
        from cosmofit.cobaya_engine.config_builder import build_cobaya_input

        return build_cobaya_input
    if name == "run_in_subprocess":
        from cosmofit.cobaya_engine.runner import run_in_subprocess

        return run_in_subprocess
    raise AttributeError(name)
