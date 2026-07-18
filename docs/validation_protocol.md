# CosmoFit validation protocol

## Purpose

This protocol verifies that CosmoFit correctly transfers user-defined
background cosmological models, parameter definitions, priors, datasets,
and sampler settings to Cobaya.

The validation does not attempt to establish new cosmological constraints.
Its purpose is to test the scientific correctness and reproducibility of
the software workflow.

## Reference model

The primary reference model is spatially flat Lambda-CDM:

\[
H(z) =
H_0
\sqrt{
\Omega_m(1+z)^3 + 1-\Omega_m
}.
\]

The tests use the same model expression, parameter ranges, initial values,
and sampler convergence settings in CosmoFit and in the independent
reference calculations.

## Validation levels

### Unit tests

Unit tests cover:

- safe parsing of user-defined H(z) expressions;
- scalar and vector evaluations of H(z);
- cosmological distance calculations;
- cosmic-chronometer dataset validation;
- Gaussian likelihood calculations;
- covariance handling;
- Cobaya configuration generation;
- chain loading and posterior analysis;
- user-interface state and validation behavior.

### Technical smoke tests

Smoke tests verify that:

- CosmoFit creates valid Cobaya input;
- the sampler starts and terminates successfully;
- chain, metadata, status, summary, and log files are generated;
- official Cobaya supernova likelihoods can request distances from the
  generic background theory.

### Synthetic recovery

A reproducible synthetic cosmic-chronometer dataset is generated from
flat Lambda-CDM with:

\[
H_0 = 70\ {\rm km\,s^{-1}\,Mpc^{-1}},
\qquad
\Omega_m = 0.30.
\]

Gaussian noise is generated using a fixed random seed. The validation is
successful when the fiducial values are recovered within the reported
posterior credible intervals.

### Independent reference comparisons

Independent calculations are performed without using CosmoFit's
configuration builder or generic background theory.

For cosmic chronometers, the reference likelihood evaluates H(z)
directly.

For Pantheon+, Pantheon+SH0ES, and Union3, an independent Cobaya Theory
provides the flat-Lambda-CDM angular-diameter distance directly to the
official Cobaya likelihood.

## Comparison statistics

For each parameter, the following quantities are reported:

1. CosmoFit posterior mean and standard deviation;
2. independent-reference posterior mean and standard deviation;
3. symmetric relative difference between posterior means;
4. symmetric relative difference between posterior standard deviations;
5. normalized separation between posterior means,

\[
\Delta_{\rm norm}
=
\frac{
|\mu_{\rm CF}-\mu_{\rm ref}|
}{
\sqrt{
\sigma_{\rm CF}^2+\sigma_{\rm ref}^2
}
}.
\]

## Acceptance criteria

The implementation is considered statistically consistent when:

- the posterior credible intervals overlap;
- the normalized mean separation is substantially smaller than
  \(1\sigma\);
- the MCMC run satisfies the configured convergence criteria;
- no likelihood or theory errors are present in the execution logs.

Differences between posterior standard deviations at the few-percent
level are interpreted in the context of finite independent MCMC chains,
their autocorrelation, and effective sample sizes.

## Reproducibility

Validation scripts are stored under `validation/`.

Numerical summaries are stored under `validation/results/`.

Generated MCMC chains remain under `outputs/` and are not committed to
the repository.

The package versions, run configurations, logs, metadata, and random
seeds are retained in the generated run artifacts.
