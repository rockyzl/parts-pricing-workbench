# Pricing Workbench V2 — product and interface specification

Prepared 2026-11-18. **Design specification only.** This document defines a future interface; it does not establish that its models, authentication, upload service, reviews, or publication are implemented. It creates no frontend code, assets, accounts, or cloud resources and does not change V1.

Implementation starts after the model/engine evidence and relevant backend contracts pass review. Phase 1 is verified; Phase 2 is being built. Any example model result below is a field to populate from a verified artifact, never a prescribed successful outcome.

Sources: [V2 plan, Phase 4](pricing-engine-v2-plan.zh.md#phase-4--定价工作台审核与价格版本), [Phase 1 handoff](pricing-phase1-handoff.md), [weekly data contract](data-contracts/weekly-pricing-v1.md), [deployment preflight](deployment-preflight-2026-11-17.md), [model protocol](model-protocol-v1.md), and the existing V1 HTML, JavaScript, styles, and screenshot. The model protocol is still subject to its independent review process; bind the interface to the accepted version when implementation begins.

## 1. The product in one sentence

Help a pricing analyst **plan prices for the next four weeks**, understand the evidence for every catalog decision, and hand one version to a different reviewer for publication to a demo price ledger.

The default reference case is **orange juice: three brands across 83 stores, making 249 store–brand series**. Its business unit is a brand at a store, not a vehicle part, an individual quote, or 249 distinct products. The visible product name is **Pricing Workbench**; the repository name need not dictate the interface title.

The opening headline is **“Plan prices for the next 4 weeks.”** The sentence below is **“Review the sales history, compare a price plan, and send it for approval.”** One short context line says **“Orange juice example · 3 brands · 83 stores · 249 store–brand series.”** No landing-page hero, technology logo grid, chat prompt, or wall of capability cards precedes the work.

Success means a first-time visitor can answer these questions from the visible workflow:

1. Which records are we using, and what is missing?
2. What has the model actually been tested on?
3. Which prices would change, which stay, and why?
4. What did another person approve?
5. Which exact version entered the demo ledger?

## 2. One workspace, five steps

Use one persistent plan header and a horizontal sequence:

**Import → Check data & model → Plan prices → Review → Publish**

These are real sequential stages, so step numbers and completion marks carry meaning. Each stage has one main content surface and one next action. Earlier stages remain inspectable; changing an input creates a new draft revision instead of silently updating the reviewed plan. Do not display five full forms simultaneously.

The public reference example arrives already imported. It opens at **Check data & model**, with a short “Example loaded” label, actual records, and the next action **“View example price plan.”** Visitors can inspect every stage of a persisted, verified example; they do not start jobs or edit shared samples. An invited analyst gets **“Create my plan”**, which creates a private draft from the reference input, or **“Import my data.”** These actions require real authorization.

Global navigation stays small: **Workspace**, **Price versions**, **Learn**; language and account controls sit at the right. The five-step sequence belongs inside Workspace. Data and Model are two views within step 2, not two additional admin applications. View tabs never change account permissions.

The persistent context line includes dataset name, history cutoff, four-week period, draft/review status, and revision. Full hashes and machine identifiers live in **“Version details.”** Changing dataset, cutoff, or model is a deliberate draft action. Browser Back, refresh, and direct links restore the server-owned stage and revision.

## 3. Reference facts and display rules

| Subject | Established evidence | Interface treatment |
|---|---|---|
| Full OJ source | 28,947 observed rows; 3 brands; 83 stores; 249 series | Show these counts for the complete reference snapshot only. Earlier snapshots and uploads use their own returned counts. |
| Time | Source weeks 40–160; calendar mapping unverified | Reference history ends at week 160. The next plan covers **source weeks 161–164**. Never invent calendar dates, holidays, or a current-week claim. |
| Missing observations | 1,182 absent grid records: 180 before first observation and 1,002 later gaps | Say **“No record”**; distinguish the two kinds in detail. A gap is neither zero sales nor proof of a stockout. |
| Sales | Reconstructed as unrounded `exp(logmove)` | Primary label **“Recorded sales · source units”**; adjacent provenance **“Derived from source log sales.”** Display rounded values without rounding stored/exported observations to integers. |
| Price | Observed price; exact currency/package mapping unverified | Use **“Reference price · last observed”**, a bare number, and **“Source price units.”** No dollar/pound sign, 64-ounce label, or “current list price” claim. |
| Feature advertising | 6,868 observed featured rows | Label **“Feature advertising”**, not generic promotion. Distinguish Yes / No / Unknown. |
| Outliers | 3,217 descriptive sales flags, retained | Present **“Unusual sales records”** as an inspectable filter; never claim they were removed or are necessarily errors. |
| Cost, inventory, availability, market quotes, returns | Unavailable in the OJ case | Show missing state where relevant; add separate explicit business scenarios only through their own versioned inputs. |
| Model quality / price qualification | No verified result established by this design | Populate only from reviewed model evidence. An all-hold plan is an acceptable and informative result. |

The full-source missing-record total is not the same denominator as “coverage since first observation.” Use the latter in series rows and explain the former in the dataset audit. Aggregate sales plots include an observed-series count by week so changing coverage is visible.

Use four provenance labels consistently: **Observed**, **Derived**, **Scenario**, **Missing**. They accompany the affected value or field; they are not four giant explanatory cards. For uploads, a currency or cost asserted by an uploader remains source-attributed, not independently verified by the app. Keep unit/currency compatibility explicit when combining tables.

No fabricated series values, preview curves, model scores, saved reviews, or completed jobs may appear to make a screen look populated. Wireframe placeholders in this document are bindings, not content to ship.

## 4. Visual direction: the store planning sheet

The interface borrows its structure from a regional buyer's planning sheet: store and brand identities stay anchored at the left; evidence, proposed change, and disposition line up across the page. The distinctive element is a **four-week decision band** above the catalog: the same four source weeks recur in the plan, review, and published version. Each band shows the selected price schedule and feature-advertising assumptions for the focused row. It connects one business period through the workflow without becoming a decorative timeline.

Spend visual emphasis on that band and the catalog. Use quiet white surfaces, a cool blue-gray work area, strong tabular alignment, and one cobalt primary action. Corners are modest; avoid nested floating cards and excessive shadows. Status is communicated with words and restrained markers, not traffic-light backgrounds across every row.

| Base token | Value | Role |
|---|---|---|
| Canvas | `#F3F6FA` | Page background, frozen table columns |
| Sheet | `#FFFFFF` | Main working surface |
| Ink | `#172B3A` | Text, chart axes, headings |
| Secondary | `#526474` | Supporting text |
| Action | `#174FBD` | Primary controls, selected step, visible focus |
| Evidence | `#0C6C5B` | Observed-series marks and approved status accent |

Additional functional tokens: divider `#D6DFE8`, attention text `#855200`, error text `#B42332`. Use attention/error on white with a text label; verify final contrast in the implemented component, including disabled/selected states. Historical sales use Evidence; model predictions use Action plus a dashed stroke; missing data use a gap marker. Positive scenario change is not automatically green approval.

Typography: **Barlow Semi Condensed 600** for the restrained workspace title and step heading; **IBM Plex Sans 400/500/600** for navigation, explanations, and tables; **IBM Plex Mono 400/500** for prices, week indices, and identifiers where alignment helps. If later packaged, fonts are self-hosted with their licenses; no runtime font CDN. System fallbacks are condensed sans / Segoe UI / monospace. Chinese uses an available CJK sans such as Noto Sans CJK SC or Microsoft YaHei; preserve the same hierarchy and allow wider labels.

Type scale: title 32/38 px; step heading 24/30; body 16/24; table 14/20; caption 13/18. Use tabular figures in numeric columns. Do not compress explanatory text below 13 px. Spacing follows 4/8/12/16/24/32/48 px. Main desktop width is at most 1440 px, with 24–32 px gutters. Table rows are approximately 48 px high; controls have a minimum 44 px hit area. Surfaces use 8 px radii, controls 6 px. Dividers group information; shadows are reserved for an overlay.

Motion communicates a state change only: short drawer expansion or focus movement, around 120–180 ms. No animated chart drawing, rolling counters, simulation that fills itself, or synthetic loading percentage. Respect reduced motion.

### Initial desktop view

```text
Pricing Workbench       Workspace  Price versions  Learn       中文讲解  Sign in

Plan prices for the next 4 weeks
Orange juice example · 3 brands · 83 stores · 249 store–brand series
History through week 160                      Plan: source weeks 161–164

✓ Import — 2 Check data & model — 3 Plan prices — 4 Review — 5 Publish

Data | Model evidence                           Example loaded · Read only

Recorded sales by week                          What is in this file?
[actual history with gaps and coverage]         28,947 recorded observations
[source week axis and labeled units]           1,182 missing grid records
                                               [Inspect missing records]

Store [All]  Brand [All]  Search [              ]   [Unusual sales] [More filters]
Store / brand | Last price | Observed weeks | Price changes | Records
[actual rows from the frozen snapshot, including flagged/gapped series]

                          [View model evidence]  [View example price plan →]
```

The initial viewport contains real rows, a readable chart, and a next action. The context line is a sentence-sized summary, not a row of oversized KPIs. Dataset and model details expand beside or below the selected content.

### Plan and review desktop view

```text
Plan prices             Source weeks 161 · 162 · 163 · 164          Draft r{n}
Scope: {all series}      {change} change · {hold} hold · {attention} need action
[Rules & business inputs]                                      [Compare prices]

Store / brand | Reference | Proposed | Change | Decision / reason
...                                                               ┌─────────┐
selected real store–brand row                                      │ History │
...                                                               │ Prices  │
...                                                               │ Reason  │
                                                                  └─────────┘
Resolved {n} of {scope}                                     [Send for review →]
```

At wide widths the detail pane uses roughly 38% of the content area, with the catalog retaining 62%. Close it to recover the full table. At smaller widths it opens as a full-width detail view with **“Back to catalog”**, preserving filters and focus. One row is examined in depth without changing the plan's whole-catalog scope.

## 5. The five steps in detail

### Step 1 — Import

The reference example is selected and loaded on first visit. An analyst can choose **“Use orange juice example”** or **“Import weekly sales CSV.”** The latter accepts the existing weekly-observation contract, not raw transaction lines or arbitrary spreadsheets. Parquet is not offered until its bounded parser exists.

Before upload, show a small required-column example and **“Download CSV template.”** The template is visibly synthetic and never used as model evidence. Explain the only consequential time choice: source week indices or real completed calendar weeks. Upload preview separates file validation from saving the dataset. No user-authored code or uploaded model file is accepted.

After parsing, show row count, series count, units/currency, time range, and the first authorized records. The confirmation action is **“Save dataset and check data.”** Display exact upload limits supplied by the backend capability response. Existing data-contract defaults include 10 MiB, 100,000 observations, and 2,000 series; these must not become a claim of measured service capacity or a second client-only validation rule.

Errors identify row and field with a repair action: **“Row 18: units must be zero or greater. Put returns in returns_units.”** Duplicate-key errors identify both affected row numbers. Unknown columns are reported instead of silently ignored. Show a downloadable error report if the backend supplies one; do not echo unsafe free text. Valid existing work remains accessible after a failed upload.

Imported business data, summaries, and derived plans stay in the authorized private workspace. Publishing a demo price version does not make an uploaded dataset public.

### Step 2 — Check data & model

**Data view.** Lead with an observed-sales chart and a visible records table, not just quality scores. Chart range defaults to the recent 26 source weeks, with **“All history”** available. The chart title names its filter and unit. A coverage strip shows how many series have observations each week. Missing weeks break a series line; zero is plotted only when observed. Use a separate aligned price chart for a selected series, not an unexplained dual axis. Feature-advertising markers sit on the same week axis; their presence makes no causal claim.

The catalog table shows store, brand, last observed price and week, observed weeks / weeks since first observation, and consecutive-week price changes. Expand a row to see actual week, recorded sales, price, feature-advertising state, and record status. **“Source details”** reveals source row, known-at time, snapshot, and transformations. A **“Missing records”** filter exposes gaps rather than hiding them. A **“Price changes”** column is descriptive evidence, not eligibility.

Chart explanation uses a computed statement such as **“This series has records for {observed} of {span} weeks.”** Only describe a trend or difference if the underlying calculation is provided. Avoid canned claims that sales “rose after a promotion” or that the model found a pattern.

**Model evidence view.** Lead with one business question: **“How well did predictions match recorded sales?”** Show a baseline comparison table with model label, average absolute sales error, change versus baseline, scored observations, and result status. All numbers use the same observed-target mask and horizon. Lower error means closer predictions; a negative improvement is retained. **“See each test period”** expands the time-fold table and errors by horizon/history/volume group. Preserve failed and incomplete trials; incomplete runs have no winner.

The fixed task label is **“Historical check · observed prices and advertising.”** Its one-sentence explanation is **“These predictions use the prices and feature advertising that were later recorded.”** Separate it visibly from **“Future plan scenario,”** which uses explicitly entered prices and advertising. A historical score must not be relabeled as future-plan accuracy.

Display two independent outcomes: **“Sales forecast”** and **“Price comparison.”** A useful forecast can still show **“Price comparison unavailable — too little price variation”** or another returned reason. Never create a generic “AI confidence” score. Protocol v1 provides no prediction intervals; do not draw confidence ribbons. Shared brand coefficients belong under **“How price enters the model”**, labeled conditional associations rather than causal elasticities.

Invited analysts see **“Train and evaluate”** when a compatible verified run does not exist, or **“Train a new version”** when it does. The action starts a fixed server job and never publishes a plan. Show queued/running/completed/failed states, actual completed tasks if exposed, elapsed time, and a stable run link. Reload resumes observation of that run. Old verified results remain labeled as the previous version; they are not silently reused for a changed dataset.

**“How this was built”** in Learn/details explains the actual scikit-learn estimators, fitted shared brand response, baseline, time boundaries, backend execution, artifact versions, and source references once present. It reflects the selected run; do not present installed libraries or planned components as completed modeling.

### Step 3 — Plan prices

Start with the four-week period and full catalog. For OJ this is weeks 161–164 after cutoff 160. A proposed seed model must be compatible with that cutoff and separately reviewed after confirmation/refit; do not silently turn an evaluation-fold model into the final planning model.

The default price schedule is one price held across all four weeks per series. The underlying scenario still has four weekly price/ad records. Allow weekly editing in details only when supported by the verified backend, and show all four values in review/export. Do not introduce a false calendar-date picker for OJ.

**Business inputs.** A compact expandable sheet groups objective, cost, inventory, feature-advertising plan, and rules. Each value has its provenance state and applicable series/week range. Observations and business inputs remain separate versions. OJ cost and inventory start Missing; there is no hidden 60% cost, unlimited-stock assumption, external competitor price, or fabricated promotion calendar.

An explicit **“Use example business assumptions”** action may create a named scenario version for the private analyst walkthrough. Suggested teaching settings are a unit cost equal to 60% of each frozen reference price, a 20% minimum margin, a ±5% change limit, and a cap of 20 changed series. These are illustrative settings, not established business facts or approved defaults. Show the formula before applying it; freeze the resulting per-series costs. Inventory remains Missing unless the user explicitly supplies a scenario quantity. The initial feature-advertising scenario can explicitly hold the last observed state for four weeks; show Unknown where it was unknown and let the analyst edit it. No scenario setting may mutate an observed record.

Without compatible cost, a contribution-margin objective is unavailable with the specific instruction **“Add unit costs or choose a supported comparison.”** Forecast viewing and a hold/manual-review outcome remain possible. With scenario cost, label the output **“Estimated contribution · scenario”** in source-scale units for OJ; never revenue, audited profit, or achieved uplift. Lead the OJ comparison with price change and scenario margin percentages, which are easier to interpret than large native-scale totals; show contribution amounts in details with their basis. Never promote the source value proxy to a business-revenue KPI. Margin uses `(price − cost) / price`; details distinguish margin from markup. Missing inventory means no stock feasibility check was performed, not that supply is sufficient.

**“Compare prices”** freezes the data/model/business-input/rule versions and requests a catalog run. The backend determines candidates, exclusions, eligibility, and results. The browser does not reconstruct an alternative optimizer. Constraints include any applicable cost/margin floor, allowed change, supplied contractual bounds, observed training-price support, and verified portfolio limits. Unsupported rules remain unavailable rather than decorative enabled controls.

Every series receives one primary disposition: **Change proposed**, **Hold**, **Needs data**, **Rule conflict**, or **Needs judgment**, with a plain reason. Model fallback is a separate attribute. There is one row per scope member, including failures and no-price outcomes; filtering cannot change the denominator. Sort attention first with a stable secondary store/brand order. Provide explicit sorting rather than having rows jump during review.

Primary columns: store/brand, reference price, proposed price, percentage change, disposition, and reason. Estimated four-week sales and contribution can be added with a column chooser, with unit/scenario headings preserved. Scenario totals use the same horizon and covered rows as their hold comparison. Show excluded/missing coverage next to any total. Mixed incompatible units/currencies are not summed. Totals under independent demand assumptions are not labeled a global optimum or substitution-aware gain.

**Row detail explains the choice in this order:**

1. **History:** observed sales and price plots, ad marks, and the actual recent-record table.
2. **Comparison:** current/reference hold alongside every tested candidate, four-week predicted recorded sales, applicable scenario contribution, feasible/not feasible, and the precise reason. Hold is always retained as a comparator even if a rule makes it ineligible for publication.
3. **Allowed prices:** a modest range diagram marks the reference, hard bounds, and historical support; the table remains the authoritative accessible representation. Show lower and upper bounds individually when their intersection is empty.
4. **Decision:** the selected candidate or hold reason, the model's supported use, and relevant business input states. A sentence such as **“This price has the highest estimated contribution among the allowed prices tested”** appears only when the returned result supports it. A nonoptimal/timeout state must not use that sentence.

Changing a price or business input marks the draft **“Needs recalculation.”** Keep the old comparison visible as an older revision, with its controls disabled for submission. A rule conflict never receives a forced recommended price. A reference price that violates a hard rule cannot be silently approved as a fallback hold.

### Step 4 — Review

The analyst selects **“Send for review”** after every scope row has a proposed disposition or an explicit reason to exclude. The submitted revision is immutable. The reviewer opens the same catalog and period, with proposed price, prior/reference price, rationale, and changed inputs immediately visible.

Reviewer actions are **“Approve”**, **“Request revision”**, and **“Reject.”** An approval may cover selected eligible rows after showing the selection count and scope; **“Approve all filtered”** must never ambiguously mean all 249 rows. A rejection or requested revision requires a reason. An analyst uses **“Revise price”** or **“Hold reference price”**, supplies a reason, and resubmits. A reviewer can suggest a value in a revision request; it is not an executable price until an analyst makes a new version. This preserves an understandable two-person flow.

On any executable plan change, create a new revision and invalidate the current approval for publication. Preserve previous events for comparison; never overwrite them. The reviewer sees **“Changed since your last review”** with actual differences and approves the current snapshot. The server rejects self-approval and stale revisions regardless of which buttons the browser displays.

The footer shows a reconciled count: **“{resolved} of {scope} rows resolved.”** Before publication, every row must be approved as a change/feasible hold or explicitly rejected/excluded with a reason. An unresolved conflict, missing-data row, or pending review blocks completion. Reviewers may explicitly exclude those rows; exclusions remain in the coverage manifest and are never emitted as price instructions.

The event history names actor, action, revision, comment, and timestamp from persisted records. Use **“Saved”** only after server acknowledgement. A refresh or a second authorized account sees the same state. A browser-only note is never presented as a shared review.

### Step 5 — Publish

The action is **“Publish to demo ledger.”** Its confirmation shows destination, version, source-week period or verified calendar period, approved changes/holds, and rejected/excluded count. One short line reads **“Creates a version in this workspace and a downloadable pricebook.”** It is not a live store/ERP update.

Publication uses only the approved current revision. A retry returns the same created version; refreshing does not publish again. Server checks cover permission, reviewer identity, revision, input versions, scope accounting, and unresolved rows. The actor allowed to publish must be supplied by the final role policy, not inferred from a client view.

The result is a persistent version page with approved price rows, period, source plan/revision, reviewer, publisher, event history, and **“Download pricebook”** / **“Download coverage report.”** The pricebook contains only approved executable rows, including approved feasible holds if selected by the export contract. The coverage report accounts for every scope row, including rejected/excluded reasons. Export includes unit/currency status, price basis, weekly schedule, scenario labels, and immutable version references; model/data precision is not lost by screen rounding.

Publication to the private demo ledger does not grant public access. Public seed examples are separately curated/read-only; user uploads and their aggregates remain workspace-private. **“Create revision”** starts a new draft. **“Restore earlier prices”**, if later offered, creates a new reviewed version rather than rewriting history.

The post-publication link **“Review historical predictions”** returns to the model evidence. Future weeks 161–164 have no observed outcomes in the seed; display **“No later records loaded.”** Do not animate or invent follow-up sales, profit uplift, or a successful rollout. Future imported outcomes can populate a separate observations view with coverage and known-at dates; causal business effects require their own study.

## 6. One coherent guided example

The walkthrough follows one saved plan from beginning to end, never swaps to a different dataset or silently changes rules between screens.

| Moment | Visitor sees / analyst does | Evidence required |
|---|---|---|
| Start | “Plan prices for the next 4 weeks,” OJ loaded through week 160 | Verified 249-series snapshot and real records |
| Inspect | Open a catalog row; see its recorded sales, prices, feature-advertising flags, and any gaps | Snapshot history, no generated sparkline |
| Check model | Compare recent-sales baseline with the actually selected model; open its historical test periods | Reviewed run, comparable targets, explicit conditional task |
| Set plan | Select the explicit example business assumptions and four-week ad scenario in a private draft | Saved scenario input version; no source facts overwritten |
| Compare | Calculate dispositions for all 249 series; focus the first eligible candidate if one exists | Actual engine results and rules; no mandated price change |
| Revise | Analyst holds or adjusts that row with a reason, recalculates, and submits | Valid candidate/override plus new revision |
| Review | A different invited reviewer checks the change and resolves the scope | Server-authenticated, persisted review events |
| Publish | Authorized publisher creates the demo ledger version and exports it | Approved current revision and complete coverage accounting |

Select the focused example row deterministically from the verified result: first a qualified feasible candidate by documented stable sort; otherwise a hold with its real reason. Freeze the chosen series ID in the sample manifest. Never invent a store identifier, choose a row solely to manufacture a positive story, or hide failed series. If no series qualifies, the narrative is **“The evidence supports holding these prices; review and record that decision.”** A verified rule-only scenario can be explored separately with its own label, not relabeled as model pricing.

Public viewers follow the persisted reference walkthrough with **“View next step.”** They can filter, expand evidence, inspect review events, and download only permitted public example exports. They cannot simulate being the reviewer by selecting a role. Invited users perform actual creation/revision/training in their private workspace. The seed must not claim that a visitor's inspection approved or published anything.

## 7. Identity, permissions, and durable state

| Account state | Visible capabilities |
|---|---|
| Public viewer | Browse curated published seed artifacts; inspect sample evidence; permitted seed exports |
| Signed-in user without a pricing invitation | Viewer capability; clear “This account has no workspace access” status |
| Invited analyst | Authorized workspace data; CSV upload; bounded fixed training; private plans; revisions and submission |
| Invited reviewer | Authorized workspace review queue and evidence; approval/revision request/rejection; no self-approval |
| Owner | Invitation/access and execution limits according to server policy; no implicit bypass of review rules |

Use the verified email/password provider path when implemented. The sign-in screen says **“Sign in to your pricing workspace.”** It does not display a fake company SSO button or a role selector. The account menu can show the server-issued role as read-only text. The public workspace can show “Viewing example” as content context, never as an authorization role switch.

The backend supplies allowed actions and enforces them independently. The interface handles expired sessions by preserving only safe unsent form state and requesting sign-in; it rechecks current revision/permission before resubmitting. Do not place passwords, privileged sample credentials, tokens, or raw business data in browser history/export URLs. Local storage may retain language or column preferences; it is not the source of truth for business records.

## 8. Waiting, empty, conflict, and failure states

| State | Plain-language response and next action |
|---|---|
| First public load | “Loading the orange juice example…” Keep layout stable; no fabricated counts or graph. |
| No private dataset | “Import weekly sales to start a plan.” Offer template and reference example. |
| Import rejected | Specific field/row/limit; return to editable upload preview. No partial dataset is called ready. |
| No records at cutoff | “No records were known by this week.” Choose a later cutoff or inspect import timing. |
| Chart has gaps | Break the line; “No record for this week.” No zero-filled interpolation. |
| Training queued | “Waiting for the training slot.” Show request ID/link and accepted time; no invented queue position. |
| Training running | “Training and checking models.” Show only measured stages/completed-task counts and elapsed time. Leaving the page does not start another job. |
| Training unavailable / quota | “Training is paused for this workspace” or server-supplied next eligible time. Keep prior verified results inspectable. |
| Training failed / timed out | “This run did not complete. The previous model is unchanged.” Retain failure details and a deliberate retry action if allowed. |
| Forecast available, pricing unsupported | Show forecasts and the specific price-comparison block reason; offer hold or supported manual/rule review. |
| Missing cost | “Add unit costs to compare contribution.” Show scenario creation at that field. |
| Rule conflict | “The minimum allowed price is above the maximum.” Name both rules, values, and the input to revise. |
| Edited inputs | “Inputs changed. Compare prices again.” Current submission/approval actions remain unavailable. |
| Concurrent revision | “A newer revision was saved.” Offer “View changes” and safe draft reconciliation; never overwrite silently. |
| Save acknowledgement uncertain | “Checking whether your changes were saved…” Reconcile the same operation; do not claim success or duplicate it. |
| Publish blocked | Exact blocking count and “View unresolved rows.” Preserve the already approved rows. |
| Publish response lost | Reconcile the publication key and link to the created version if present. No blind second publication. |
| Session expired | “Sign in again to continue.” Restore the safe draft after auth and revalidation. |
| No later outcome data | “No later records loaded.” Link to the existing historical evaluation instead of showing an empty success chart. |

Use inline validation near the control plus a linked summary for multi-field errors. A toast is supplementary, never the only place to learn why an action failed. Cancellation is exposed only if the backend actually supports it; do not imply that closing a tab cancels a training job.

## 9. English default, Chinese learning mode, mobile, and accessibility

English is the default. **“中文讲解”** switches navigation, controls, accessible names, status/reason text, and brief explanatory copy without changing the plan or model. The return control is **“English.”** Chinese adds a concise learning explanation where helpful, not another full tutorial panel. Keep record identifiers and immutable version IDs unchanged. Persist the language preference separately from the plan; set the document language correctly.

| English | Chinese learning wording |
|---|---|
| Plan prices for the next 4 weeks | 制定未来 4 周的价格方案 |
| Reference price · last observed | 参考价 · 最近一次记录的价格 |
| Historical check · observed prices and advertising | 历史检验 · 使用当时实际记录的价格与广告状态 |
| Future plan scenario | 未来计划情景 |
| Hold | 保持参考价 |
| No record | 缺少记录 |
| Request revision | 要求修改 |
| Publish to demo ledger | 发布到演示价格台账 |

At 1024 px and below, remove the side-by-side detail pane; use a full-width drilldown. At 768 px and below, the stepper shows **“Step 3 of 5 · Plan prices”** with a menu for the remaining stages. At 360–430 px, show store/brand, reference → proposed, disposition, and an explicit detail button in each catalog row. Numeric comparison tables scroll within a labeled region with a visible scroll cue; the page itself must not require horizontal scrolling. Keep scope counts and units visible. The four-week band becomes two rows of two weeks if needed; no tiny four-column form.

Mobile has the same review permissions and server validation. A sticky bottom next-action bar respects the safe area and cannot cover the last record or keyboard focus. Large bulk selections receive an explicit count and review summary on every viewport. Desktop sticky columns/headers must not cover content at 200% zoom; reflow at 400% is part of verification.

Target WCAG 2.2 AA. Use semantic tables with captions, scoped headers, sortable header buttons, and a separate row-detail control; do not turn the entire table into an undocumented keyboard grid. All charts have a concise text description and an accessible data table. Direction/sign, line styles, icons, and labels supplement color. Focus is visible, modal/detail focus returns to the invoking row, and controls remain operable by keyboard. Announce save/job transitions with restrained live regions; do not announce every polling update. Respect reduced motion and text scaling. Error messages link to affected fields. Test English and Chinese wrapping with real long reasons.

## 10. Data contracts the implementation must settle

This is a logical interface contract, not a claim that HTTP endpoints or schemas below already exist. Use existing Phase 1 fields where present; adapters must preserve their meanings. Final endpoint names belong to backend implementation.

| Object | UI needs | Current evidence / open boundary |
|---|---|---|
| Dataset/snapshot | Versions, cutoff, grain, unit/currency/price basis, time axis, counts, provenance states, authorized visibility | Phase 1 supplies these locally. HTTP transport and access filtering remain future work. |
| Catalog/history | Stable series key, item/site, observed/first-known/last-observed weeks, price support, gaps, records with source-row/known-at | `analyze()` and `series_history()` provide local descriptive structures. Never infer price eligibility from `distinct_prices` alone. |
| Model run | Run/model IDs, lifecycle, task, training cutoff, protocol, validation origins, metrics/masks, failed trials, publication/verification state | Phase 2 agent plans these; bind to reviewed artifacts. The post-confirmation refit through 160 needs its own reviewed proposal. |
| Forecast row | Series, origin, target week/horizon, prediction, model ID, prediction status/fallback reason, price/ad conditions and their provenance | Separate `conditional_observed_conditions` from `explicit_plan_scenario`. No v1 intervals. |
| Pricing qualification | Qualified flag, reason codes, origin support, permitted price range, response source, fold stability, review state | Price eligibility is separate from forecast selection. Until verified, do not show “qualified.” |
| Business inputs | Value, observed/derived/scenario/missing state, source/version, series scope, unit/currency, effective interval, known-at | Separate versioned input tables remain to be implemented. Need an explicit rule for null-currency OJ scenario units. |
| Plan/candidates | Scope manifest, period, revision, frozen input/model/rule references, every candidate including hold, feasibility reasons, objective, disposition, solver state, coverage/totals | Phase 3 contract needed. Constant-price default still emits four explicit weekly conditions. |
| Review | Actor, permissions, exact proposal/plan revision, action, reason, timestamp, concurrency token, previous-event linkage | Persisted server state required; different reviewer identity and stale-write rejection. |
| Price version | Idempotent publication key, approved revision, published executable rows, rejected/excluded manifest, destination, actor/time, export metadata, visibility | Demo ledger contract needed; private publication must not create a public link. |
| Job/capabilities | Actual limits, allowed actions, stages/progress if known, safe errors, timestamps, retry/cancel capability | Backend owns resource limits and status; no percentage fabricated by the client. |

### Decisions sent to the model/backend owners

- **Confirmed with project owner:** use cutoff 160 and source weeks 161–164; show all 249 source-series dispositions; permit publication of an approved subset only after all other rows are explicitly resolved as holds/rejections/exclusions with reasons and reconciled totals; uploads remain private even after ledger publication.
- **Confirmed with model implementer:** the two forecast tasks remain distinct; model rows include origin/target/horizon and fallback state; support and conditional metrics are separate from pricing qualification; protocol v1 has no intervals. A refit through 160 is a separate post-confirmation decision, not an existing result.
- **Before model evidence design is bound:** which accepted protocol/run/model IDs and verification states are eligible to appear in the reference example? Which folds/rows are scored, and how are baseline, selected forecaster, and price-response model distinguished when different?
- **Before candidate UI implementation:** what are the accepted scenario-unit semantics for null-currency OJ, legal price precision/ticks, minimum supported increment, candidate-generation bounds, manual-override policy, and portfolio solver statuses? Can the backend support the illustrative cost/margin/change-count settings above? Do not expose controls it cannot enforce.
- **Before the default plan is calculable:** is the approved model an actual cutoff-160 refit, and what is its compatible dataset/snapshot contract? What should the backend return for a plan when no series qualifies? Required behavior is a full scope with explicit fallback, not an empty successful plan.
- **Before review/publication:** which server role may publish; do rejected rows terminate scope or require replacement; how are feasible holds approved/exported; and is approval invalidation whole-plan as proposed here? Freeze these semantics and event shapes before implementation.
- **Before exports/public samples:** which actual record extracts/artifacts may be served publicly under the source conditions; what exact pricebook and coverage schemas are supported; and what server check prevents a private dataset/summary from being attached to the public seed? Public viewing requires curated artifacts, not access to all storage.
- **Before waiting/error screens:** which persisted job stages, heartbeat, reconciliation state, quota reset, safe error identifiers, and cancellation capabilities actually exist? Final copy is driven by those facts, not guessed infrastructure behavior.

## 11. Design review and later implementation acceptance

The central design choice is a catalog planning sheet with a repeated four-week decision band. This replaces the previous one-product, three-panel interaction because the business decision now covers a store–brand catalog and a shared approval period. The five steps reveal the work in order; the user never has to understand job infrastructure to find the next action. Source, model, and architecture detail remains one click away from the evidence it explains.

Before implementing visuals, verify the data/model/candidate/review contract gates above. The eventual UI acceptance walkthrough must demonstrate:

- First load shows the real OJ subject, source-week period, actual observations, and a clear next action; no vehicle-parts disguise or unsupported success claim.
- Every frozen scope row remains traceable across data, plan, review, and coverage export. Counts reconcile with the snapshot; no “best example only” catalog.
- Actual model results, including failures and a forecast-only/pricing-blocked case, are understandable beside a baseline. Missing data and uncertainty are not converted into zeros or invented intervals.
- A real analyst uploads, trains through the fixed backend, calculates, and submits; a separate reviewer can approve and request a revision. Changing the revision prevents stale publication.
- The review survives refresh/restart and appears for the second authorized account. Anonymous or uninvited users cannot upload, train, review, publish, or access private artifacts.
- A complete approved plan publishes once to the demo ledger, with immutable version and reconciled exports. A retry does not duplicate it. No later outcome is shown until observed data exists.
- English/Chinese, keyboard/screen-reader use, 200%/400% zoom, and desktop/mobile layouts are tested against real records, long reasons, empty states, concurrent revision, and failed jobs.

This acceptance list describes future verification. No frontend implementation, model performance, public deployment, or successful end-to-end run is asserted by this design document.
