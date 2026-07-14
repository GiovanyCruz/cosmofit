# CosmoFit

## Project goal

Build a desktop application for Bayesian inference of cosmological
background models using Cobaya.

The user provides:

- H(z) or E(z)
- model parameters
- fixed or sampled status
- prior bounds
- initial/reference values
- proposal widths
- selected datasets

The application validates the model, constructs a Cobaya configuration,
runs the sampler in a separate process, and displays posterior results
using GetDist.

## Initial scope

The first stable release supports:

1. Flat background cosmology.
2. Cosmic chronometers.
3. Pantheon+ supernovae.
4. Uniform priors.
5. Fixed and sampled parameters.
6. Cobaya MCMC.
7. GetDist plots and summaries.
8. PySide6 desktop interface.
9. macOS development first.

Union and non-flat cosmology should only be added after the initial
end-to-end implementation is validated.

## Architecture

The dependency direction is:

ui -> application services -> domain/cosmology
                           -> likelihoods
                           -> cobaya adapter

The cosmology and likelihood layers must not import PySide6.

Cobaya-specific objects must remain inside `cobaya_engine`.

## Scientific requirements

- Use explicit physical units.
- H(z) is expressed in km/s/Mpc unless documented otherwise.
- Distances are expressed in Mpc.
- Never silently assume a supernova calibration convention.
- Validate covariance matrix dimensions and symmetry.
- Reject NaN, infinite, complex, and non-positive H(z) values.
- Every scientific formula must have a unit test.
- Compare implemented LCDM predictions against independent reference
  calculations.

## Security

- Never use Python eval() or exec() to interpret user models.
- Parse mathematical expressions using a restricted symbolic parser.
- Only permit declared symbols and approved mathematical functions.
- The model expression must not access files, modules, attributes,
  subprocesses, networking, or Python builtins.

## Development rules

- Use Python 3.12.
- Use type hints for public functions.
- Use dataclasses or Pydantic models for configuration.
- Use pathlib instead of string-based paths.
- Use NumPy arrays internally.
- Use pytest for tests.
- Use Ruff for linting and formatting.
- Avoid adding dependencies without explaining why.
- Keep commits focused.
- Do not modify unrelated files.
- Run the relevant tests after every implementation task.

## Definition of done

A task is complete only when:

- the implementation is present,
- tests cover normal and failure cases,
- tests pass,
- public behavior is documented,
- no unrelated files were changed,
- scientific assumptions are explicit.
