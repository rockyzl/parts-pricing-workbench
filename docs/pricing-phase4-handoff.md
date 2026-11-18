# Phase 4 accepted local application and hosted-acceptance handoff

2026-11-18. **The local Phase 4 application passed independent functional, quality and anti-pattern review.** It implements the same-origin workbench/API, private artifact and ledger interfaces, server-enforced identity/role boundaries, immutable pricing revisions, independent review, and a bounded operational-job controller/worker. The final reviewed source snapshot is preserved below. No hosted V2 application, live provider identity, actual operational fit or cloud persistence is established by this acceptance; the public website remains V1.

This status follows the original [API](pricing-phase4-api-handoff.md), [training](pricing-phase4-training-handoff.md), and [UI](pricing-phase4-ui-handoff.md) owner handoffs. Their pending-independent-review notes record delivery-time status. Their detailed interfaces and remaining hosted checks remain useful; the independent reports below establish the final local acceptance.

| Accepted record | Physical SHA-256 |
| --- | --- |
| [Functional verification](reviews/phase4-verification.md) | `9b1b6b5d260d88276453bea1227ee7abf6e123b0f82f6c5a79686655526f96c6` |
| [Quality review](reviews/phase4-quality.md) | `f3ac98bff8db90fc2f77e0516f5d52af2de0d1f8a3436d4a836be660e3108e95` |
| [Anti-pattern review](reviews/phase4-antipattern.md) | `926050ddeeed2e2a5ab09c1d2995a6f989154a731640456fa6ee8ff0640d5351` |
| [28-file verification snapshot](reviews/phase4-verification-snapshot.json) | `4a32960715d7bcb7914284e151e78e09af6a903973bea8704d22ef6ea86c90c2` |

Independent verification exercised the actual local HTTP handlers, fixed inference child, pricing engine, seven review batches and idempotent private publication for all 249 reference entries: 20 changes and 229 holds, 996 exported weekly price rows and 249 coverage rows. Identity verification and storage in these checks were explicit local test seams. Reopening the same in-memory store through a new app instance does not establish Azure durability.

Final targeted evidence includes 21 no-fit training/supervisor tests, 13 backend tests, 11 frontend client tests, real Chromium identity-race and local API/engine integration checks, and an independently injected telemetry/worker CAS race. The fixes retain mutation keys until response bodies finish, fence private asynchronous work across identity changes, and supervise training from a separate parent process. The real subprocess tests exercise resource termination without fitting; mocked pipeline calls establish control flow only. Exact execution history and limitations are in the independent reports.

The accepted Phase 2/3 engine and review bindings remain unchanged. The expanded dependency lock preserves all ten original package/version records and pins the API/storage/auth/job dependencies and CPython 3.13.12. The curated public example is an allowlisted saved projection with no per-series raw history or checkpoints, unknown currency, explicit business assumptions, and no publication approval. Private data/model artifacts remain outside public Git.

Next acceptance must establish two real invited identities and server capabilities, explicit personal Azure managed-identity permissions, private Blob/Table persistence across restart, immutable image pull, actual fixed-job dispatch and termination, bounded real training and model registration, hosted comparison resources, and the complete live browser upload/train/compare/review/publish/download flow. Preserve failed runs and declared budgets. Concurrent Docker/deployment preparation and teaching-download files are outside this reviewed commit and require their own checks. This working-branch backup does not merge `main` or trigger GitHub Pages.
