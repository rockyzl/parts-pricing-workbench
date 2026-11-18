# Sources and implementation boundaries

## Data

Chen, D. (2015). **Online Retail**. UCI Machine Learning Repository.
https://doi.org/10.24432/C5BW33

Official source: https://archive.ics.uci.edu/dataset/352/online+retail
License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

`web/catalog.json` is an attributed derivative: selected UK merchandise sales are aggregated by week; customer identifiers are removed; a small set of examples is published. The source is historical gift retail, not vehicle parts. Filtering, selection and hash are recorded in `scripts/prepare_data.py` and `docs/data-audit.json`.

Cost, competitor-price ceilings, family and item elasticity inputs are educational assumptions added by this demo. They are not fields or learned results from UCI.

## Researched references

No source code from these repositories is bundled in this first version. The browser optimizer and UI are independently implemented. Tools named here are references, not installed integrations.

- [Microsoft Interactive Price Analytics](https://github.com/Azure/cortana-intelligence-price-analytics), MIT, inspected at `5ea231ff4f9feccfed5b5ea78f10428a6fb0fe3b`: useful business architecture and discussion of sparse-item information sharing. Archived; no legacy cloud templates were deployed.
- [StatsForecast](https://github.com/Nixtla/statsforecast), Apache-2.0: intermittent sales baselines for a later measured modeling stage. Not installed or benchmarked here.
- [OR-Tools](https://github.com/google/or-tools), Apache-2.0: future portfolio-level constraints; the current single-item optimizer enumerates a bounded grid directly.
- [Choice-Learn](https://github.com/artefactory/choice-learn), MIT, inspected at `9af332f9eea930d8824e67f3cbf7d194b62f7455`: possible later treatment of substitution and product-choice data.
- [Price Elasticity Optimization](https://github.com/msgupta/price-elasticity-optimization), MIT, inspected at `faa2b6ca49562a257cc5d5c8deb22567b5fc4e91`: reviewed a compact pooling/optimization example. It uses synthetic data. A reproduced inconsistent-bound case returned £121.20 when the declared ceiling was £112; our test rejects that case. The published upstream business claims were not verified.

The browser runs standard JavaScript with no runtime library/CDN, paid API or LLM. Python/pandas/openpyxl are used only to prepare the historical aggregate data.
