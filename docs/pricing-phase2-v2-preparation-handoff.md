# Phase 2 v2 correction preparation — stopped before authorization

The v1 authorized computational smoke failed at the first Poisson L-BFGS fit's 500-iteration limit. No planned fit completed and no tree fit started. This is not a model-quality result. The independent diagnosis is [phase2-smoke-v1-diagnosis.md](reviews/phase2-smoke-v1-diagnosis.md); the underlying convergence mechanism remains unproven without a controlled, separately approved new smoke.

Before any correction, all 13 proposal-bound v1 runtime/config/protocol/lock files were copied byte-for-byte to `data/model-lineages/v1-pre-correction/`, including previously untracked implementation files. Every copied hash equals its original proposal hash. The archive contains the exact original proposal and a manifest with SHA-256 `6e7286b0bd839d6e13f015fdb2fe65e94570b93133fa789adfc41725422874aa`. The failed run and prepared v1 proposal were not modified. Original v1 config/protocol, lock, project metadata and scientific feature module remain unchanged in the worktree as well.

V2 uses separate [`configs/model-protocol-v2.json`](../configs/model-protocol-v2.json), [protocol](model-protocol-v2.md) and [runbook](model-runbook-v2.md). Only the Poisson solver changes computational method, to officially supported `newton-cholesky`, with the same alphas, 500 iterations, tolerance, objective, features, windows, selection rules and budgets. `verbose=1`, `n_iter_`, warnings and design/Hessian size diagnostics are recorded. Sklearn's internal L-BFGS fallback is allowed when it does not raise `ConvergenceWarning`; any such warning still fails under the original v1 guard. Other warnings such as `LinAlgWarning` are recorded. There is no claim of Newton-only execution and no private solver patch or log-based fallback rejection.

The public validator now reports preserved failures with `status=failed`, `eligible_for_selection=false`, no ranking and read-only durable evidence. Internal feasibility/selection/promotion gates require complete authenticated success and reject failed reports. The v1 failure report shows zero completed trials, 25,152 decoded source rows through week 144, and zero protected rows.

## Immutable proposal

- Path: `data/model-runs/oj-smoke-v2-20261118-prepared/proposal.json`
- Physical SHA-256: `13b458a355a6714dc180647f8aecc857babcecd54574e61578e5e651978d578e`
- Semantic SHA-256: `9d6c02d51bdea201f518a2c7b82f43e640ddaa9875a32e4044c97e6f68880915`
- Nonce: `701f37938ccb43b8bc7c9b39cf995397`
- Bound runtime/config/protocol/lock files: 15, including preserved v1 and separate v2 protocol/config.
- Planned origin-140 fits: `poisson-a01`, then `tree-80`; seed 20261118.
- Unchanged local bounds: 2 GiB, two native threads/200% CPU quota, 180-second hard limit and 120-second drain.
- Preparation label counters: all zero; no v2 output/run directory exists.

Fresh `validate_proposal` passed. All 26 no-fit tests pass, including the narrow config-change comparison, supported constructor, failed-run read-only/nonpromotion checks, and prior model/governance tests. Lock and whitespace checks pass. No additional real fitting, source-backed full-ingestion regression, authorization, cloud mutation, commit or deployment was performed during v2 preparation.

The independent reviewer must now inspect these exact bytes and write a new `authorize-smoke` artifact. After authorization, stop again for a fresh separately bound `execute-only` review. Neither the failed v1 approval nor this preparation authorizes v2 execution. Changes to frozen files require another proposal/run ID.
