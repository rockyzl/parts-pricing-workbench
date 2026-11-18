# Phase 2 preparation handoff — no fitting performed

Prepared the actual modeling/scenario implementation, frozen protocol and guarded local CPU runner. This handoff is **not** execution authorization or model-performance evidence. No model fitting, scientific ranking, cloud mutation, commit, email, or public backend publication was performed by this preparation task.

## Frozen smoke proposal

- Path: `data/model-runs/oj-smoke-v1-20261118-prepared/proposal.json` (local, ignored).
- Physical SHA-256: `45486e8dd23043d142a7b4ab2d27ee4d6aac29a2572807a16c6852af9d0e3bcc`.
- Semantic SHA-256: `95cb707e7478cc79e09074f5662a665330e2d4d3fbcca873e316c35ab93f7f35`.
- One-use nonce: `9f79f158b3d848bc83a1a053cbb8b321`.
- Planned trials: origin 140, `poisson-a01` and `tree-80`, seed 20261118; all origin-visible series, no selected subgroup.
- Source SHA-256: `3fc53cf6b14df1d69aba1977a27953400e53df5483c23493a38d6031b27b2c54`.
- Limits: 2 native threads; 2 GiB cgroup; 200% CPU quota; 180 s hard runtime; 120 s drain; 30 s stale-supervisor failure; no swap/GPU/cloud/publication/confirmation access.
- Proposal creation and fresh `validate_proposal` both succeeded with zero decoded-target counters. The proposal contains full wrapper argv, source/config/code/lock/binary/environment identities, target-free membership and complete fit roster.

**Prior access disclosure:** Full-source descriptive EDA had already occurred in Phase 1. The existing source-backed Phase 1 regression tests were also rerun during this preparation, before the immutable proposal. Those tests decoded the complete source for data-contract/arithmetic assertions. They produced no fitted performance or candidate-selection metrics. The prospective restricted-run counter boundary starts at the final proposal; confirmation must not be described as never-read or blind. Do not rerun source-backed full-ingestion tests during the protected selection period.

## Changed implementation

- `model_data.py`: filter source weeks before target conversion, target-free membership, own-origin historical training blocks, full origin catalog, conditional evaluation and explicit baseline/fallback coverage, grouped metrics.
- `models.py`: genuine penalized pooled Poisson and bounded histogram tree fit functions, fold-frozen learned categories, shared brand log-price associations, full-catalog scenario prediction, support/qualification rules and conservative model admission.
- `model_governance.py`: strict derived phase plans, immutable proposal binding, external review consumption, authorization hard stop, target-free replay, hash-chained trial ledger, atomic handoff publication and post-run artifact validation.
- `model_cli.py`: separate prepare/authorize/execute/validate, whole-process cgroup supervisor and actual fit subprocesses, final resource capture, retained-unit lifecycle release, confirmation/final-refit gates and baseline-only future forecasts.
- [`model-protocol-v1.md`](model-protocol-v1.md), machine config, [`model-runbook-v1.md`](model-runbook-v1.md), locked scikit-learn 1.9.1 and related actual dependencies, plus no-fit tests.

Other agents own the design/backend contract/review documents currently present in the shared worktree. No files were committed by this task.

## Verification evidence

- 23 model tests pass in ~0.23 s, with no real fitting. They cover historical-origin leakage, future labels/conditions/membership, missing vs zero, source label filtering, nonfinite/admission errors, all-zero constant state, joint support, incomplete selection rejection, replay/checkpoint/wrapper tampering, atomic publication and stale monitor failure.
- Existing 21 data tests passed in 2.009 s before final proposal freeze; existing 8 JavaScript tests passed. The full-source access from the former is disclosed above.
- `uv lock --check`, `git diff --check`, compilation and CLI help passed.
- Independent code reviewer additionally blocked all estimator/encoder fits while rerunning the no-fit suite, checked arbitrary canonical grouping/time metadata and baseline-only final refit behavior.
- No-data/no-fit systemd infrastructure probe: `data/model-runs/wrapper-probe-20261118/evidence-retained.json` records active/exited + MainPID 0, retained outer peak 20,959,232 bytes, empty/collected prior cgroup, successful lifecycle release, and inactive/not-found afterward. This tests the wrapper seam only. It is **not** backend training feasibility. The earlier probe artifact is preserved and its empty-ControlGroup check was flawed; do not cite that first check as a pass.

## Next gate

Independent reviewer inspects the exact prepared proposal and code, then writes an external scope `authorize-smoke` artifact using the strict schema in the runbook. Root runs the authorize command and stops. A **new** independent `execute-only` artifact bound to the resulting authorization is required before the exact bounded smoke command can execute.

Only successful real-backend smoke with authenticated aggregate resource evidence can support formal selection preparation. Confirmation and through-160 refit implementations already exist behind separate reviewed phase proposals, preserving the same scientific code lineage. Any change to frozen source/config/protocol after this handoff invalidates this prepared proposal and requires a new run ID; never update its bytes or reuse its directory. Public upload/retraining/auth/review service remains later implementation, not delivered by this local runner.
