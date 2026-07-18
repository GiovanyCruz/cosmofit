# Installation

This guide explains how to install and run CosmoFit from source.

## Requirements

CosmoFit requires:

* macOS or Linux
* Python 3.12 or newer
* Git
* Cobaya
* PySide6
* A Python virtual environment

Python 3.12 is recommended for the first scientific release.

## Clone the repository

Clone the public CosmoFit repository:

```bash
git clone nano docs/installation.md
cd cosmofit
```

Replace `REPLACE_WITH_REPOSITORY_URL` with the final public repository URL when it becomes available.

## Create a virtual environment

Create a local Python virtual environment:

```bash
python3.12 -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Verify that the correct Python interpreter is active:

```bash
which python
python --version
```

The interpreter path should point inside the project directory:

```text
cosmofit/.venv/bin/python
```

## Upgrade the packaging tools

Upgrade `pip`, `setuptools`, and `wheel`:

```bash
python -m pip install --upgrade pip setuptools wheel
```

## Install CosmoFit

Install CosmoFit in editable mode:

```bash
python -m pip install -e .
```

Editable installation is recommended for development and scientific validation because changes made under `src/` become available without reinstalling the package.

For development, install the optional dependencies when the project provides a `dev` dependency group:

```bash
python -m pip install -e ".[dev]"
```

If the development group is unavailable, install Pytest separately:

```bash
python -m pip install pytest
```

## Verify the Python package

Confirm that Python can import CosmoFit:

```bash
python -c "import cosmofit; print(cosmofit.__file__)"
```

The printed path should point to the local repository.

## Configure the Cobaya package directory

The official supernova likelihoods require external data installed through Cobaya.

Create a shared package directory:

```bash
mkdir -p "$HOME/cobaya_packages"
```

Set the environment variable used by Cobaya:

```bash
export COBAYA_PACKAGES_PATH="$HOME/cobaya_packages"
```

Confirm the configured location:

```bash
echo "$COBAYA_PACKAGES_PATH"
```

To make the setting permanent on macOS with Zsh, add it to `~/.zshrc`:

```bash
echo 'export COBAYA_PACKAGES_PATH="$HOME/cobaya_packages"' >> ~/.zshrc
source ~/.zshrc
```

## Install the supported supernova likelihoods

Install the official data used by the supported Cobaya likelihoods:

```bash
cobaya-install \
  sn.pantheonplus \
  sn.pantheonplusshoes \
  sn.union3 \
  --packages-path "$COBAYA_PACKAGES_PATH"
```

The supernova data are installed and managed by Cobaya. They are not redistributed directly with CosmoFit.

## Verify the Cobaya data directory

Inspect the installed package directory:

```bash
find "$COBAYA_PACKAGES_PATH" -maxdepth 3 -type d | sort
```

## Run the test suite

Run all tests from the root of the repository:

```bash
pytest -q
```

To display the reasons for skipped tests:

```bash
pytest -q -rs
```

A successful installation should complete the test suite without failures. Some optional graphical or threaded smoke tests may be skipped depending on the runtime environment.

## Launch CosmoFit

Start the graphical interface with:

```bash
python -m cosmofit.ui
```

If the project defines a command-line entry point in `pyproject.toml`, that command may also be used after installation.

## Verify PySide6

If the graphical interface does not start, confirm that PySide6 is installed:

```bash
python -c "import PySide6; print(PySide6.__version__)"
```

If the import fails, install PySide6:

```bash
python -m pip install PySide6
```

Then launch CosmoFit again:

```bash
python -m cosmofit.ui
```

## Run a scientific validation

The reference flat-(\Lambda)CDM model used by the validation scripts is:

```text
H0*sqrt(Om*(1+z)**3 + 1-Om)
```

Build the consolidated validation summary:

```bash
python validation/build_validation_summary.py
```

The generated files are:

```text
validation/results/validation_summary.csv
validation/results/validation_summary.md
```

The complete validation methodology is described in:

```text
docs/validation_protocol.md
```

## Run outputs

A typical CosmoFit run produces:

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

The generated MCMC chains are normally stored under `outputs/` and excluded from version control.

Numerical summaries used for software validation are stored under:

```text
validation/results/
```

## Updating an existing installation

Enter the repository:

```bash
cd cosmofit
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Download the latest changes:

```bash
git pull
```

Refresh the editable installation:

```bash
python -m pip install -e .
```

Run the tests again:

```bash
pytest -q
```

## Deactivate the environment

When finished, deactivate the virtual environment:

```bash
deactivate
```

## Troubleshooting

### CosmoFit cannot be imported

Reinstall the local package:

```bash
python -m pip install -e .
```

Verify the import:

```bash
python -c "import cosmofit; print(cosmofit.__file__)"
```

### Cobaya cannot find the likelihood data

Check the environment variable:

```bash
echo "$COBAYA_PACKAGES_PATH"
```

If it is empty, configure it again:

```bash
export COBAYA_PACKAGES_PATH="$HOME/cobaya_packages"
```

Reinstall the likelihood data if necessary:

```bash
cobaya-install \
  sn.pantheonplus \
  sn.pantheonplusshoes \
  sn.union3 \
  --packages-path "$COBAYA_PACKAGES_PATH"
```

### The wrong Python environment is active

Check the active interpreter:

```bash
which python
python --version
```

Reactivate the CosmoFit environment:

```bash
source .venv/bin/activate
```

### The interface fails to start on macOS

Run the interface directly from the terminal:

```bash
python -m cosmofit.ui
```

Review the terminal output for missing dependencies, Qt plugins, or import errors.

More troubleshooting information is available in:

```text
docs/troubleshooting.md
```

