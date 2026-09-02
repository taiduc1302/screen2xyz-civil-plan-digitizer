# Next Action

## Current stage: make civil takeoff runnable before real accuracy claims

The review-first quantity domain, workspace, evidence/question model,
OpenTakeoff request adapter, segmentation boundary, and deterministic tests are
implemented on `integration/open-source-takeoff-stack`.

They are not yet a complete operator product. The existing launcher still opens
the point/terrain Civil Plan Digitizer UI; quantity takeoff is not wired into
that UI, the OpenTakeoff adapter does not execute an MCP process, and
Screen2XYZ does not yet expose a runnable MCP gateway for Claude/ChatGPT.
The existing Civil project model is also centered on one selected PDF page and
one page calibration, which is too narrow for a real multi-sheet/mixed-scale
tender takeoff workflow.

## Exactly one recommended next action

Build and validate one **runnable local takeoff vertical slice** before the
private Example Road/Bluebeam accuracy comparison:

1. introduce the bid-set/sheet + scale-region contract (or an intentionally
   limited single-sheet pilot that refuses mixed-scale regions);
2. wire manual line/polygon/count takeoffs and the `.s2t` workspace into the
   local estimator UI;
3. add a real OpenTakeoff process/MCP runner and protocol integration test;
4. add a Screen2XYZ MCP gateway with proposal-only AI tools and human-only
   approval/export gates;
5. add one-command environment diagnostics and an operator run guide;
6. prove save/reopen/QA/export in an end-to-end Windows test.

Only after that vertical slice works should the owner-machine private
Example Road/Bluebeam gold set be used to measure proposal coverage, silent misses,
rule accuracy, and quantity/geometry error.

See `docs/integrations/RUNTIME_OPERATOR_TEST_MODEL.md` for the runtime,
operator, ChatGPT/Claude connection, privacy, scale-region, and test contract.

Real proprietary-drawing use, AGTEK/Civil 3D/Kubla acceptance, marked-plan or
Bluebeam compatibility, default-branch merge, licence selection, packaging,
and public release remain separate owner gates.