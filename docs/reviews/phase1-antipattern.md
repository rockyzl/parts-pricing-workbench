# Phase 1 independent anti-pattern review

Reviewed the working tree on `agent/pricing-engine-v2`, based on `412dbe7`, on 2026-11-18. **PASS for the current local data-foundation scope; no blocking anti-pattern findings.** This is a source/documentation review, not a substitute for the separate arithmetic and test-suite verification. No training, deployment, cloud access, or code changes were performed.

## Scope and search evidence

Read `docs/pricing-phase1-handoff.md`, `docs/data-contracts/weekly-pricing-v1.md`, Phase 0/1 and status statements in `docs/pricing-engine-v2-plan.zh.md`; inspected all `src/pricing_engine/*.py`, `tests/data/test_data.py`, `pyproject.toml`, `.gitignore`, README, THIRD_PARTY, deployment preflight, and the Pages workflow.

Used `rg` over these paths for `ffill|bfill|fillna|interpolat|reindex|future|scaler|standardscaler|fit\(|train|imput`, `exp\(|logmove|promo|cost|inventory|date|calendar`, `merge\(|join\(|duplicate`, `eval\(|exec\(|pickle|yaml\.load|urlopen|MAX_`, and `public_audit|audit.summary|cloud|sso|entra|auth|部署|训练|登录`. Inspected matches in context, including explicit negative capability claims. Also checked `git ls-files` for raw/archive/model/credential files, `git check-ignore` for the raw and processed paths, and `git diff --name-only HEAD -- web scripts tests/engine.test.mjs .github`.

## Results

| Check | Result and evidence |
|---|---|
| Future catalog, values, scalers, filling | **PASS.** `data.py:37` filters both observation and known-at weeks before catalog construction. Catalog, price support, concentration, and outlier flags use snapshot observations. No scaler, model fitting, forward/back filling, or interpolation exists in V2. OJ demographics with unverified historical availability are excluded (`ingest.py:234`). Full-source hashes/counts remain provenance, not cutoff-local model features. |
| Missing weeks and zero demand | **PASS.** `data.py:76` creates null gaps, labels pre-observation gaps separately, and keeps availability unknown. `analysis.py:116` emits null weekly units when no records exist. Explicit observed zeros survive. |
| Manufactured promotion, cost, inventory, dates | **PASS.** OJ uses original `feat`, source week indices, and unrounded `exp(logmove)` (`ingest.py:214`). Dates/currency/returns remain unknown where unavailable. No shifted demonstration calendar, fictional cost, inferred discount, or manufactured stock enters V2. Uploads require provided dates or indexed weeks; blank advertising remains unknown. |
| Duplicate and many-to-many joins | **PASS.** `ingest.py:108` rejects duplicate series/week keys. Series keys are unambiguous JSON item/site pairs. The panel merge enforces `validate="one_to_one"` (`data.py:91`); no other V2 table joins were found. |
| User-controlled parsing and expansion | **PASS for local scope, with resource note below.** Byte/row/field/series/source-span caps, finite numeric ranges, strict schema/time/grain checks, safe identifiers, and a preallocation panel cap are present. Remote downloads use one pinned URL and checksum. No executable upload format or user URL exists. |
| Public summary and private uploads | **PASS.** `analysis.py:158` emits a fixed aggregate/metadata projection; raw item/site/source identifiers, free text, detailed rows, and paths are excluded. CLI errors avoid private OS paths. Detailed artifacts remain local; documentation explicitly keeps uploaded totals private even after identifier removal. |
| Accidentally tracked raw data | **PASS at review time.** No tracked CSV, Parquet, XLSX, ZIP, pickle/joblib, environment, or credential/token files were found. Raw/processed paths are ignored. The existing public UCI aggregate catalog is V1, not a new OJ raw export. Pages uploads only `web/`. |
| Unsupported capability claims / V1 regression | **PASS.** README and handoff distinguish the unchanged static V1 from V2 data work. Outputs say `not_trained` / `models_trained=0`; dependencies contain no model/cloud/auth framework. Preflight describes a proposed backend and unverified integration. No tracked changes to V1 web, scripts, tests, or workflow appeared. |

## Nonblocking limits to carry forward

- **Resource cap is not a runtime guarantee.** `Dataset.as_of()` accepts a cutoff beyond the 5,200-week source span. A single series may expand toward the one-million-row cap, and `analysis.py:112` scans observations once per output week. Before exposing this through HTTP, bound the requested horizon and measure/enforce execution time and memory. Current documentation already describes the interface as local and the limits as unmeasured defaults.
- The contract explicitly defers independent catalogs, raw transaction ingestion, and separate cost/inventory/rule tables. This review approves no claim that those broader Phase 1 planning items, V2 training, SSO, or public multiuser execution are implemented. Historical training must use snapshot observations, not whole-file provenance or the descriptive weekly chart's cutoff-wide catalog denominator.

No fresh data-license approval was requested: the authorized personal noncommercial demo scope and private-by-default upload handling were retained.

## Remediation status note

The later [code-quality remediation review](phase1-quality.md#remediation-review--pass) confirms that nonempty expanded timelines now share the 5,200-week cap with source spans, with checks before panel allocation and weekly analysis. The final full Python suite passes all 21 tests. This supersedes the unbounded-cutoff observation above; measuring and enforcing HTTP execution time and memory remain future work.
