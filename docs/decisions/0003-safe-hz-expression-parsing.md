# ADR 0003: Safe H(z) Expression Parsing

## Status

Accepted

## Context

Users supply cosmological background models as mathematical expressions.
`AGENTS.md` forbids `eval()` and `exec()` and requires a restricted
parser that only permits declared symbols and approved mathematical
functions.

Some common symbolic helpers are not acceptable for milestone 1:

- `sympy.parse_expr` relies on Python evaluation internally.
- `sympy.lambdify` generates executable Python code.

## Decision

Milestone 1 accepts only `H(z)` expressions and parses them using Python
`ast.parse(..., mode="eval")` as a syntax front-end, without executing
the parsed source.

The parser will:

- accept numeric literals, binary arithmetic, unary sign, exponentiation,
  parentheses, the redshift symbol `z`, declared parameter symbols, and
  approved bare math-function names;
- reject attributes, subscripts, comprehensions, lambdas, assignments,
  imports, keyword arguments, and any call target that is not a
  whitelisted function name;
- build an internal expression tree or validated symbolic form that is
  evaluated only through a closed NumPy-backed function map.

The evaluator will:

- operate on NumPy arrays;
- return `H(z)` in `km/s/Mpc`;
- reject `NaN`, infinite, complex, and non-positive outputs.

## Consequences

- The parser satisfies the no-`eval`/no-`exec` security constraint.
- The allowed expression language is explicit and testable.
- Supporting richer symbolic constructs later will require a deliberate
  ADR update instead of ad hoc parser growth.
