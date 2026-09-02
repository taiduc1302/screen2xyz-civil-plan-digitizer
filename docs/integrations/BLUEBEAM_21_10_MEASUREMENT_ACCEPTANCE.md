# Bluebeam Revu 21.10 MCP measurement acceptance gate

Status: owner-machine/live-Revu acceptance procedure. Do not treat this document as evidence that a particular connected Revu instance has passed the gate.

## Product-documented capability

As of Revu 21.10 (released 2026-06-02), Bluebeam documents expanded MCP workflows and states that **measurement capabilities are available in Revu 21.10**. Bluebeam also documents MCP markup management functions in 21.10 such as creating markups, listing markups, reading markup geometry, editing markup geometry, and changing markup properties.

References:

- https://support.bluebeam.com/revu/resources/revu-mcp.html
- https://community.bluebeam.com/kb/articles/327-2-can-mcp-support-qto-and-measurements
- https://support.bluebeam.com/revu/resources/revu-21-release-notes.html

This establishes `PRODUCT_DOCUMENTED`, not `CURRENT_SURFACE_EXPOSED` or `LIVE_TESTED` for the user's current Revu/MCP connection. Tool names/schemas exposed to the current MCP host must be discovered at runtime instead of invented from documentation.

## Why this gate exists

Screen2XYZ can propose and validate geometry independently, but the final civil workflow needs native Revu measurement markups whose quantity is computed by the active Revu scale/viewport. A JSON plan or a generic Polygon markup is not sufficient evidence that a native Area/Length measurement was created correctly.

Before Claude is allowed to mass-create takeoff measurements, prove the exact connected Revu path once on a disposable local test markup.

## Preconditions

Use an editable **local working copy**, not the only authoritative tender file and not a Studio Session baseline whose inherited markups are frozen. Confirm:

1. Revu version is 21.10 or later.
2. The Bluebeam MCP server is enabled and connected to the same Claude host that has `screen2xyz`.
3. The intended PDF is the active PDF in Revu; Bluebeam MCP access is scoped to the active document.
4. The PDF allows adding/changing markups and is not blocked by certification/security/read-only restrictions.
5. The relevant page/viewport scale is resolved and independently verified in Revu.
6. `Make Annotation`/equivalent measurement behavior is enabled so persistent measurements create Markups List entries.
7. The acceptance markup is clearly disposable and outside production takeoff geometry where possible.

If any precondition fails, stop and report it. Do not work around security, locked Session ownership, or an unresolved scale.

## Runtime capability discovery

In Claude, inspect the actual Bluebeam MCP tools before calling them. Record three capability states separately:

- `PRODUCT_DOCUMENTED`: Bluebeam documentation says the product version supports it.
- `CURRENT_SURFACE_EXPOSED`: the current MCP tool list/schema exposes the needed operation.
- `LIVE_TESTED`: a create/save/readback round trip succeeded in this environment.

At minimum look for the current equivalents of:

- listing markups in the active PDF;
- creating a markup/measurement;
- reading the created markup's properties and/or geometry;
- changing Subject/Comment/properties;
- deleting the disposable markup after the test if safe.

Do **not** assume the runtime function is literally named `add_markup`, and do not assume a generic Polygon is a native Area measurement. Use the schemas the connected server actually advertises.

## Live Length acceptance

1. Choose two safe points in one confirmed-scale region whose real distance can be independently checked.
2. Create one **native Length measurement** through the actual exposed Bluebeam MCP measurement path.
3. Give it an unmistakable Subject/Comment such as `S2XYZ ACCEPTANCE - DELETE` and a unique acceptance ID.
4. Save/allow Revu to persist the markup.
5. Read it back through the MCP server and verify:
   - markup ID exists;
   - correct page;
   - native measurement/markup intent is Length, not a generic Line;
   - unit is the intended unit;
   - live computed quantity is present and numerically agrees with the independently expected distance within the chosen tolerance;
   - Subject/Comment survived;
   - geometry/endpoints agree with the requested test geometry where exposed.
6. Delete the acceptance markup if deletion is safely exposed, or manually delete it after recording the result.

If any readback field is unavailable, mark that field `NOT_EXPOSED`; do not fabricate verification.

## Live Area acceptance

Repeat the same procedure with a small, simple rectangle in one confirmed-scale region:

1. Create a **native Area measurement**, not a generic Polygon.
2. Use a known rectangle so expected area is deterministic.
3. Read back type/intent, unit, live computed area, Subject/Comment, and geometry where exposed.
4. Compare the Revu-computed area with the independently expected value.
5. Clean up the disposable markup.

## Acceptance record

Record a small local/private JSON or Markdown result containing:

- timestamp;
- Revu version;
- MCP host/client;
- active PDF hash/name (do not commit a proprietary path/content);
- page and scale/viewport basis;
- actual tool names used;
- actual tool schema/version information if exposed;
- Length test expected vs readback quantity and pass/fail;
- Area test expected vs readback quantity and pass/fail;
- property/geometry readback coverage;
- cleanup result;
- overall disposition.

Recommended overall values:

- `LIVE_MEASUREMENT_CREATE_READBACK_PASS`
- `CREATE_EXPOSED_READBACK_INCOMPLETE`
- `MEASUREMENT_CREATE_NOT_EXPOSED`
- `SCALE_NOT_VERIFIED`
- `DOCUMENT_NOT_EDITABLE`
- `FAILED_OTHER`

Keep proprietary/project-specific acceptance evidence local unless the owner intentionally sanitizes it.

## Promotion rule

Only after **both** a Length and Area create + saved readback pass may the Claude operator treat Bluebeam native measurement creation as `LIVE_TESTED` for that machine/Revu/MCP setup.

Then the production loop for each Screen2XYZ proposal is:

```text
Screen2XYZ proposal
  -> verify rule / geometry / flags / scale region
  -> Bluebeam native Length or Area creation
  -> set traceability Subject/Comment
  -> saved Revu readback
  -> compare Revu quantity/geometry to Screen2XYZ intent
  -> QA_CHECKED
  -> human estimator review later
```

A later Revu/MCP upgrade, profile change, scale model change, document security change, or materially different tool schema should trigger a new acceptance test.

## Studio Session warning

Do not use this acceptance test to prove editability of inherited/pre-existing Studio Session markups. Bluebeam Session ownership rules are a separate concern. For production takeoff editing, prefer a local editable working file and use a Session as the review/published collaboration layer when that matches the project workflow.
