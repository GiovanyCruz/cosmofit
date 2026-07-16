"""Module entry point for `python -m cosmofit.ui`."""

from __future__ import annotations

import sys

from cosmofit.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
