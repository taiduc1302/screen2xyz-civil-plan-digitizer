# Bluebeam Revu 21.10+ MCP native-measurement acceptance gate

Status: owner-machine/live-Revu acceptance procedure. Do not treat this document as evidence that a particular connected Revu instance has passed the gate.

## Product-documented capability boundary

Bluebeam's current MCP documentation establishes a substantial markup/control surface, but it must not be over-read as proof of a native Length/Area creation schema.

Official Bluebeam documentation currently shows, among other functions:

- `add_markup` - create a new markup, available in Revu 21.10+;
- `list_markups_in_pdf` - inspect detailed existing markups, Revu 21.9+;
- `get_markup_shape` - read markup geometry, Revu 21.10+;
- `set_markup_property` - edit properties, Revu 21.9+;
- `set_markup_shape` - edit geometry, Revu 21.10+;
- `set_page_scale` - set document scale, Revu 21.9+.

Revu 21.10 was released 2026-06-02 with expanded MCP workflows. Revu 21.11 was released 2026-09-01 with further MCP expansion, including ChatGPT (Codex) support and additional markup workflow capability.

Bluebeam also publishes QTO/measurement guidance in its MCP community material, but the public general tool table does **not** by itself name a dedicated native `create_length_measurement` or `create_area_measurement` function. Therefore a generic `add_markup` call, even if it visually creates a line or polygon, must not be treated as a proven native measurement until Revu's saved readback demonstrates measurement intent and a live computed quantity.

References:

- https://support.bluebeam.com/revu/resources/revu-mcp.html
- https://support.bluebeam.com/revu/resources/revu-21-release-notes.html
- https://support.bluebeam.com/revu/how-to/mcp-anything.html
- https://community.bluebeam.com/kb/articles/327-2-can-mcp-support-qto-and-measurements

This establishes only `PRODUCT_DOCUMENTED` facts. The exact current Revu/MCP host must separately establish `CURRENT_SURFACE_EXPOSED` and then `LIVE_TESTED`.

## Immutable source vs working PDF

Never run this test on the Screen2XYZ immutable source PDF. The `.s2a.json` session deliberately guards that source by exact SHA-256.

Native Revu work belongs in a **separate registered Bluebeam working copy**. Before this acceptance test:

1. call Screen2XYZ `bluebeam_working_copy_status` (or `agent-status` outside MCP);
2. require `safe_for_bluebeam_operator = true` and `drawing_match = true`;
3. verify the active Revu document is exactly the registered working-copy PDF, not the immutable source;
4. preferably create a disposable clone of the working PDF for the acceptance markups, then reopen the registered working PDF after the gate passes.

A working PDF is allowed to change full-file SHA when annotations are saved. Its underlying selected-page drawing fingerprint must continue to match the immutable source. If it does not, stop: this is a drawing/revision mismatch, not a harmless markup save.

## Why this gate exists

Screen2XYZ can propose and validate geometry independently, but the final civil workflow needs native Revu measurement markups whose quantity is computed by the active Revu scale/viewport. A JSON plan, a generic Line, or a generic Polygon is not sufficient evidence that a native Length/Area measurement was created correctly.

Before Claude is allowed to mass-create takeoff measurements, prove the exact connected Revu path once on disposable local test markups.

## Preconditions

Confirm:

1. Record the exact Revu point version. Use Revu 21.10+ for markup create/edit workflows; prefer the currently approved/current company version rather than inferring the version from a `Revu\21` install folder.
2. Confirm the user has the Bluebeam plan/licensing required for MCP. Bluebeam's current MCP documentation identifies this as a Max-plan feature.
3. In `Revu > Preferences > Admin > MCP`, MCP is enabled for a supported/current host path.
4. The Bluebeam MCP server is connected to the same Claude workflow that has `screen2xyz`, or is otherwise exposed through a separately verified local MCP host.
5. The active PDF is the disposable acceptance clone of the registered working copy (or, if intentionally testing in place, the registered working copy itself) — never the immutable source.
6. The PDF allows adding/changing markups and is not blocked by certification, security, read-only restrictions, or Studio ownership rules.
7. The relevant page/viewport scale is resolved **and independently verified** in Revu.
8. Persistent measurement behavior is enabled so the test creates a Markups List entry.
9. The acceptance markups are clearly disposable and outside production takeoff geometry where possible.

If any precondition fails, stop and report it. Do not work around security, locked Session ownership, an unresolved scale, or a source/working-copy mismatch.

