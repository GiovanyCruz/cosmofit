# Matched-Cobaya validation workflow

This isolated workflow extends, and does not replace, the existing single-realization synthetic cosmic-chronometer (CC) recovery. It provides complementary synthetic and real-data validation experiments.

## Preserved baseline

The existing manuscript validation remains unchanged at `validation/data/cosmic_chronometers_synthetic_recovery_input.csv` and `validation/run_synthetic_recovery.py`. It uses 15 CC measurements from z=0.05 to 2.35, flat ΛCDM `H0*sqrt(Om*(1+z)**3 + 1-Om)`, fiducial H0=70 and Om=0.30, independent Gaussian errors from 2.5 to 12 km/s/Mpc, and seed 20260717. The fit uses uniform H0=[50,90] and Om=[0.05,0.60] priors, references 70/0.30, proposals 1.0/0.02, `max_samples=10000`, `burn_in=200`, learned proposals, `Rminus1_stop=0.01`, and `Rminus1_cl_stop=0.05`.

## Independent realizations

`run_realizations.py` retains precisely that redshift grid, error prescription, fiducial model, priors, references, proposals, and stopping settings. It creates each noise realization with `numpy.random.default_rng(seed)` in a distinct directory, then invokes the same `RunConfig` and `run_in_subprocess` backend used by CosmoFit. Existing successful directories are skipped. An incomplete pre-existing directory is refused rather than overwritten.

## Paired MCMC-seed repeatability

`run_mcmc_seed_comparison.py` fixes the original manuscript synthetic input dataset and runs both (A) the CosmoFit-generated Cobaya workflow and (B) a direct, independent Cobaya Gaussian CC likelihood for every seed. The canonical scientific configuration includes H(z), dataset checksum, diagonal covariance prescription, parameters, priors, references, proposal widths, MCMC controls, stopping thresholds, and package path. It is compared programmatically before sampling; a difference aborts the run and is saved in `configuration_comparison.json`.

## Historical real-CC controlled comparison

`run_comparison.py` is separate from both synthetic experiments. It fixes the historical 18-point real CC file at `data/cosmic_chronometers/cosmic_chronometers_18.csv` (SHA-256 `ed9d77b5f3b0ce368354eef886b654e639370dfe987c9cd8a971a093a8510869`) and uses the historical flat-LCDM, priors, references, proposals, burn-in, learned proposal, maximum samples, and convergence thresholds. Before every pair it compares dataset checksum, H(z), likelihood, parameters, sampler controls, and the native Cobaya seed. The pair is aborted on a scientific mismatch.

This study records posterior means and weighted-covariance standard deviations with exactly `loadMCSamples(root, settings={"ignore_rows": 0.3})`, raw/retained rows, retained weights, accepted samples, ESS, R−1, status, and time. Its outputs live only under `outputs/real_cc_seed_repeatability/`; it never modifies historical outputs, synthetic recovery realizations, or synthetic seed comparisons.

## Diagnostics and interpretation

Cobaya's checkpoint supplies `converged` and final `Rminus1_last`; convergence is governed by the unchanged thresholds R−1<0.01 and confidence-level R−1<0.05. GetDist’s `getEffectiveSamples(j)` is recorded separately for H0 and Om. This is a parameter-specific, autocorrelation-adjusted estimate relevant to the error on that parameter mean, not a single total ESS. Progress files provide accepted/total counts (where Cobaya exposes them) and acceptance rate. Failed or non-converged runs are retained in row summaries but excluded from successful aggregate recovery statistics.

Coverage fractions are measured descriptive fractions, never claims of exact nominal coverage from a small ensemble. The seed report similarly reports observed paired posterior-width differences and does not attribute historical 6.1%/4.6% differences to finite MCMC fluctuations unless a completed production experiment supports it.

## Commands

From the activated project environment:

```bash
python validation/matched_cobaya/run_realizations.py --smoke
python validation/matched_cobaya/run_mcmc_seed_comparison.py --smoke
python validation/matched_cobaya/run_comparison.py --smoke
python validation/matched_cobaya/summarize.py
```

Production commands (not launched automatically):

```bash
python validation/matched_cobaya/run_realizations.py --n-realizations 20
python validation/matched_cobaya/run_mcmc_seed_comparison.py --n-seeds 5
python validation/matched_cobaya/run_comparison.py --n-seeds 5
python validation/matched_cobaya/summarize.py
```

Outputs are under `validation/matched_cobaya/outputs/`; row-level CSV/JSON tables and the report are under `validation/matched_cobaya/summaries/`; Matplotlib PNG/PDF figures are under `validation/matched_cobaya/plots/`. Every run records environment versions, UTC date, seed, dataset checksum, covariance status, configuration, and output directory. Large chains and caches are ignored by Git.
