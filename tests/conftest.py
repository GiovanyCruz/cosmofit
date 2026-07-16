"""Shared pytest configuration for CosmoFit tests."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")
os.environ.setdefault("LANG", "en_US.UTF-8")
