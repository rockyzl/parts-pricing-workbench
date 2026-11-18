# V2c smoke review — engineering PASS

Reviewed 2026-11-18 by independent agent `/root/pricing_smoke_result_review` through `collaboration.spawn_agent`. Scope: focused completed-smoke replay, resource/label evidence and equivalence to V2b after the independently reviewed [serialization-only correction](phase2-v2c-serialization-preparation-review.md). No incomplete outputs were evaluated before the immutable terminal appeared. No fitting, new model inference, protected-cache reading, original-source target conversion, authorization, execution or frozen-source edit occurred during this review.

The completed run is `data/model-runs/oj-smoke-v2c-20261118`. Terminal physical SHA-256: `0954f7e1f2ccda562254a257acee9543bae61d4db9597d4017d5bbfe826c5a43`; semantic SHA-256: `de709c62351831e9925ec949bb42e47b99e8ad9cf15593218ec5232601dd8f9d`.

`uv run --locked pricing-model validate --output data/model-runs/oj-smoke-v2c-20261118` exited zero and exactly matched direct `validate_run`. Fresh `validate_proposal` also passed, authenticating actual current source/config/protocol/lock/environment/hardware, target-free membership and the complete outer command. Official replay authenticated all 19 inventoried file hashes, checkpoint/report/cache identities, historical independent-decision bindings, resource capture and the complete two-trial ledger. The ledger has one start, two reservations, two matching completions and one terminal.

Both frozen trials completed: `140-poisson-a01` reports six iterations, finite train mean-Poisson deviance `5802.109788464948`, no warnings and native Newton convergence with decreasing gradient and final gradient below `1e-4`; `140-tree-80` reports 80 iterations, finite deviance `2997.7831906682172` and no warnings. Each prediction file has 996 unique series/week rows, finite nonnegative predictions and 960 observed targets. No scientific ranking is present.

Authenticated V2c and V2b files are **byte-identical** for `permitted-data.json`, `baselines.json`, `results.json` and both learned `.predictions.json` files. Each trial's frozen identity, training loss, optimizer diagnostics and complete result object also match exactly. This establishes observed smoke-output equivalence without repeating the prior exhaustive scientific review. It does not itself exercise confirmation qualification serialization; that seam has the separate focused correction regression cited above.

The authoritative outside aggregate peak is **397,742,080 bytes**, identical in retained wrapper status, capture and final cgroup sensor. All memory events are zero. Limits remain 2 GiB, zero swap, 200% CPU quota, two native threads and a 180-second smoke hard limit. Elapsed time is **20.777340781 seconds**, below the 120-second drain. Four supervisor heartbeats have maximum adjacent progress gap 5.012477 seconds; 24 outside samples have maximum gap 1.014643 seconds. Fresh reservation observations meet resource floors. Final state is successful `active/exited`, `MainPID=0`, zero exit status and empty cgroup, followed by verified release of the already-empty retained unit; no cleanup/termination actions are recorded.

Run counters are `decoded_target_rows=25152`, `highest_decoded_week=144`, `protected_target_rows=0`. These describe this run only. The updated provenance explicitly discloses previously observed selection and partial confirmation data, including prior authorized weeks 153–160 access. This maintenance rerun does not make confirmation blind, erase that exposure or permit retuning.

The official nine-fit preparation gates pass:

```text
(max(10.012751762000335, 10.010064989000966)
 + 0.24344951400053105) × 9 × 2
 = 184.61162296801558 seconds < 480 seconds

397742080 × 1.25 = 497177600 bytes < 2147483648 bytes
```

**PASS for engineering smoke and preparation feasibility only.** `selection_result=null`, `scientific_result=false` and `publication_ready=false` remain unchanged. The permitted next action is preparation of new `oj-selection-v2c-20261118`, bound to this smoke and the unchanged V2 science: three candidates × origins 140/144/148, seed 20261118, nine fits, 600/480-second hard/drain limits and no confirmation-label permission. A distinct reviewer must provide `authorize-selection`; authorization then stops before a new authorization-bound `execute-only` review. This document authorizes neither phase.
