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
    """Translate backend exceptions into concise Spanish messages."""

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
                "Los nombres de los parametros deben ser unicos.",
            ),
            (
                "Parameter symbols must be unique.",
                "Los nombres internos de los parametros deben ser unicos.",
            ),
            (
                "Dataset selections must be unique.",
                "No se puede seleccionar el mismo conjunto de datos mas de una vez.",
            ),
            (
                "At least one dataset must be selected.",
                "Debes seleccionar al menos un conjunto de datos.",
            ),
            (
                "At least one cosmological parameter is required.",
                "Debes definir al menos un parametro cosmologico.",
            ),
            (
                "Parameter name must not be empty.",
                "Cada parametro necesita un nombre interno.",
            ),
            (
                "must be a valid identifier",
                "El nombre interno del parametro debe ser "
                "un identificador valido.",
            ),
            ("is reserved.", "Ese nombre de parametro esta reservado."),
            (
                "conflicts with an allowed function.",
                "El nombre interno del parametro coincide con "
                "una funcion aprobada.",
            ),
            ("requires a prior.", "Un parametro muestreado necesita limites de prior."),
            (
                "requires a reference value.",
                "Un parametro muestreado necesita un valor de referencia.",
            ),
            (
                "requires a strictly positive proposal.",
                "Un parametro muestreado necesita una propuesta "
                "estrictamente positiva.",
            ),
            (
                "must lie within the prior bounds.",
                "El valor de referencia debe estar dentro de los limites del prior.",
            ),
            (
                "Fixed parameter",
                "Un parametro fijo necesita un valor y no puede incluir "
                "prior ni propuesta.",
            ),
            (
                "Model expression must not be empty.",
                "La expresion H(z) no puede estar vacia.",
            ),
            (
                "Invalid H(z) expression syntax",
                "La expresion H(z) tiene una sintaxis invalida.",
            ),
            ("Unknown symbol", "La expresion H(z) usa un simbolo no declarado."),
            (
                "not in the approved function list",
                "La expresion H(z) usa una funcion no aprobada.",
            ),
            (
                "Only arithmetic binary operations are allowed.",
                "La expresion H(z) solo permite operaciones aritmeticas.",
            ),
            (
                "Attribute access is not allowed.",
                "La expresion H(z) no permite acceso por atributos.",
            ),
            (
                "Subscript access is not allowed.",
                "La expresion H(z) no permite indices ni subscripts.",
            ),
            (
                "Lambda expressions are not allowed.",
                "La expresion H(z) no permite lambdas.",
            ),
            (
                "Conditional expressions are not allowed.",
                "La expresion H(z) no permite expresiones condicionales.",
            ),
            (
                "Collection literals are not allowed.",
                "La expresion H(z) no permite colecciones literales.",
            ),
            (
                "Comprehensions are not allowed.",
                "La expresion H(z) no permite comprensiones.",
            ),
            ("CSV file is empty.", "El archivo de cronometros cosmicos esta vacio."),
            (
                "Cosmic chronometer CSV header must be exactly 'z,H,sigma'.",
                "El archivo de cronometros cosmicos debe usar el "
                "encabezado exacto 'z,H,sigma'.",
            ),
            (
                "Could not parse cosmic chronometer CSV",
                "No se pudo leer el archivo CSV de cronometros cosmicos.",
            ),
            ("No such file or directory", "No se encontro el archivo seleccionado."),
            (
                "Unsupported dataset kind",
                "El conjunto de datos seleccionado no esta soportado.",
            ),
            (
                "Unsupported supernova dataset component name.",
                "El conjunto de datos de supernova no esta soportado.",
            ),
        )
        for needle, translated in translations:
            if needle in message:
                return translated
        return None
