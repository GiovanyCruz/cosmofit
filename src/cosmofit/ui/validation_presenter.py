"""User-facing validation messages for the PySide6 interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationFeedback:
    """Normalized validation result for display in the desktop UI."""

    success: bool
    summary: str
    details: str


class ValidationPresenter:
    """Translate backend exceptions into concise English messages."""

    def present_success(self, summary: str) -> ValidationFeedback:
        return ValidationFeedback(success=True, summary=summary, details=summary)

    def present_error(self, error: Exception, *, fallback: str) -> ValidationFeedback:
        message = str(error).strip()
        detail = f"{type(error).__name__}: {error}"
        return ValidationFeedback(
            success=False,
            summary=self._summarize(message, fallback=fallback),
            details=detail,
        )

    def _summarize(self, message: str, *, fallback: str) -> str:
        translated = self._translate(message)
        if translated is not None:
            return translated
        if not message:
            return fallback
        return f"{fallback} {message}"

    def _translate(self, message: str) -> str | None:
        translations = (
            (
                "Parameter names must be unique.",
                "Parameter names must be unique.",
            ),
            (
                "Parameter symbols must be unique.",
                "Parameter symbols must be unique.",
            ),
            (
                "Dataset selections must be unique.",
                "Dataset selections must be unique.",
            ),
            (
                "At least one dataset must be selected.",
                "At least one dataset must be selected.",
            ),
            (
                "At least one cosmological parameter is required.",
                "At least one cosmological parameter is required.",
            ),
            (
                "Parameter name must not be empty.",
                "Parameter name must not be empty.",
            ),
            (
                "must be a valid identifier",
                "Parameter symbol must be a valid identifier.",
            ),
            ("is reserved.", "That parameter symbol is reserved."),
            (
                "conflicts with an allowed function.",
                "Parameter symbol conflicts with an allowed function.",
            ),
            ("requires a prior.", "A sampled parameter requires prior bounds."),
            (
                "requires a reference value.",
                "A sampled parameter requires a reference value.",
            ),
            (
                "requires a strictly positive proposal.",
                "A sampled parameter requires a strictly positive proposal.",
            ),
            (
                "must lie within the prior bounds.",
                "The reference value must lie within the prior bounds.",
            ),
            (
                "Fixed parameter",
                "A fixed parameter requires a value and must not define "
                "a prior or proposal.",
            ),
            (
                "Model expression must not be empty.",
                "The H(z) expression cannot be empty.",
            ),
            (
                "Invalid H(z) expression syntax",
                "The H(z) expression has invalid syntax.",
            ),
            ("Unknown symbol", "The H(z) expression uses an undeclared symbol."),
            (
                "not in the approved function list",
                "The H(z) expression uses a function outside the approved list.",
            ),
            (
                "Only arithmetic binary operations are allowed.",
                "The H(z) expression allows only arithmetic operations.",
            ),
            (
                "Attribute access is not allowed.",
                "The H(z) expression does not allow attribute access.",
            ),
            (
                "Subscript access is not allowed.",
                "The H(z) expression does not allow subscript access.",
            ),
            (
                "Lambda expressions are not allowed.",
                "The H(z) expression does not allow lambda expressions.",
            ),
            (
                "Conditional expressions are not allowed.",
                "The H(z) expression does not allow conditional expressions.",
            ),
            (
                "Collection literals are not allowed.",
                "The H(z) expression does not allow collection literals.",
            ),
            (
                "Comprehensions are not allowed.",
                "The H(z) expression does not allow comprehensions.",
            ),
            ("CSV file is empty.", "The cosmic chronometer CSV file is empty."),
            (
                "Cosmic chronometer CSV header must be exactly 'z,H,sigma'.",
                "The cosmic chronometer CSV header must be exactly 'z,H,sigma'.",
            ),
            (
                "Could not parse cosmic chronometer CSV",
                "Could not parse the cosmic chronometer CSV file.",
            ),
            ("No such file or directory", "The selected file was not found."),
            (
                "Unsupported dataset kind",
                "The selected dataset is not supported.",
            ),
            (
                "Unsupported supernova dataset component name.",
                "The selected supernova dataset is not supported.",
            ),
        )
        for needle, translated in translations:
            if needle in message:
                return translated
        return None
