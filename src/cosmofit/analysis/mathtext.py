"""Safe Matplotlib MathText validation and preview rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from cosmofit.analysis.errors import InvalidMathTextError

matplotlib.use("Agg")


@dataclass(frozen=True)
class MathTextPreview:
    """Rendered PNG preview bytes for one MathText string."""

    png_bytes: bytes


def _has_escaped_prefix(text: str, index: int) -> bool:
    """Return whether the character at ``index`` is escaped by backslashes."""

    backslash_count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslash_count += 1
        cursor -= 1
    return (backslash_count % 2) == 1


def _count_unescaped_dollar_delimiters(text: str) -> int:
    """Count MathText dollar delimiters while ignoring escaped literal dollars."""

    delimiter_count = 0
    for index, character in enumerate(text):
        if character == "$" and not _has_escaped_prefix(text, index):
            delimiter_count += 1
    return delimiter_count


def validate_mathtext(text: str | None, *, field_name: str) -> None:
    """Raise a stable error when Matplotlib cannot render the given text."""

    normalized = (text or "").strip()
    if not normalized:
        return
    delimiter_count = _count_unescaped_dollar_delimiters(normalized)
    if delimiter_count % 2 == 1:
        raise InvalidMathTextError(
            field_name=field_name,
            details="unbalanced MathText dollar delimiters",
        )

    figure = Figure(figsize=(3.2, 0.75), dpi=144)
    try:
        canvas = FigureCanvasAgg(figure)
        figure.text(
            0.02,
            0.5,
            normalized,
            fontsize=12,
            ha="left",
            va="center",
        )
        canvas.draw()
    except Exception as error:  # pragma: no cover - backend-specific exception types
        raise InvalidMathTextError(
            field_name=field_name,
            details=str(error),
        ) from error


def render_mathtext_preview(
    text: str | None,
    *,
    field_name: str,
) -> MathTextPreview | None:
    """Render a transparent PNG preview using the same MathText engine as plots."""

    normalized = (text or "").strip()
    if not normalized:
        return None

    validate_mathtext(normalized, field_name=field_name)
    width_inches = min(max(1.6, 0.12 * len(normalized)), 5.0)
    figure = Figure(figsize=(width_inches, 0.75), dpi=144)
    FigureCanvasAgg(figure)
    figure.patch.set_alpha(0.0)
    figure.text(
        0.02,
        0.5,
        normalized,
        fontsize=12,
        ha="left",
        va="center",
    )
    buffer = BytesIO()
    figure.savefig(
        buffer,
        format="png",
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.05,
    )
    return MathTextPreview(png_bytes=buffer.getvalue())


def is_matplotlib_usetex_enabled() -> bool:
    """Expose the active Matplotlib usetex default for tests."""

    return bool(matplotlib.rcParams["text.usetex"])
