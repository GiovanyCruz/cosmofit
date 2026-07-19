# CosmoFit

CosmoFit is a desktop graphical interface for background-level cosmological parameter inference with Cobaya.

It allows users to define a cosmological expansion history (H(z)), configure model parameters and priors, select supported datasets, execute Markov chain Monte Carlo analyses, and inspect posterior results without directly writing Cobaya configuration files.

## Current release

The current development release is:

```text
CosmoFit 0.1.0
```

This version focuses on homogeneous and isotropic background cosmology. Cosmological perturbations are not included in the initial release.

## Main features

CosmoFit currently provides:

* user-defined (H(z)) expressions;
* safe expression parsing without unrestricted `eval`;
* fixed and sampled cosmological parameters;
* uniform parameter priors;
* cosmic-chronometer likelihoods;
* official Cobaya supernova likelihoods;
* MCMC execution in an isolated worker process;
* reproducible configuration and metadata files;
* chain inspection with GetDist;
* marginalized parameter summaries;
* one-dimensional and two-dimensional posterior plots;
* validation against independent Cobaya calculations.

## Supported datasets

The initial release supports:

* cosmic chronometers;
* Pantheon+;
* Pantheon+SH0ES;
* Union3.

The supernova datasets are accessed through the official Cobaya likelihood components and are not bundled directly with CosmoFit.

## Installation

CosmoFit is currently distributed through this source-code repository.

To install and run CosmoFit, users need:

* Git
* Python 3.12

Git is required to clone the repository. Python is required to create the virtual environment, install the dependencies, and run the graphical interface.

Clone the repository:

```bash
git clone https://github.com/GiovanyCruz/cosmofit.git
cd cosmofit
```

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install CosmoFit:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

For full installation instructions, see:

```text
docs/installation.md
```

## Cobaya likelihood data

Create a shared directory for external Cobaya packages:

```bash
mkdir -p "$HOME/cobaya_packages"
export COBAYA_PACKAGES_PATH="$HOME/cobaya_packages"
```

Install the supported supernova likelihood data:

```bash
cobaya-install \
  sn.pantheonplus \
  sn.pantheonplusshoes \
  sn.union3 \
  --packages-path "$COBAYA_PACKAGES_PATH"
```

## Launching CosmoFit

After installation, launch the interface with:

```bash
cosmofit
```

Alternatively:

```bash
python -m cosmofit.ui
```

## Example model

A flat Lambda-CDM background can be entered as:

```text
H0*sqrt(Om*(1+z)**3 + 1-Om)
```

A typical definition uses:

* `H0` as a fixed or sampled parameter;
* `Om` as a sampled parameter;
* a uniform prior for each sampled parameter.

## Run outputs

Each execution creates a dedicated directory containing configuration, metadata, logs, status information, summaries, and Cobaya chain files.

A typical run contains:

```text
input.yaml
normalized_config.json
cobaya_input.yaml
metadata.json
status.json
summary.json
logs/
chains/
```

See `docs/outputs.md` for details.

## Scientific validation

CosmoFit has been validated using:

* unit and integration tests;
* a synthetic parameter-recovery experiment;
* an independent cosmic-chronometer likelihood;
* independent Cobaya comparisons for Pantheon+;
* independent Cobaya comparisons for Pantheon+SH0ES;
* independent Cobaya comparisons for Union3.

The consolidated numerical results are stored in:

```text
validation/results/validation_summary.csv
validation/results/validation_summary.md
```

The full protocol is described in:

```text
docs/validation_protocol.md
```

## Running the tests

Run the complete test suite:

```bash
pytest -q
```

Show skipped-test reasons with:

```bash
pytest -q -rs
```

Run the code-quality checker:

```bash
ruff check .
```

## Documentation

The documentation currently includes:

* `docs/installation.md`;
* `docs/quickstart.md`;
* `docs/datasets.md`;
* `docs/outputs.md`;
* `docs/validation_protocol.md`;
* `docs/troubleshooting.md`;
* architecture and design-decision documents.

## Current limitations

The initial release:

* considers background cosmology only;
* assumes spatially flat distance relations;
* does not include cosmological perturbations;
* does not yet provide an explicit absolute-magnitude parameter for calibrated supernova inference;
* requires external Cobaya data for official supernova likelihoods;
* has been developed primarily on macOS;
* should be independently validated on additional operating systems.

## Reproducibility

CosmoFit stores:

* the normalized user configuration;
* the generated Cobaya configuration;
* runtime metadata;
* sampler status;
* logs;
* posterior chains;
* numerical summaries.

Random seeds are fixed in the reference validation scripts.

## Citation

Citation metadata are provided in:

```text
CITATION.cff
```

When the associated article and archive DOI become available, they will be added to the citation metadata.

## License

CosmoFit is distributed under the MIT License.

See:

```text
LICENSE
```

## Author

Giovany Cruz Huerfano