## Runtime capability discovery

In Claude, inspect the actual Bluebeam MCP tools before calling them. Record three capability states separately:

- `PRODUCT_DOCUMENTED`: Bluebeam documentation says the product version supports the relevant general capability.
- `CURRENT_SURFACE_EXPOSED`: the current MCP tool list/schema exposes a plausible operation for the needed native measurement path.
- `LIVE_TESTED`: a create/save/readback round trip succeeded in this exact environment and Revu itself returned the expected native measurement state/quantity.

At minimum inspect the current equivalents of page information/scale, listing markups, creating a markup/measurement, reading properties/geometry, changing Subject/Comment/properties, and deleting the disposable markup if safe.

Do **not** invent a runtime function or payload because an online example exists. Use the schemas the connected server actually advertises. Do not equate `add_markup created a Line`, `a line is visible in Revu`, and `Revu created a native Length measurement with a live scaled quantity`. Only the last statement passes the Length gate.

## Live Length acceptance

1. Choose two safe points in one confirmed-scale region whose real distance can be independently checked.
2. Using only the actual exposed Bluebeam MCP schema, attempt to create one **native Length measurement**.
3. Give it an unmistakable Subject/Comment such as `S2XYZ ACCEPTANCE - DELETE` and a unique acceptance ID.
4. Save/allow Revu to persist the markup.
5. Read the saved markup back through the MCP server and verify markup ID, page, native Length intent/type, unit, live Revu-computed quantity, Subject/Comment, and geometry/endpoints where exposed.
6. Compare the live quantity with the independently expected distance within the chosen tolerance.
7. Delete the acceptance markup if safely exposed, or manually delete it after recording the result.

If the runtime offers only generic Line creation with no native measurement intent/live quantity, classify `MEASUREMENT_CREATE_NOT_EXPOSED`; do not calculate the distance outside Revu and call that a pass.

## Live Area acceptance

Repeat the same procedure with a small, simple rectangle in one confirmed-scale region:

1. Attempt to create a **native Area measurement**, not merely a generic Polygon.
2. Use a known rectangle so expected area is deterministic.
3. Read back type/intent, unit, live computed area, Subject/Comment, and geometry where exposed.
4. Compare the Revu-computed area with the independently expected value.
5. Clean up the disposable markup.

If only a generic Polygon can be created/read back, the native Area gate has not passed.

## Acceptance record

Record a small local/private JSON or Markdown result containing timestamp, exact Revu point version, Bluebeam plan/license state, MCP host/client/registration route, registered working-copy identity/fingerprint status, active acceptance PDF, page and scale/viewport basis, actual tool names/schemas, Length expected vs readback, Area expected vs readback, property/geometry readback coverage, cleanup, and overall disposition.

Recommended overall values:

- `LIVE_MEASUREMENT_CREATE_READBACK_PASS`
- `CREATE_EXPOSED_READBACK_INCOMPLETE`
- `GENERIC_MARKUP_ONLY_NOT_NATIVE_MEASUREMENT`
- `MEASUREMENT_CREATE_NOT_EXPOSED`
- `SCALE_NOT_VERIFIED`
- `DOCUMENT_NOT_EDITABLE`
- `WORKING_COPY_MISMATCH`
- `FAILED_OTHER`

Keep proprietary/project-specific acceptance evidence local unless the owner intentionally sanitizes it.

## Promotion rule

Only after **both** a native Length and native Area create + saved Revu readback pass may the Claude operator classify native measurement creation as `LIVE_TESTED` for that exact machine/Revu/MCP setup.

Then the production loop is:

```text
immutable Screen2XYZ drawing evidence
  -> Screen2XYZ proposal / rule / flags / scale QA
  -> verify registered working PDF drawing_match
  -> Bluebeam native Length or Area create/edit on working PDF
  -> set traceability Subject/Comment
  -> saved Revu readback
  -> verify native measurement intent + live Revu quantity
  -> compare Revu quantity/geometry to Screen2XYZ intent
  -> verify working-copy drawing_match still true
  -> QA_CHECKED
  -> human estimator review later
```

A later Revu/MCP upgrade, host/configuration change, profile change, scale model change, document security change, or materially different tool schema should trigger a new acceptance test.

## Studio Session warning

Do not use this acceptance test to prove editability of inherited/pre-existing Studio Session markups. Bluebeam Session ownership rules are separate. For production takeoff editing, prefer the registered local editable working file and use a Session as the review/published collaboration layer when that matches the project workflow.