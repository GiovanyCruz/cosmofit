# Cobaya Supernova Contracts

This document records the supernova-likelihood contracts verified
against the locally installed Cobaya `3.6.2` source in
`.venv/lib/python3.13/site-packages/cobaya`.

Verified sources:

- `cobaya/likelihoods/base_classes/sn.py`
- `cobaya/likelihoods/sn/pantheonplus.py`
- `cobaya/likelihoods/sn/pantheonplusshoes.py`
- `cobaya/likelihoods/sn/union3.py`
- `cobaya/likelihoods/sn/pantheonplus.yaml`
- `cobaya/likelihoods/sn/pantheonplusshoes.yaml`
- `cobaya/likelihoods/sn/union3.yaml`
- `cobaya/theory.py`
- `cobaya/theories/cosmo/boltzmannbase.py`

## Shared SN Base Contract

Component family:

- `sn.pantheonplus`
- `sn.pantheonplusshoes`
- `sn.union3`

Shared base behavior comes from `SN.get_requirements()` and `SN.logp()`
in `cobaya/likelihoods/base_classes/sn.py`.

Verified contract:

- Requirement name: `angular_diameter_distance`
- Requirement payload shape: `{"z": self.zcmb}`
- Optional extra requirement: `Mb` only when `use_abs_mag` is `True`
- Provider method used by the likelihood: `provider.get_angular_diameter_distance(z)`
- Provider method signature expected by Cobaya’s standard cosmology API:
  `get_angular_diameter_distance(self, z)`
- Redshift input format: one-dimensional array-like `z` values matching
  the dataset’s `zcmb` column after any internal masking
- Expected distance units: `Mpc`
- No Hubble-rate theory quantity is requested by these SN likelihoods

Distance convention used internally by Cobaya:

- The likelihood computes
  `lumdists = 5 * log10((1 + zhel) * (1 + zcmb) * D_A)`
- Since `D_A` is expected in `Mpc`, the argument of `log10` is
  `D_L / Mpc`, where `D_L = (1 + zhel)(1 + zcmb)D_A`
- The additive `+25` offset is not part of the theory quantity; it is
  introduced only through the supernova calibration term when `Mb` is
  active

Absolute-magnitude handling:

- If `use_abs_mag: False`, the likelihood does not request `Mb`
- If `use_abs_mag: True`, the likelihood requests `Mb` and uses
  `estimated_scriptm = Mb + 25`
- Therefore `Mb` is the absolute-magnitude nuisance/calibration
  parameter in Cobaya’s contract, not part of the theory distance
  modulus

## `sn.pantheonplus`

Verified implementation:

- Class: `PantheonPlus`
- Source: `cobaya/likelihoods/sn/pantheonplus.py`
- Official component name: `sn.pantheonplus`

Dataset columns used:

- `m_b_corr`
- `zhd` as `zcmb`
- `zhel`

Redshift treatment:

- Internal mask: only rows with `zcmb > 0.01` are used
- Theory is queried at masked `zcmb` values
- `zhel` is still used in the luminosity-distance conversion factor

Calibration behavior:

- Default YAML sets `use_abs_mag: False`
- In that default mode, `PantheonPlus.init_params()` calls
  `_marginalize_abs_mag()`
- This projects out the constant absolute-magnitude/calibration mode
  from the inverse covariance matrix before likelihood evaluation

Conclusion:

- Default Pantheon+ marginalizes over the absolute-magnitude
  calibration internally
- It does not need `Mb` unless `use_abs_mag` is explicitly enabled

## `sn.pantheonplusshoes`

Verified implementation:

- Class: `PantheonPlusShoes`
- Source: `cobaya/likelihoods/sn/pantheonplusshoes.py`
- Official component name: `sn.pantheonplusshoes`

Dataset columns used:

- `m_b_corr`
- `zhd` as `zcmb`
- `zhel`
- `is_calibrator`
- `ceph_dist`

Redshift treatment:

- Internal mask keeps rows with `(zcmb > 0.01) | is_calibrator`
- Theory is queried only at the retained `zcmb` values
- For calibrator rows, the theory luminosity quantity is overwritten by
  `ceph_dist - 25.0`

Calibration behavior:

- Default YAML sets `use_abs_mag: False`
- In that default mode, it inherits `PantheonPlus.init_params()` and
  therefore still calls `_marginalize_abs_mag()`
- If `use_abs_mag: True`, the likelihood requests `Mb` and uses
  `Mb + 25` as the absolute-magnitude offset while also substituting
  Cepheid-host distances for calibrator rows

Conclusion:

- Pantheon+SH0ES has an explicit calibrator subset
- Default behavior still marginalizes over the absolute-magnitude mode
- `Mb` becomes an explicit nuisance parameter only when
  `use_abs_mag: True`

## `sn.union3`

Verified implementation:

- Class: `Union3`
- Source: `cobaya/likelihoods/sn/union3.py`
- Official component name: `sn.union3`

Dataset columns used:

- `zcmb`
- `mb` as `mag`

Redshift treatment:

- No low-redshift mask is applied in `Union3.configure()`
- `zhel` is set equal to `zcmb`
- Theory is queried at all dataset `zcmb` values

Calibration behavior:

- Default YAML sets `use_abs_mag: False`
- `Union3` inherits `PantheonPlus.init_params()`
- Therefore it also calls `_marginalize_abs_mag()` in the default mode
- If `use_abs_mag: True`, it requests `Mb` and uses `Mb + 25`

Conclusion:

- Default Union3 marginalizes over the absolute-magnitude/calibration
  mode internally
- It does not request `Mb` unless enabled explicitly

## Cobaya Provider Names And Signatures

Verified from `cobaya/theory.py` and
`cobaya/theories/cosmo/boltzmannbase.py`:

- Cobaya exposes provider methods from exact `get_<name>` method names
- Requirement names are case-sensitive in practice at the provider
  level
- Standard cosmology method for SN support:
  `get_angular_diameter_distance(self, z)`
- Standard cosmology method for Hubble support:
  `get_Hubble(self, z, units="km/s/Mpc")`

For CosmoFit’s generic background theory milestone, the minimum exact
provider surface needed for these verified SN contracts is:

- `get_angular_diameter_distance(self, z)`

For joint operation with CosmoFit’s cosmic chronometer adapter, the same
shared theory should also expose:

- `get_Hubble(self, z, units="km/s/Mpc")`

## Practical Builder Implications

To keep scientific assumptions explicit:

- Use official internal Cobaya likelihood names:
  `sn.pantheonplus`, `sn.pantheonplusshoes`, `sn.union3`
- Set `use_abs_mag: False` explicitly unless CosmoFit adds an explicit
  `Mb` configuration contract
- Do not encode any hidden absolute-magnitude offset into the theory
  distance modulus or luminosity distance
- Provide `angular_diameter_distance` in `Mpc`
- Provide `Hubble` in `km/s/Mpc`, with optional `1/Mpc` conversion only
  for Cobaya compatibility

## Data Installation

These SN likelihoods declare shared install metadata through the SN base
class:

- GitHub repository: `CobayaSampler/sn_data`
- Required release: `v1.8`

Verified local Cobaya console entrypoints include `cobaya-install`.
The installation command for the data package is therefore:

```bash
cobaya-install sn.pantheonplus
```

That installs the shared `sn_data` package used by Pantheon+, Pantheon+
SH0ES, and Union3.
