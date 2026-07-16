"""Application-facing facade for safe Matplotlib MathText handling."""

from __future__ import annotations

from cosmofit.analysis.mathtext import (
    MathTextPreview,
    is_matplotlib_usetex_enabled,
    render_mathtext_preview,
    validate_mathtext,
)


class MathTextService:
    """Expose MathText validation and preview rendering without leaking UI details."""

    def validate(self, text: str | None, *, field_name: str) -> None:
        validate_mathtext(text, field_name=field_name)

    def render_preview(
        self,
        text: str | None,
        *,
        field_name: str,
    ) -> MathTextPreview | None:
        return render_mathtext_preview(text, field_name=field_name)

    def is_usetex_enabled(self) -> bool:
        return is_matplotlib_usetex_enabled()
