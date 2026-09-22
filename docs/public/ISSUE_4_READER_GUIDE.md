# Issue 4: related research code

*Applied AI for Estimating - AI Takeoff Markups in Bluebeam Through MCP*

## Start here

The [research preview](https://github.com/taiduc1302/screen2xyz-civil-plan-digitizer/tree/task/plan-layer-extraction)
contains the related single-sheet MCP and vector-geometry implementation.
The default landing branch and `main` retain the earlier point/terrain baseline;
the cleanup does not silently merge the experimental runtime into it.

On the research branch, start with:

- `src/screen2xyz_civil/mcp_gateway.py`: the host's proposal/evidence tool surface;
- `agent_session.py`: source-bound session and proposal records;
- `pdf.py`, `cad_layers.py`, `vector_fill.py`: PDF text/vector/layer evidence;
- `bluebeam_bridge.py`, `host_frame.py`: working-copy and placement contracts;
- `tests_civil/`: synthetic regression cases and explicit optional/live gates.

Read that branch's README and dependency file before running it. Synthetic
unit tests are not a real-drawing accuracy benchmark. A markup-plan JSON is
not proof of a native Revu Length or Area measurement. Actual Revu/connector
versions still require a disposable create/save/read-back acceptance check.

This is **related experimental source**, not the exact 21-markup demonstration
package from the article, not a production estimator and not approved quantities.
No generated cover image or invented read-back CSV is used as validation evidence.

Suggested article wording:

> Related experimental code is available in the Screen2XYZ research preview.
> It includes the MCP tool gateway, PDF geometry processing and review controls.
> This is research source, not a production-ready estimating tool or a packaged
> reproduction of the demonstration. Use synthetic drawings for evaluation.
