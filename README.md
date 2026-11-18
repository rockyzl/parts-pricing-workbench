# Parts Pricing Workbench

[Open the demo](https://rockyzl.github.io/parts-pricing-workbench/) · [中文讲解](docs/learn.zh.md)

An independent learning prototype that makes a price decision inspectable: view a historical product, enter business assumptions, compare feasible prices, and save a local review note.

The public demo uses genuine **UCI Online Retail** gift-retail transactions. It is a public proxy for learning the workflow, **not automotive-parts data**. Costs, market ceilings and elasticity inputs are explicit scenario assumptions. This first version does not train an elasticity model or call an LLM.

## Try it

1. Select a product and inspect its recorded weekly sales.
2. Enter an assumed unit cost, minimum gross-margin rate and permitted price change.
3. Compare candidate prices. Expand the sparse-item explanation to adjust a hypothetical item/family sensitivity combination.
4. Try a cost/ceiling conflict, or select a product with no recent sales. The engine returns an explanation instead of inventing a price or a unit of demand.
5. Save a local review note or download the calculation record. No real prices are published.

The page defaults to English and has a Chinese learning toggle. There is no login, paid server or model API.

## Calculation

For each allowed price `p` and assumed elasticity `e`:

```text
scenario units = recent eight-week mean recorded units × (p / reference price)^e
scenario gross profit = (p − assumed unit cost) × scenario units
price floor = max(cost / (1 − minimum margin), reference price × (1 − change limit))
price ceiling = min(reference price × (1 + change limit), optional market ceiling)
```

Limits are rounded inward to pence. If the interval is empty, no price is proposed. Zero recent recorded sales returns a data-review state. Otherwise, the engine tests a grid of at most 1,003 cent-valued candidates and chooses the highest minimum profit across three sensitivity scenarios. Ties prefer the price nearest the reference. This is the best of the enumerated candidates, not a claim of continuous or real-world optimality.

The three elasticities are a central teaching assumption plus/minus 0.6 (upper value capped at −0.05). The central assumption mixes hypothetical item and family values using `activeWeeks / (activeWeeks + 8)`. This is an explicit teaching policy, **not empirical-Bayes estimation, an estimated posterior, causal inference or a confidence interval**.

## Real data / assumptions / missing information

| Layer | What it contains |
|---|---|
| Observed | Real historical product descriptions, prices, quantities and transaction dates, aggregated without customer identifiers |
| Descriptive | Recent eight-week mean recorded sales; days/weeks without a recorded sale do not establish in-stock exposure |
| Assumed | Unit cost, margin requirement, maximum price change, optional comparable-market ceiling, price sensitivity and information-sharing policy |
| Calculated | Feasible price range, scenario quantities/profit, selected grid candidate and review record |
| Not implemented | Fitted elasticity, causal identification, forecast validation, substitution model, portfolio optimizer, LLM, Palantir integration, authenticated approvals or live experimentation |

Changes in observed transaction prices can reflect customer mix, quantity discounts or promotions. No actual profit improvement is claimed. No four-hundred-thousand-product scaling benchmark is claimed.

## Run locally

```bash
node --test tests/engine.test.mjs
python3 -m http.server 8791 --directory web
```

Open http://localhost:8791. The browser executes `web/engine.mjs` on every calculation; results are not prerecorded.

V2 development has completed the Python weekly-data foundation, independently reviewed local OJ model training, and the reviewed portable reference bundle and bounded pricing engine. The frozen Poisson model's confirmation MAE is 7,698.47 (recent-mean baseline: 11,921.55), conditional on realized prices and advertising; this is not causal price-response or profit evidence. See the [Phase 3 acceptance and handoff](docs/pricing-phase3-handoff.md), [Phase 2 results](docs/pricing-phase2-handoff.md), [model runbook](docs/model-runbook-v2.md), and [validated upload contract](docs/data-contracts/weekly-pricing-v1.md). The public page remains V1. Hosted uploads/retraining, authentication, shared review and the V2 UI remain to be implemented; local raw data and model artifacts are excluded from Git.

To regenerate the data, install `requirements-data.txt`, download the official [UCI ZIP](https://archive.ics.uci.edu/static/public/352/online+retail.zip) as `data/raw/online-retail.zip`, and run:

```bash
python3 scripts/prepare_data.py
```

The downloader receipt and expected SHA-256 are in `docs/data-source.json`. Raw transactions are excluded from Git. Data processing is descriptive; no model fitting occurs.

## Verification and next steps

Tests cover conflicting limits, inward rounding, zero sales, malformed inputs, unchanged prices, the teaching weight, and independent exhaustive-grid arithmetic. Browser verification checks all public cases, state invalidation, language switching, review/export and mobile layout.

Phase 3 passed 22 bundle tests, 32 pricing tests and independent full-catalog arithmetic checks over 249 series and 5,566 candidates. The next phase implements the authenticated public application and persistent review workflow described in the [Phase 4 design handoff](docs/pricing-phase4-implementation-handoff.md). Forecast accuracy and causal commercial impact remain separate. See the [Phase 3 verification](docs/reviews/phase3-verification.md) and [source attribution](THIRD_PARTY.md).
