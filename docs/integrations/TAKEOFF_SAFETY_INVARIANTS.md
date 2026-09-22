# Civil takeoff safety invariants

Status: required invariants for the runnable takeoff vertical slice. These are product rules, not optional implementation notes.

## 1. Source identity is immutable evidence

Every takeoff/evidence item must resolve to a document hash + sheet/page identity. Reopening or syncing a workspace must verify that the current source hash matches the retained source identity. A matching project id alone is not sufficient.

If a drawing revision/addendum supersedes a source document, dependent proposals are marked stale and returned to review. They are never silently carried forward as current quantities.

## 2. Canonical geometry is resolution-independent

Rendered canvas pixels are a view, not the durable geometry contract. Persist geometry in source PDF coordinates or normalized sheet coordinates together with the page rotation and source dimensions. Any canvas/OpenTakeoff/Bluebeam pixel frame is derived from that canonical representation.

A re-render at another DPI, a reopen, or a different screen zoom must not change a measured quantity.

## 3. Scale is a transform on a region, not one page-wide number

A civil sheet can contain plan, profile, section, and detail views at different scales. Each `ScaleRegion` owns a bounded region and a reviewed transform.

Plan views normally use an isotropic transform. Profiles/details may require distinct horizontal and vertical scale factors. A generic Euclidean line length must not be computed from an anisotropic profile view unless the rule explicitly defines the intended axis/measurement semantics.

A summable geometry must be contained by exactly one compatible, human-confirmed scale region. Crossing regions, missing scale, ambiguous scale, or incompatible anisotropic scale is a blocker.

Existing PDF/Bluebeam viewport data may be imported as scale-region **evidence/suggestions**, but it is not silently trusted as human confirmation.

## 4. Human authority is cryptographically/logically distinct from an agent call

Omitting `approve_takeoff` from an MCP tool list is not sufficient protection. The application service must distinguish human-authorized operations from agent-originated calls.

Final approval, scale confirmation, clearing a human review gate, and final export require a local UI action or a short-lived/single-use confirmation capability minted by that UI. Audit events record the actor and authority source.

## 5. Concurrent UI/agent writes cannot overwrite each other

The takeoff project/workspace carries a monotonically increasing revision/event sequence. Every mutation uses compare-and-swap semantics (`expected_revision`). If the UI and an agent edit the same state concurrently, the stale writer is rejected and must refresh.

Persistence remains atomic, but atomic files alone do not solve logical lost updates.

## 6. Geometry supports real estimating semantics

Before normal area takeoff use, the model must represent:

- polygon outer rings and holes/deductions;
- explicit deduct records where appropriate;
- line/polygon split operations for mixed scope;
- duplicate/overlap QA so two proposals cannot silently double-count the same work;
- count-marker identity/de-duplication for EA takeoffs.

An irregular driveway or roadwork region must not be simplified to a rectangle merely because the storage model is simpler.

## 7. Scope completeness is first-class

Live estimating cannot measure a `silent miss` directly without a gold set. The runtime therefore maintains a `ScopeLedger` for every requested takeoff task.

Each expected rule/bid item/sheet target ends in an explicit state such as:

- `PROPOSED`;
- `WITHHELD`;
- `NOT_PRESENT` with evidence of search;
- `NOT_APPLICABLE` with reason;
- `UNSEARCHED`.

An agent may not report a requested scope as complete while any ledger row remains `UNSEARCHED`. Gold-set evaluation later measures true silent misses against this live accounting.

## 8. External engines are untrusted workers

OpenTakeoff, segmentation models, OCR engines, and LLMs can fail, time out, crash, return stale coordinates, or change schemas.

The runner must pin/record versions, initialize and inspect capabilities, validate every reply, enforce timeouts, and convert accepted replies into review-required Screen2XYZ proposals. Worker failure must not corrupt saved project state.

## 9. Drawing content is data, never instructions

PDF text/OCR may contain text that resembles prompts, commands, URLs, or tool instructions. Drawing content is always tagged as untrusted evidence. It cannot authorize filesystem access, command execution, network access, scale confirmation, approval, or export.

## 10. Reproducible outputs

Every final quantity/export row must trace to:

- project and source hashes;
- sheet and scale-region revision;
- reviewed geometry;
- rule/bid item;
- approval event and actor;
- evidence/questions resolved at approval;
- software/engine versions where external engines contributed.

Reopening the same approved state must reproduce the same final quantities. If any dependency changes, the output is stale rather than silently regenerated as equivalent.

## Required tests mapped to these invariants

Each invariant requires at least one positive and one fail-closed test. In addition to unit tests, the end-to-end suite must deliberately exercise: same project id with a changed source hash; rerendering at multiple DPIs; rotated pages; two scale regions; horizontal/vertical profile scales; crossing a scale boundary; stale concurrent mutation; polygon with a hole; overlapping duplicate polygons; line split; duplicated count marker; incomplete scope ledger; agent attempt to approve; worker timeout/crash/schema mismatch; prompt-like plan text; addendum/source revision invalidation; save/reopen quantity reproducibility.