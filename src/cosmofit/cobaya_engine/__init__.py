"""Cobaya integration layer for CosmoFit milestone 1."""

from cosmofit.cobaya_engine.config_builder import build_cobaya_input
from cosmofit.cobaya_engine.runner import run_in_subprocess

__all__ = ["build_cobaya_input", "run_in_subprocess"]
